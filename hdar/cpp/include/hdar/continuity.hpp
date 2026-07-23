#pragma once

#include "hdar/crypto.hpp"
#include "hdar/identity.hpp"
#include "hdar/seal.hpp"
#include "hdar/restore.hpp"
#include "hdar/lease.hpp"
#include "hdar/capabilities.hpp"
#include "hdar/execution_receipt.hpp"
#include "hdar/termination_receipt.hpp"
#include "hdar/host_attestation.hpp"
#include "hdar/offline_verify.hpp"
#include "hdar/provider_base.hpp"
#include "hdar/restoration_contract.hpp"
#include <string>
#include <optional>
#include <vector>

namespace hdar {

struct FencingInvalidation {
    std::string agent_id;
    std::string invalidated_token;
    int generation = 0;
    double timestamp = 0.0;
    std::string reason;

    JsonValue to_json() const;
};

struct ContinuityCapsule {
    CapsuleManifest manifest;
    std::string capsule_path;
    std::string manifest_hash;
};

struct ContinuityResult {
    bool success = false;
    int assertions_passed = 0;
    int assertions_failed = 0;
    std::vector<std::string> assertion_details;
    VerificationResult verification;
    ExecutionReceipt exec_receipt;
    TerminationReceipt term_receipt;
    RestorationReport restoration_report;
    CapsuleManifest source_manifest;
    CapsuleManifest dest_manifest;
    std::string error;

    JsonValue to_json() const;
};

class ContinuityLoop {
public:
    ContinuityLoop(OwnerKeyPair& owner_keys,
                   ContentStore& store,
                   ProviderBase* provider_a,
                   ProviderBase* provider_b);

    ContinuityResult run(
        const std::string& workspace_dir,
        const std::string& objective,
        const std::map<std::string, std::string>& dest_policy,
        const std::string& task_command = "echo 'task executed' > task_output.txt");

private:
    OwnerKeyPair& owner_keys_;
    ContentStore& store_;
    ProviderBase* provider_a_;
    ProviderBase* provider_b_;
    LeaseManager lease_manager_;

    void assert_true(ContinuityResult& result, bool condition, const std::string& description);
};

} // namespace hdar
