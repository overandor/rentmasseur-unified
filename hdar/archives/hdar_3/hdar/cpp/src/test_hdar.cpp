#include "hdar/crypto.hpp"
#include "hdar/store.hpp"
#include "hdar/identity.hpp"
#include "hdar/receipt.hpp"
#include "hdar/seal.hpp"
#include "hdar/restore.hpp"
#include "hdar/capabilities.hpp"
#include "hdar/state_machine.hpp"
#include "hdar/effects.hpp"
#include "hdar/lease.hpp"
#include "hdar/controller.hpp"
#include "hdar/provider_base.hpp"
#include "hdar/unsafe_host.hpp"
#include "hdar/offline_verify.hpp"
#include "hdar/restoration_contract.hpp"
#include "hdar/execution_receipt.hpp"
#include "hdar/termination_receipt.hpp"
#include "hdar/host_attestation.hpp"
#include "hdar/continuity.hpp"
#include "hdar/gateway.hpp"
#include "hdar/reliability.hpp"
#include "hdar/remote_ssh.hpp"

#include <iostream>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

static int tests_passed = 0;
static int tests_failed = 0;

#define TEST(name) static void name()
#define RUN(test) do { \
    std::cout << "  " #test " ... "; \
    try { test(); std::cout << "OK\n"; ++tests_passed; } \
    catch (const std::exception& e) { std::cout << "FAIL: " << e.what() << "\n"; ++tests_failed; } \
} while(0)

#define ASSERT(cond) do { if (!(cond)) throw std::runtime_error(#cond " failed"); } while(0)

// ── Crypto tests ──────────────────────────────────────────────

TEST(test_ed25519_sign_verify) {
    auto owner = hdar::OwnerKeyPair::generate();
    hdar::JsonValue obj = hdar::JsonValue::object();
    obj["test"] = hdar::JsonValue::string("value");
    std::string sig = owner.sign_json(obj);
    ASSERT(owner.public_key.verify_json(obj, sig));
    ASSERT(!owner.public_key.verify_json(obj, "00"));
}

TEST(test_key_roundtrip) {
    auto owner = hdar::OwnerKeyPair::generate();
    std::string hex = owner.private_key_hex();
    auto restored = hdar::OwnerKeyPair::from_private_hex(hex);
    ASSERT(restored.fingerprint() == owner.fingerprint());
    ASSERT(restored.public_key_hex() == owner.public_key_hex());
}

TEST(test_canonical_json) {
    hdar::JsonValue obj = hdar::JsonValue::object();
    obj["z"] = hdar::JsonValue::integer(1);
    obj["a"] = hdar::JsonValue::string("test");
    obj["m"] = hdar::JsonValue::boolean(true);
    std::string canon = hdar::canonical_json(obj);
    ASSERT(canon.find("\"a\"") < canon.find("\"m\""));
    ASSERT(canon.find("\"m\"") < canon.find("\"z\""));
}

TEST(test_sha256) {
    std::string hash = hdar::sha256_hex("hello");
    ASSERT(hash.size() == 64);
    // Known SHA-256 of "hello"
    ASSERT(hash == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824");
}

TEST(test_host_key_pair) {
    auto host = hdar::HostKeyPair::generate("host-1");
    ASSERT(host.fingerprint() != "");
    ASSERT(host.host_id == "host-1");
    hdar::JsonValue obj = hdar::JsonValue::object();
    obj["x"] = hdar::JsonValue::integer(42);
    std::string sig = host.sign_json(obj);
    ASSERT(host.public_key.verify_json(obj, sig));
}

// ── Store tests ───────────────────────────────────────────────

TEST(test_content_store) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    hdar::ContentStore store(dir + "/store");
    std::vector<uint8_t> data = {'t', 'e', 's', 't'};
    std::string hash = store.ingest_bytes(data);
    auto retrieved = store.retrieve(hash);
    ASSERT(retrieved == data);
    fs::remove_all(dir);
}

