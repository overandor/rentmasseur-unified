// hdar_continuity.cpp — Continuity loop orchestrator (pure C++).

#include "hdar_continuity.h"
#include <sstream>
#include <chrono>
#include <random>

namespace hdar {

static double now_seconds() {
    auto now = std::chrono::system_clock::now();
    return std::chrono::duration<double>(now.time_since_epoch()).count();
}

// ─── WitnessReceipt ────────────────────────────────────────────────────

std::string WitnessReceipt::canonical_form() const {
    std::ostringstream ss;
    ss << "{"
       << "\"capsule_hash\":\"" << capsule_hash << "\""
       << ",\"host_id\":\"" << host_id << "\""
       << ",\"runtime_id\":\"" << runtime_id << "\""
       << ",\"host_public_key\":\"" << host_public_key << "\""
       << ",\"operations\":" << operations_json
       << ",\"test_results\":" << test_results_json
       << ",\"timestamp\":" << timestamp
       << ",\"test_success\":" << (test_success ? "true" : "false")
       << "}";
    return ss.str();
}

std::string WitnessReceipt::to_json() const {
    std::ostringstream ss;
    ss << "{"
       << "\"capsule_hash\":\"" << capsule_hash << "\""
       << ",\"host_id\":\"" << host_id << "\""
       << ",\"runtime_id\":\"" << runtime_id << "\""
       << ",\"host_public_key\":\"" << host_public_key << "\""
       << ",\"signature_hex\":\"" << signature_hex << "\""
       << ",\"operations\":" << operations_json
       << ",\"test_results\":" << test_results_json
       << ",\"timestamp\":" << timestamp
       << ",\"test_success\":" << (test_success ? "true" : "false")
       << "}";
    return ss.str();
}

WitnessReceipt WitnessReceipt::from_json(const std::string& json) {
    WitnessReceipt w;
    auto find_str = [&](const std::string& key) -> std::string {
        size_t pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return "";
        size_t s = json.find("\"", pos + key.size() + 2) + 1;
        size_t e = json.find("\"", s);
        return json.substr(s, e - s);
    };
    auto find_bool = [&](const std::string& key) -> bool {
        size_t pos = json.find("\"" + key + "\"");
        if (pos == std::string::npos) return false;
        size_t s = json.find(":", pos + key.size() + 2) + 1;
        return json.substr(s, 4).find("true") != std::string::npos;
    };

    w.capsule_hash = find_str("capsule_hash");
    w.host_id = find_str("host_id");
    w.runtime_id = find_str("runtime_id");
    w.host_public_key = find_str("host_public_key");
    w.signature_hex = find_str("signature_hex");
    w.test_success = find_bool("test_success");
    return w;
}

// ─── ContinuityVerifier ────────────────────────────────────────────────

ContinuityVerifier::ContinuityVerifier(const Ed25519PublicKey& owner_pub)
    : owner_pub_(owner_pub) {}

VerificationResult ContinuityVerifier::verify_full_chain(
    const std::vector<Capsule>& capsules,
    const std::vector<FencingInvalidation>& invalidations,
    const std::vector<std::pair<WitnessReceipt, Ed25519PublicKey>>& witnesses
) {
    VerificationResult result;
    result.valid = true;
    result.checks_passed = 0;
    result.checks_failed = 0;

    if (capsules.empty()) {
        result.problems.push_back("empty capsule chain");
        result.valid = false;
        result.checks_failed++;
        return result;
    }

    for (size_t i = 0; i < capsules.size(); i++) {
        const auto& cap = capsules[i];

        std::string computed = sha256_hex(cap.canonical_form());
        if (computed != cap.manifest_hash) {
            result.problems.push_back("capsule " + std::to_string(i) + " manifest hash mismatch");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;

        if (!ed25519_verify_hex(owner_pub_, cap.canonical_form(), cap.owner_signature)) {
            result.problems.push_back("capsule " + std::to_string(i) + " owner signature invalid");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;

        if (cap.epoch < 0) {
            result.problems.push_back("capsule " + std::to_string(i) + " negative epoch");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;

        if (i > 0 && cap.parent_hash != capsules[i-1].manifest_hash) {
            result.problems.push_back("capsule " + std::to_string(i) + " parent hash mismatch");
            result.valid = false;
            result.checks_failed++;
        } else if (i > 0) result.checks_passed++;
    }

    for (size_t i = 0; i < invalidations.size(); i++) {
        const auto& inv = invalidations[i];
        if (inv.fencing_token.empty()) {
            result.problems.push_back("invalidation " + std::to_string(i) + " empty token");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;

        if (inv.lease_generation < 0) {
            result.problems.push_back("invalidation " + std::to_string(i) + " negative generation");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;
    }

    for (size_t i = 0; i < witnesses.size(); i++) {
        const auto& [witness, host_pub] = witnesses[i];
        auto sig = from_hex(witness.signature_hex);
        auto canonical = witness.canonical_form();
        if (!ed25519_verify(host_pub, (const uint8_t*)canonical.data(), canonical.size(), sig.data(), sig.size())) {
            result.problems.push_back("witness " + std::to_string(i) + " host signature invalid");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;

        if (witness.capsule_hash.empty()) {
            result.problems.push_back("witness " + std::to_string(i) + " empty capsule hash");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;

        if (!witness.test_success) {
            result.problems.push_back("witness " + std::to_string(i) + " test not successful");
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;
    }


    for (size_t i = 1; i < capsules.size(); i++) {
        if (capsules[i].epoch <= capsules[i-1].epoch) {
            result.problems.push_back("epoch rollback at capsule " + std::to_string(i));
            result.valid = false;
            result.checks_failed++;
        } else result.checks_passed++;
    }


    return result;
}

// ─── ContinuityLoop ────────────────────────────────────────────────────

ContinuityLoop::ContinuityLoop(
    const Ed25519KeyPair& owner_key,
    ContentStore& store,
    LeaseManager& lease_mgr,
    const std::string& sandbox_dir
) : owner_key_(owner_key), store_(store), lease_mgr_(lease_mgr), sandbox_dir_(sandbox_dir) {}

std::pair<Capsule, std::string> ContinuityLoop::seal_on_host_a(
    const std::string& workspace_dir,
    const std::string& agent_id,
    const std::string& agent_name,
    int epoch,
    const std::string& parent_hash,
    const std::string& objective,
    const std::string& continuation_point,
    const std::string& capabilities_json,
    const std::string& fencing_token
) {
    Capsule cap;
    cap.epoch = epoch;
    cap.agent_id = agent_id;
    cap.agent_name = agent_name;
    cap.parent_hash = parent_hash;
    cap.objective = objective;
    cap.continuation_point = continuation_point;
    cap.capabilities_json = capabilities_json;
    cap.workspace = store_.store_workspace(workspace_dir);
    cap.compute_hash();

    auto sig = ed25519_sign(owner_key_, cap.canonical_form());
    cap.owner_signature = to_hex(sig);
    cap.owner_public_key = owner_key_.public_key_hex();

    return {cap, ""};
}

std::pair<FencingInvalidation, std::string> ContinuityLoop::destroy_host_a(
    AppleContainerProvider& provider,
    const std::string& runtime_id,
    const std::string& agent_id,
    int64_t lease_generation,
    const std::string& fencing_token
) {
    provider.destroy(runtime_id);
    std::string err = lease_mgr_.invalidate(agent_id, fencing_token);

    FencingInvalidation inv;
    inv.agent_id = agent_id;
    inv.lease_generation = lease_generation;
    inv.fencing_token = fencing_token;
    inv.holder_id = "host-A";
    inv.runtime_id = runtime_id;
    inv.invalidated_at = now_seconds();
    inv.reason = "runtime destroyed";

    return {inv, err};
}

ContinuityLoop::RestorationResult ContinuityLoop::restore_on_host_b(
    const Capsule& capsule,
    AppleContainerProvider& provider,
    const Ed25519KeyPair& host_key,
    const std::string& workspace_dest,
    const std::string& holder_id
) {
    RestorationResult result;
    result.restored = false;

    Ed25519PublicKey owner_pub = Ed25519PublicKey::from_hex(capsule.owner_public_key);
    if (!ed25519_verify_hex(owner_pub, capsule.canonical_form(), capsule.owner_signature)) {
        result.reason = "owner signature verification failed";
        return result;
    }

    if (!store_.restore_workspace(capsule.workspace, workspace_dest)) {
        result.reason = "workspace restoration failed";
        return result;
    }

    auto [lease, err] = lease_mgr_.acquire(
        capsule.agent_id, capsule.manifest_hash, 0, holder_id, "runtime-B"
    );
    if (!lease) {
        result.reason = "lease acquisition failed: " + err;
        return result;
    }

    result.restored = true;
    result.fencing_token = lease->fencing_token;
    result.lease_generation = lease->lease_generation;

    // Generate runtime ID
    std::random_device rd;
    char buf[48];
    snprintf(buf, sizeof(buf), "hdar-restore-%08x", rd());
    result.runtime_id = buf;

    return result;
}

WitnessReceipt ContinuityLoop::host_b_witness(
    const Capsule& capsule,
    const Ed25519KeyPair& host_key,
    const std::string& runtime_id,
    const std::string& operations_json,
    const std::string& test_results_json,
    bool test_success
) {
    WitnessReceipt w;
    w.capsule_hash = capsule.manifest_hash;
    w.host_id = "host-B";
    w.runtime_id = runtime_id;
    w.host_public_key = host_key.public_key_hex();
    w.operations_json = operations_json;
    w.test_results_json = test_results_json;
    w.test_success = test_success;
    w.timestamp = now_seconds();

    auto sig = ed25519_sign(host_key, w.canonical_form());
    w.signature_hex = to_hex(sig);

    return w;
}

std::pair<Capsule, std::string> ContinuityLoop::owner_reseal(
    const Capsule& parent,
    const WitnessReceipt& witness,
    const std::string& workspace_dir,
    int new_epoch,
    const std::string& objective,
    const std::string& continuation_point,
    const Ed25519PublicKey& host_pub
) {
    Capsule cap;
    cap.epoch = new_epoch;
    cap.agent_id = parent.agent_id;
    cap.agent_name = parent.agent_name;
    cap.parent_hash = parent.manifest_hash;
    cap.objective = objective;
    cap.continuation_point = continuation_point;
    cap.capabilities_json = parent.capabilities_json;
    cap.workspace = store_.store_workspace(workspace_dir);
    cap.receipt_chain = parent.receipt_chain;
    cap.receipt_chain.push_back(witness.to_json());
    cap.compute_hash();

    auto sig = ed25519_sign(owner_key_, cap.canonical_form());
    cap.owner_signature = to_hex(sig);
    cap.owner_public_key = owner_key_.public_key_hex();

    return {cap, ""};
}

} // namespace hdar
