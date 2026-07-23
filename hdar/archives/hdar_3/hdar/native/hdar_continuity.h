// hdar_continuity.h — Continuity loop orchestrator (native C++).

#ifndef HDAR_CONTINUITY_H
#define HDAR_CONTINUITY_H

#include <string>
#include <vector>
#include <memory>
#include "hdar_crypto.h"
#include "hdar_store.h"
#include "hdar_lease.h"
#include "hdar_provider.h"

namespace hdar {

/// A witness receipt signed by a host's ephemeral key.
struct WitnessReceipt {
    std::string capsule_hash;    // Input capsule
    std::string host_id;
    std::string runtime_id;
    std::string host_public_key; // Ephemeral key hex
    std::string signature_hex;   // Ed25519 signature
    std::string operations_json;
    std::string test_results_json;
    double timestamp;
    bool test_success;

    std::string canonical_form() const;
    std::string to_json() const;
    static WitnessReceipt from_json(const std::string& json);
};

/// Offline verifier — checks full chain with only owner's public key.
struct VerificationResult {
    bool valid;
    int checks_passed;
    int checks_failed;
    std::vector<std::string> problems;
};

class ContinuityVerifier {
public:
    explicit ContinuityVerifier(const Ed25519PublicKey& owner_pub);

    VerificationResult verify_full_chain(
        const std::vector<Capsule>& capsules,
        const std::vector<FencingInvalidation>& invalidations,
        const std::vector<std::pair<WitnessReceipt, Ed25519PublicKey>>& witnesses
    );

private:
    Ed25519PublicKey owner_pub_;
};

/// The continuity loop orchestrator.
class ContinuityLoop {
public:
    ContinuityLoop(
        const Ed25519KeyPair& owner_key,
        ContentStore& store,
        LeaseManager& lease_mgr,
        const std::string& sandbox_dir
    );

    /// Seal a capsule on Host A.
    std::pair<Capsule, std::string> seal_on_host_a(
        const std::string& workspace_dir,
        const std::string& agent_id,
        const std::string& agent_name,
        int epoch,
        const std::string& parent_hash,
        const std::string& objective,
        const std::string& continuation_point,
        const std::string& capabilities_json,
        const std::string& fencing_token
    );

    /// Destroy Host A and invalidate fencing.
    std::pair<FencingInvalidation, std::string> destroy_host_a(
        AppleContainerProvider& provider,
        const std::string& runtime_id,
        const std::string& agent_id,
        int64_t lease_generation,
        const std::string& fencing_token
    );

    /// Restore capsule on Host B.
    struct RestorationResult {
        bool restored;
        std::string runtime_id;
        std::string reason;
        std::string fencing_token;
        int64_t lease_generation;
    };

    RestorationResult restore_on_host_b(
        const Capsule& capsule,
        AppleContainerProvider& provider,
        const Ed25519KeyPair& host_key,
        const std::string& workspace_dest,
        const std::string& holder_id
    );

    /// Host B signs witness receipt.
    WitnessReceipt host_b_witness(
        const Capsule& capsule,
        const Ed25519KeyPair& host_key,
        const std::string& runtime_id,
        const std::string& operations_json,
        const std::string& test_results_json,
        bool test_success
    );

    /// Owner reseals capsule with advanced epoch.
    std::pair<Capsule, std::string> owner_reseal(
        const Capsule& parent,
        const WitnessReceipt& witness,
        const std::string& workspace_dir,
        int new_epoch,
        const std::string& objective,
        const std::string& continuation_point,
        const Ed25519PublicKey& host_pub
    );

private:
    Ed25519KeyPair owner_key_;
    ContentStore& store_;
    LeaseManager& lease_mgr_;
    std::string sandbox_dir_;
};

} // namespace hdar

#endif // HDAR_CONTINUITY_H