TEST(test_workspace_ingest_restore) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string ws = dir + "/ws";
    fs::create_directories(ws);
    std::ofstream(ws + "/a.txt") << "content a";
    fs::create_directories(ws + "/sub");
    std::ofstream(ws + "/sub/b.txt") << "content b";

    hdar::ContentStore store(dir + "/store");
    auto manifest = store.ingest_workspace(ws);
    ASSERT(manifest.files.size() == 2);
    ASSERT(!manifest.root_hash.empty());

    std::string restored = dir + "/restored";
    store.restore_workspace(manifest, restored);
    ASSERT(fs::exists(restored + "/a.txt"));
    ASSERT(fs::exists(restored + "/sub/b.txt"));

    auto restored_manifest = store.hash_workspace(restored);
    ASSERT(restored_manifest.root_hash == manifest.root_hash);

    fs::remove_all(dir);
}

// ── Identity tests ─────────────────────────────────────────────

TEST(test_agent_identity) {
    auto id = hdar::AgentIdentity::create("agent1");
    ASSERT(id.name == "agent1");
    ASSERT(!id.agent_id.empty());
    ASSERT(id.fingerprint().size() == 16);
}

TEST(test_lineage_epoch) {
    auto id = hdar::AgentIdentity::create("agent1");
    auto e0 = hdar::LineageEpoch::genesis(id.agent_id);
    auto e1 = hdar::LineageEpoch::child(e0);
    ASSERT(e0.sequence == 0);
    ASSERT(e1.sequence == 1);
    ASSERT(e1.parent_epoch.value() == e0.epoch_id);
    ASSERT(e1.agent_id == e0.agent_id);
}

// ── Receipt tests ─────────────────────────────────────────────

TEST(test_receipt_chain) {
    auto id = hdar::AgentIdentity::create("agent1");
    auto epoch = hdar::LineageEpoch::genesis(id.agent_id);
    hdar::ReceiptChain chain(id.agent_id, epoch.epoch_id, id.signing_key);
    chain.append("SEAL", "sealed");
    chain.append("DESTROY", "destroyed");
    ASSERT(chain.size() == 2);
    ASSERT(chain.verify(id.public_key()));
}

// ── Capability tests ──────────────────────────────────────────

TEST(test_capability_non_expansion) {
    std::vector<hdar::Capability> src = {
        {"filesystem.read", "/workspace", true, {}},
        {"filesystem.write", "/workspace", true, {}},
    };
    std::vector<hdar::Capability> dst = {
        {"filesystem.read", "/workspace", true, {}},
        {"filesystem.write", "/workspace", true, {}},
    };
    hdar::CapabilityCompiler compiler;
    auto [ok, violations] = compiler.verify_non_expansion(src, dst);
    ASSERT(ok);
    ASSERT(violations.empty());
}

TEST(test_capability_expansion_detected) {
    std::vector<hdar::Capability> src = {
        {"filesystem.read", "/workspace", true, {}},
    };
    std::vector<hdar::Capability> dst = {
        {"filesystem.read", "/", true, {}},  // broader scope
    };
    hdar::CapabilityCompiler compiler;
    auto [ok, violations] = compiler.verify_non_expansion(src, dst);
    ASSERT(!ok);
    ASSERT(!violations.empty());
}

TEST(test_capability_compile_attenuation) {
    std::vector<hdar::Capability> src = {
        {"budget.spend", "$100", true, {}},
    };
    std::map<std::string, std::string> policy = {
        {"budget.max", "$50"},
    };
    hdar::CapabilityCompiler compiler;
    auto [dst, rejections] = compiler.compile(src, policy);
    ASSERT(!dst.empty());
    ASSERT(dst[0].scope == "$50");
}

// ── Lease tests ───────────────────────────────────────────────

TEST(test_lease_acquire_release) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    hdar::LeaseManager lm(dir + "/leases.db");
    auto [lease, err] = lm.acquire("agent1", "hash1", 0, "holder1", "rt1");
    ASSERT(lease.has_value());
    ASSERT(!err.has_value());
    ASSERT(lm.validate_token("agent1", lease->fencing_token));
    ASSERT(lm.release("agent1", lease->fencing_token));
    ASSERT(!lm.validate_token("agent1", lease->fencing_token));
    fs::remove_all(dir);
}

TEST(test_lease_stale_rejected) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    hdar::LeaseManager lm(dir + "/leases.db");
    auto [lease, err] = lm.acquire("agent1", "hash1", 0, "holder1", "rt1");
    ASSERT(lm.reject_stale("agent1", "stale-token"));
    ASSERT(!lm.reject_stale("agent1", lease->fencing_token));
    lm.release("agent1", lease->fencing_token);
    fs::remove_all(dir);
}

