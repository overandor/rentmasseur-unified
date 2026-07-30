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

#include <iostream>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

static int passed = 0;
static int failed = 0;

#define CHECK(cond, msg) do { \
    if (cond) { ++passed; std::cout << "  PASS: " << msg << "\n"; } \
    else { ++failed; std::cout << "  FAIL: " << msg << "\n"; } \
} while(0)

int main() {
    std::cout << "=== HDAR C++ Demo ===\n\n";

    // 1. Crypto
    std::cout << "[1] Cryptography\n";
    auto owner = hdar::OwnerKeyPair::generate();
    CHECK(!owner.fingerprint().empty(), "owner key pair generated with fingerprint");
    CHECK(owner.fingerprint().size() == 16, "fingerprint is 16 hex chars");

    auto owner2 = hdar::OwnerKeyPair::from_private_hex(owner.private_key_hex());
    CHECK(owner2.fingerprint() == owner.fingerprint(), "key round-trips through hex");

    hdar::JsonValue test_obj = hdar::JsonValue::object();
    test_obj["b"] = hdar::JsonValue::string("second");
    test_obj["a"] = hdar::JsonValue::string("first");
    std::string canon = hdar::canonical_json(test_obj);
    CHECK(canon == R"({"a":"first","b":"second"})", "canonical JSON sorts keys");

    std::string sig = owner.sign_json(test_obj);
    CHECK(owner.public_key.verify_json(test_obj, sig), "Ed25519 sign/verify round-trip");
    CHECK(!owner.public_key.verify_json(test_obj, "deadbeef"), "invalid signature rejected");

    // 2. Content store
    std::cout << "\n[2] Content Store\n";
    std::string test_dir = "/tmp/hdar-demo-" + hdar::generate_uuid_hex().substr(0, 8);
    hdar::ContentStore store(test_dir + "/store");

    std::string data = "hello hdar";
    std::string hash = store.ingest_bytes(std::vector<uint8_t>(data.begin(), data.end()));
    CHECK(hash.size() == 64, "content hash is SHA-256 (64 hex chars)");

    auto retrieved = store.retrieve(hash);
    CHECK(std::string(retrieved.begin(), retrieved.end()) == data, "content retrieved matches");

    // 3. Identity & Lineage
    std::cout << "\n[3] Identity & Lineage\n";
    auto identity = hdar::AgentIdentity::create("test-agent");
    CHECK(!identity.agent_id.empty(), "agent identity created");
    CHECK(identity.fingerprint().size() == 16, "agent has fingerprint");

    auto epoch0 = hdar::LineageEpoch::genesis(identity.agent_id);
    auto epoch1 = hdar::LineageEpoch::child(epoch0);
    CHECK(epoch1.sequence == 1, "epoch 1 is child of epoch 0");
    CHECK(epoch1.parent_epoch.value() == epoch0.epoch_id, "epoch 1 parent links to epoch 0");

    // 4. Receipt chain
    std::cout << "\n[4] Receipt Chain\n";
    hdar::ReceiptChain chain(identity.agent_id, epoch0.epoch_id, identity.signing_key);
    chain.append("SEAL", "capsule_sealed");
    chain.append("DESTROY", "runtime_destroyed");
    CHECK(chain.size() == 2, "receipt chain has 2 entries");
    CHECK(chain.verify(identity.public_key()), "receipt chain verifies");

    // 5. Capabilities
    std::cout << "\n[5] Capability Compiler\n";
    std::vector<hdar::Capability> caps = {
        {"filesystem.read", "/workspace", true, {}},
        {"filesystem.write", "/workspace", true, {}},
        {"network.egress", "api.example.com", true, {}},
        {"budget.spend", "$100", true, {}},
    };
    std::map<std::string, std::string> policy = {
        {"filesystem.root", "/workspace"},
        {"network.allowlist", "api.example.com"},
        {"budget.max", "$50"},
    };
    hdar::CapabilityCompiler compiler;
    auto [dest_caps, rejections] = compiler.compile(caps, policy);
    CHECK(!dest_caps.empty(), "capabilities compiled");
    auto [non_exp, violations] = compiler.verify_non_expansion(caps, dest_caps);
    CHECK(non_exp, "non-expansion invariant holds");

    // 6. Lease manager
    std::cout << "\n[6] Lease Manager\n";
    hdar::LeaseManager lm(test_dir + "/leases.db");
    auto [lease, err] = lm.acquire("test-agent", "hash123", 0, "holder1", "runtime1");
    CHECK(lease.has_value(), "lease acquired");
    CHECK(lm.validate_token("test-agent", lease->fencing_token), "fencing token valid");
    CHECK(lm.reject_stale("test-agent", "old-token"), "stale token rejected");
    CHECK(lm.release("test-agent", lease->fencing_token), "lease released");

    // 7. State machine
    std::cout << "\n[7] State Machine\n";
    hdar::LifecycleStateMachine sm("test-agent");
    CHECK(sm.is_dormant(), "starts DORMANT");
    sm.transition(hdar::AgentState::ACQUIRING_LEASE);
    sm.transition(hdar::AgentState::MATERIALIZING);
    sm.transition(hdar::AgentState::VERIFYING_INPUT);
    sm.transition(hdar::AgentState::RUNNING);
    CHECK(sm.is_running(), "reached RUNNING");
    sm.transition(hdar::AgentState::QUIESCING);
    CHECK(sm.can_seal(), "can seal from QUIESCING");

    // 8. Unsafe host provider
    std::cout << "\n[8] Unsafe Host Provider\n";
    std::string ws_dir = test_dir + "/workspace";
    fs::create_directories(ws_dir);
    std::ofstream(ws_dir + "/test.txt") << "test content";

    hdar::UnsafeHostProvider provider(test_dir + "/sandbox");
    auto runtime = provider.materialize("rt1", ws_dir);
    CHECK(runtime.exists, "runtime materialized");
    auto exec = provider.execute("rt1", "test", "echo hello");
    CHECK(exec.success, "command executed");
    auto stopped = provider.stop("rt1");
    auto destroyed = provider.destroy("rt1");
    CHECK(!destroyed.exists, "runtime destroyed");
    CHECK(provider.verify_destruction("rt1"), "destruction verified");

    // 9. Restoration contract
    std::cout << "\n[9] Restoration Contract\n";
    hdar::RestorationContract rc;
    auto report = rc.classify("arm64", "linux", "none", "arm64", "linux", "none",
                               true, true, true, {});
    CHECK(report.restoration_class == hdar::RestorationClass::EXACT, "same arch = exact restoration");

    auto report2 = rc.classify("arm64", "linux", "metal", "x86_64", "linux", "cuda",
                                false, true, true, {"gpu_passthrough"});
    CHECK(report2.restoration_class == hdar::RestorationClass::DEGRADED, "different arch + missing model = degraded");

    // 10. Offline verifier
    std::cout << "\n[10] Offline Verifier\n";
    hdar::OfflineVerifier verifier(owner.public_key);
    auto cap_result = verifier.verify_capability_continuity(caps, dest_caps);
    CHECK(cap_result.overall_pass, "capability continuity verifies");

    // Cleanup
    fs::remove_all(test_dir);

    std::cout << "\n=== Results: " << passed << " passed, " << failed << " failed ===\n";
    return failed > 0 ? 1 : 0;
}