// ── State machine tests ───────────────────────────────────────

TEST(test_state_machine_transitions) {
    hdar::LifecycleStateMachine sm("agent1");
    ASSERT(sm.is_dormant());
    ASSERT(sm.transition(hdar::AgentState::ACQUIRING_LEASE));
    ASSERT(sm.transition(hdar::AgentState::MATERIALIZING));
    ASSERT(sm.transition(hdar::AgentState::VERIFYING_INPUT));
    ASSERT(sm.transition(hdar::AgentState::RUNNING));
    ASSERT(sm.is_running());
    ASSERT(!sm.transition(hdar::AgentState::DORMANT)); // invalid
}

// ── Provider tests ────────────────────────────────────────────

TEST(test_unsafe_host_provider) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string ws = dir + "/ws";
    fs::create_directories(ws);
    std::ofstream(ws + "/test.txt") << "test";

    hdar::UnsafeHostProvider provider(dir + "/sandbox");
    auto rt = provider.materialize("rt1", ws);
    ASSERT(rt.exists);
    auto exec = provider.execute("rt1", "test", "echo hello");
    ASSERT(exec.success);
    provider.destroy("rt1");
    ASSERT(provider.verify_destruction("rt1"));
    fs::remove_all(dir);
}

// ── Restoration contract tests ────────────────────────────────

TEST(test_restoration_exact) {
    hdar::RestorationContract rc;
    auto report = rc.classify("arm64", "linux", "none", "arm64", "linux", "none",
                               true, true, true, {});
    ASSERT(report.restoration_class == hdar::RestorationClass::EXACT);
}

TEST(test_restoration_degraded) {
    hdar::RestorationContract rc;
    auto report = rc.classify("arm64", "linux", "metal", "x86_64", "linux", "cuda",
                               false, true, true, {"gpu"});
    ASSERT(report.restoration_class == hdar::RestorationClass::DEGRADED);
}

// ── Evidence tests ────────────────────────────────────────────

TEST(test_execution_receipt) {
    auto host = hdar::HostKeyPair::generate("host-1");
    hdar::ExecutionReceiptBuilder erb("capsule-hash-123", host, "rt-1", "apple-container");
    erb.add_operation("task", hdar::JsonValue::object());
    auto receipt = erb.build_and_sign();
    ASSERT(receipt.verify(host.public_key));
    ASSERT(receipt.host_fingerprint == host.fingerprint());
}

TEST(test_termination_receipt) {
    auto owner = hdar::OwnerKeyPair::generate();
    hdar::JsonValue inspection = hdar::JsonValue::object();
    inspection["exists"] = hdar::JsonValue::boolean(false);
    auto receipt = hdar::build_termination_receipt("rt-1", "apple-container",
                                                     inspection, "fence-token-123",
                                                     owner.private_key);
    ASSERT(receipt.verify(owner.public_key));
    ASSERT(!receipt.fencing_token_revoked.empty());
}

TEST(test_host_attestation) {
    auto host = hdar::HostKeyPair::generate("host-1");
    auto att = hdar::build_host_attestation("host-1", host, "rt-1", "apple-container",
                                             "arm64", "linux", "6.6.0", "Apple M5", 8,
                                             "16g", "none", "none");
    ASSERT(att.verify(host.public_key));
    ASSERT(att.arch == "arm64");
}

// ── Offline verifier tests ────────────────────────────────────

TEST(test_offline_verifier_capabilities) {
    auto owner = hdar::OwnerKeyPair::generate();
    hdar::OfflineVerifier verifier(owner.public_key);
    std::vector<hdar::Capability> src = {{"filesystem.read", "/workspace", true, {}}};
    std::vector<hdar::Capability> dst = {{"filesystem.read", "/workspace", true, {}}};
    auto result = verifier.verify_capability_continuity(src, dst);
    ASSERT(result.overall_pass);
}

// ── Continuity loop test ──────────────────────────────────────

TEST(test_continuity_loop) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string ws = dir + "/workspace";
    fs::create_directories(ws);
    std::ofstream(ws + "/input.txt") << "task data";

    auto owner = hdar::OwnerKeyPair::generate();
    hdar::ContentStore store(dir + "/store");
    hdar::UnsafeHostProvider pa(dir + "/sandbox-a");
    hdar::UnsafeHostProvider pb(dir + "/sandbox-b");

    std::map<std::string, std::string> policy = {
        {"filesystem.root", "/workspace"},
        {"network.allowlist", "api.example.com"},
        {"budget.max", "$50"},
    };

    hdar::ContinuityLoop loop(owner, store, &pa, &pb);
    auto result = loop.run(ws, "complete task", policy, "echo done > output.txt");

    ASSERT(result.assertions_failed == 0);
    ASSERT(result.success);
    ASSERT(result.verification.overall_pass);

    fs::remove_all(dir);
}

// ── Item 1: Reliability harness tests ─────────────────────────

TEST(test_reliability_100_cycles) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string ws = dir + "/ws";
    fs::create_directories(ws);
    std::ofstream(ws + "/input.txt") << "reliability test data";

    hdar::ContentStore store(dir + "/store");
    hdar::UnsafeHostProvider provider(dir + "/sandbox");

    hdar::ReliabilityHarness harness(&provider, store, ws);
    auto result = harness.run_cycles(100);

    ASSERT(result.cycles_run == 100);
    ASSERT(result.cycles_passed == 100);
    ASSERT(result.cycles_failed == 0);
    ASSERT(result.failures.empty());
    ASSERT(result.cleanup_verifications.size() == 100);

    fs::remove_all(dir);
}

TEST(test_reliability_failure_injection) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string ws = dir + "/ws";
    fs::create_directories(ws);
    std::ofstream(ws + "/input.txt") << "failure injection test";

    hdar::ContentStore store(dir + "/store");
    hdar::UnsafeHostProvider provider(dir + "/sandbox");

    hdar::ReliabilityHarness harness(&provider, store, ws);

    // Inject failure at cycle 5 — destroy the runtime before the harness can
    int injected_cycle = -1;
    harness.set_failure_injector([&](int cycle, const std::string& runtime_id) {
        if (cycle == 5) {
            injected_cycle = cycle;
            harness.inject_failure(cycle, "premature_destroy");
            provider.destroy(runtime_id);
        }
    });

    auto result = harness.run_cycles(10);

    // Cycle 5 should fail because the runtime was already destroyed
    ASSERT(result.cycles_run == 10);
    ASSERT(result.cycles_failed >= 1);
    ASSERT(injected_cycle == 5);
    ASSERT(!result.failure_injections.empty());

    fs::remove_all(dir);
}

// ── Item 2: Fencing validation tests ──────────────────────────

TEST(test_fencing_all_effect_states) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);

    hdar::LeaseManager lm(dir + "/leases.db");
    auto [lease, err] = lm.acquire("agent1", "hash1", 0, "holder1", "rt1");
    ASSERT(lease.has_value());

    hdar::EffectRegistry effects(dir + "/effects.jsonl", &lm, "agent1");

    std::vector<uint8_t> payload = {'t', 'e', 's', 't'};

    auto reg = effects.register_effect("agent1", "filesystem.read", payload,
                                        "op-1", lease->fencing_token);
    ASSERT(reg.status == "starting");

    auto submitted = effects.submit("agent1", "op-1", lease->fencing_token);
    ASSERT(submitted.status == "submitted");

    auto committed = effects.commit("agent1", "op-1", hdar::JsonValue::null(),
                                     lease->fencing_token);
    ASSERT(committed.status == "committed");

    auto reg2 = effects.register_effect("agent1", "filesystem.read", payload,
                                         "op-2", lease->fencing_token);
    ASSERT(reg2.status == "starting");

    auto unknown = effects.mark_unknown("agent1", "op-2", lease->fencing_token);
    ASSERT(unknown.status == "unknown");

    auto reg3 = effects.register_effect("agent1", "filesystem.read", payload,
                                         "op-3", lease->fencing_token);
    ASSERT(reg3.status == "starting");

    auto cancelled = effects.cancel("agent1", "op-3", lease->fencing_token);
    ASSERT(cancelled.status == "cancelled");

    lm.release("agent1", lease->fencing_token);
    auto [lease2, err2] = lm.acquire("agent1", "hash1", 1, "holder2", "rt2");
    ASSERT(lease2.has_value());

    bool threw = false;
    try {
        effects.register_effect("agent1", "filesystem.read", payload,
                                "op-stale", lease->fencing_token);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    ASSERT(threw);

    auto reg_stale = effects.register_effect("agent1", "filesystem.read", payload,
                                               "op-stale-submit", lease2->fencing_token);
    ASSERT(reg_stale.status == "starting");

    threw = false;
    try {
        effects.submit("agent1", "op-stale-submit", lease->fencing_token);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    ASSERT(threw);

    auto reg_stale2 = effects.register_effect("agent1", "filesystem.read", payload,
                                                "op-stale-unknown", lease2->fencing_token);
    threw = false;
    try {
        effects.mark_unknown("agent1", "op-stale-unknown", lease->fencing_token);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    ASSERT(threw);

    auto reg_stale3 = effects.register_effect("agent1", "filesystem.read", payload,
                                                "op-stale-cancel", lease2->fencing_token);
    threw = false;
    try {
        effects.cancel("agent1", "op-stale-cancel", lease->fencing_token);
    } catch (const std::runtime_error&) {
        threw = true;
    }
    ASSERT(threw);

    lm.release("agent1", lease2->fencing_token);
    fs::remove_all(dir);
}

TEST(test_concurrent_acquire) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    hdar::LeaseManager lm(dir + "/leases.db");

    // First acquire should succeed
    auto [lease1, err1] = lm.acquire("agent1", "hash1", 0, "holder1", "rt1");
    ASSERT(lease1.has_value());
    ASSERT(!err1.has_value());

    // Second concurrent acquire for same agent should fail (lease already held)
    auto [lease2, err2] = lm.acquire("agent1", "hash1", 0, "holder2", "rt2");
    ASSERT(!lease2.has_value());
    ASSERT(err2.has_value());

    // Different agent should succeed
    auto [lease3, err3] = lm.acquire("agent2", "hash2", 0, "holder3", "rt3");
    ASSERT(lease3.has_value());

    // Release first lease, then acquire should succeed again
    ASSERT(lm.release("agent1", lease1->fencing_token));
    auto [lease4, err4] = lm.acquire("agent1", "hash1", 1, "holder4", "rt4");
    ASSERT(lease4.has_value());
    ASSERT(lease4->lease_generation > lease1->lease_generation);

    lm.release("agent1", lease4->fencing_token);
    lm.release("agent2", lease3->fencing_token);
    fs::remove_all(dir);
}

TEST(test_stale_holder_cannot_collapse) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string ws = dir + "/ws";
    fs::create_directories(ws);
    std::ofstream(ws + "/input.txt") << "stale holder test";

    auto owner = hdar::OwnerKeyPair::generate();
    hdar::ContentStore store(dir + "/store");
    hdar::UnsafeHostProvider provider(dir + "/sandbox");

    hdar::AgentIdentity identity = hdar::AgentIdentity::create_with_key("agent1", owner.private_key);

    hdar::ControllerConfig config;
    config.workspace_root = dir + "/workspace";
    config.store_dir = dir + "/store";
    config.lease_db = dir + "/leases.db";
    config.effects_ledger = dir + "/effects.jsonl";
    config.lease_ttl = 900;

    hdar::LifecycleController controller(identity, &provider, store, config);

    // Wake the agent
    auto [runtime, wake_err] = controller.wake("capsule-hash-1", ws);
    ASSERT(runtime.exists);
    ASSERT(!wake_err.has_value());

    // Create the workspace directory that collapse() will seal from
    std::string seal_ws = config.workspace_root + "/" + runtime.runtime_id;
    fs::create_directories(seal_ws);
    std::ofstream(seal_ws + "/output.txt") << "task output";

    std::string stale_token = "stale-invalid-token";

    // Attempt collapse with stale fencing token — should be rejected
    auto epoch = hdar::LineageEpoch::genesis(identity.agent_id);
    auto result = controller.collapse(epoch, "objective", "continuation",
                                       "summary", hdar::JsonValue::object(),
                                       "", std::nullopt, stale_token);

    ASSERT(!result.get("collapsed").bool_val);
    ASSERT(result.get("reason").string_val.find("stale") != std::string::npos);

    // Now collapse with correct fencing token
    auto result2 = controller.collapse(epoch, "objective", "continuation",
                                        "summary", hdar::JsonValue::object(),
                                        "", std::nullopt, controller.fencing_token());

    ASSERT(result2.get("collapsed").bool_val);

    fs::remove_all(dir);
}

// ── Item 3: Remote SSH Provider test ──────────────────────────

TEST(test_remote_ssh_provider) {
    // Skip if passwordless SSH to localhost isn't configured
    int ssh_check = system("ssh -o BatchMode=yes -o ConnectTimeout=2 localhost true 2>/dev/null");
    if (ssh_check != 0) {
        std::cout << "  ... SKIPPED (no passwordless SSH to localhost)\n";
        return;
    }

    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string ws = dir + "/ws";
    fs::create_directories(ws);
    std::ofstream(ws + "/input.txt") << "remote ssh test data";

    // Test against localhost — this exercises the full SSH path
    // without requiring a second physical host
    hdar::RemoteSshProvider provider("localhost", "", dir + "/remote", 22);

    std::string runtime_id = "remote-test-" + hdar::generate_uuid_hex().substr(0, 8);

    auto record = provider.materialize(runtime_id, ws);
    ASSERT(record.exists);
    ASSERT(record.provider == "remote-ssh");

    auto exec = provider.execute(runtime_id, "test", "echo hello_from_remote");
    ASSERT(exec.success);
    ASSERT(exec.stdout_text.find("hello_from_remote") != std::string::npos);

    auto insp = provider.inspect(runtime_id);
    ASSERT(insp.get("exists").bool_val);

    auto destroyed = provider.destroy(runtime_id);
    ASSERT(!destroyed.exists);

    ASSERT(provider.verify_destruction(runtime_id));

    fs::remove_all(dir);
}

// ── Item 4: SSH Gateway config tests ──────────────────────────

TEST(test_gateway_config_load_save) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    fs::create_directories(dir);

    hdar::LeaseManager lm(dir + "/leases.db");

    auto resolver = [](const std::string&) -> std::optional<hdar::CapsuleManifest> {
        return std::nullopt;
    };
    auto materializer = [](const hdar::CapsuleManifest&,
                           const std::string&) -> std::pair<hdar::RuntimeRecord, std::optional<std::string>> {
        hdar::RuntimeRecord r;
        r.exists = false;
        return {r, "not implemented"};
    };

    hdar::SshGateway gateway(lm, resolver, materializer);

    // Register agents
    hdar::AgentRegistration reg1;
    reg1.ssh_user = "agent-user-1";
    reg1.agent_id = "agent-001";
    reg1.agent_name = "Test Agent 1";
    reg1.default_capsule_hash = "hash-abc123";
    reg1.capabilities_json = "[{\"name\":\"filesystem.read\",\"scope\":\"/workspace\"}]";
    reg1.authorized_public_key = "ssh-ed25519 AAAA... test1";

    hdar::AgentRegistration reg2;
    reg2.ssh_user = "agent-user-2";
    reg2.agent_id = "agent-002";
    reg2.agent_name = "Test Agent 2";
    reg2.default_capsule_hash = "hash-def456";
    reg2.capabilities_json = "[{\"name\":\"filesystem.write\",\"scope\":\"/workspace\"}]";
    reg2.authorized_public_key = "ssh-ed25519 BBBB... test2";

    gateway.register_agent(reg1);
    gateway.register_agent(reg2);

    ASSERT(gateway.registrations().size() == 2);

    // Save config
    std::string config_path = dir + "/gateway_config.json";
    gateway.save_config(config_path);
    ASSERT(fs::exists(config_path));

    // Compute hash for integrity verification
    std::string config_hash = hdar::SshGateway::compute_config_hash(config_path);
    ASSERT(!config_hash.empty());
    ASSERT(config_hash.size() == 64);

    // Load config back
    auto loaded = hdar::SshGateway::load_config(config_path);
    ASSERT(loaded.size() == 2);
    ASSERT(loaded[0].ssh_user == "agent-user-1");
    ASSERT(loaded[0].agent_id == "agent-001");
    ASSERT(loaded[0].default_capsule_hash == "hash-abc123");
    ASSERT(loaded[1].ssh_user == "agent-user-2");
    ASSERT(loaded[1].agent_id == "agent-002");

    // Verify integrity
    ASSERT(hdar::SshGateway::verify_config_integrity(config_path, config_hash));

    fs::remove_all(dir);
}

TEST(test_gateway_config_tamper_detection) {
    std::string dir = "/tmp/hdar-test-" + hdar::generate_uuid_hex().substr(0, 8);
    fs::create_directories(dir);

    hdar::LeaseManager lm(dir + "/leases.db");

    auto resolver = [](const std::string&) -> std::optional<hdar::CapsuleManifest> {
        return std::nullopt;
    };
    auto materializer = [](const hdar::CapsuleManifest&,
                           const std::string&) -> std::pair<hdar::RuntimeRecord, std::optional<std::string>> {
        hdar::RuntimeRecord r;
        r.exists = false;
        return {r, "not implemented"};
    };

    hdar::SshGateway gateway(lm, resolver, materializer);

    hdar::AgentRegistration reg;
    reg.ssh_user = "tamper-test-user";
    reg.agent_id = "agent-tamper-001";
    reg.agent_name = "Tamper Test Agent";
    reg.default_capsule_hash = "hash-tamper-123";
    reg.capabilities_json = "[]";
    reg.authorized_public_key = "ssh-ed25519 AAAA... tamper";

    gateway.register_agent(reg);

    std::string config_path = dir + "/gateway_config.json";
    gateway.save_config(config_path);

    std::string original_hash = hdar::SshGateway::compute_config_hash(config_path);

    // Tamper with the config file
    std::ofstream f(config_path, std::ios::app);
    f << "TAMPERED";
    f.close();

    // Verify integrity should fail
    ASSERT(!hdar::SshGateway::verify_config_integrity(config_path, original_hash));

    // Hash should be different
    std::string tampered_hash = hdar::SshGateway::compute_config_hash(config_path);
    ASSERT(tampered_hash != original_hash);

    fs::remove_all(dir);
}

// ── Main ──────────────────────────────────────────────────────

int main() {
    std::cout << "=== HDAR C++ Test Suite ===\n\n";

    std::cout << "Crypto:\n";
    RUN(test_ed25519_sign_verify);
    RUN(test_key_roundtrip);
    RUN(test_canonical_json);
    RUN(test_sha256);
    RUN(test_host_key_pair);

    std::cout << "\nStore:\n";
    RUN(test_content_store);
    RUN(test_workspace_ingest_restore);

    std::cout << "\nIdentity:\n";
    RUN(test_agent_identity);
    RUN(test_lineage_epoch);

    std::cout << "\nReceipts:\n";
    RUN(test_receipt_chain);

    std::cout << "\nCapabilities:\n";
    RUN(test_capability_non_expansion);
    RUN(test_capability_expansion_detected);
    RUN(test_capability_compile_attenuation);

    std::cout << "\nLeases:\n";
    RUN(test_lease_acquire_release);
    RUN(test_lease_stale_rejected);

    std::cout << "\nState Machine:\n";
    RUN(test_state_machine_transitions);

    std::cout << "\nProviders:\n";
    RUN(test_unsafe_host_provider);

    std::cout << "\nRestoration:\n";
    RUN(test_restoration_exact);
    RUN(test_restoration_degraded);

    std::cout << "\nEvidence:\n";
    RUN(test_execution_receipt);
    RUN(test_termination_receipt);
    RUN(test_host_attestation);

    std::cout << "\nOffline Verifier:\n";
    RUN(test_offline_verifier_capabilities);

    std::cout << "\nContinuity Loop:\n";
    RUN(test_continuity_loop);

    std::cout << "\nReliability Harness:\n";
    RUN(test_reliability_100_cycles);
    RUN(test_reliability_failure_injection);

    std::cout << "\nFencing Validation:\n";
    RUN(test_fencing_all_effect_states);
    RUN(test_concurrent_acquire);
    RUN(test_stale_holder_cannot_collapse);

    std::cout << "\nRemote SSH Provider:\n";
    RUN(test_remote_ssh_provider);

    std::cout << "\nSSH Gateway Config:\n";
    RUN(test_gateway_config_load_save);
    RUN(test_gateway_config_tamper_detection);

    std::cout << "\n=== Results: " << tests_passed << " passed, "
              << tests_failed << " failed ===\n";
    return tests_failed > 0 ? 1 : 0;
}
