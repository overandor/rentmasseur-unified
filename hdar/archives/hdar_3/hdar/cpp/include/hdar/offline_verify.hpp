#pragma once

#include "hdar/crypto.hpp"
#include "hdar/seal.hpp"
#include "hdar/receipt.hpp"
#include "hdar/execution_receipt.hpp"
#include "hdar/termination_receipt.hpp"
#include "hdar/host_attestation.hpp"
#include "hdar/capabilities.hpp"
#include <string>
#include <vector>

namespace hdar {

struct VerificationResult {
    int passed = 0;
    int failed = 0;
    std::vector<std::string> checks_passed;
    std::vector<std::string> checks_failed;
    bool overall_pass = false;

    void ok(const std::string& check);
    void bad(const std::string& check);

    JsonValue to_json() const;
};

class OfflineVerifier {
public:
    explicit OfflineVerifier(const PublicKey& owner_public_key);

    VerificationResult verify_capsule(const CapsuleManifest& manifest);
    VerificationResult verify_receipt_chain(const std::vector<Receipt>& receipts);
    VerificationResult verify_execution_receipt(const ExecutionReceipt& er);
    VerificationResult verify_termination_receipt(const TerminationReceipt& tr);
    VerificationResult verify_host_attestation(const HostAttestation& ha);
    VerificationResult verify_lineage(const std::vector<LineageEpoch>& epochs);
    VerificationResult verify_capability_continuity(
        const std::vector<Capability>& source_caps,
        const std::vector<Capability>& dest_caps);
    VerificationResult verify_quiescence(const JsonValue& quiescence_report);

    VerificationResult verify_full_chain(
        const CapsuleManifest& source_manifest,
        const ExecutionReceipt& exec_receipt,
        const TerminationReceipt& term_receipt,
        const CapsuleManifest& dest_manifest,
        const std::vector<Capability>& source_caps,
        const std::vector<Capability>& dest_caps);

private:
    PublicKey owner_pk_;
};

} // namespace hdar
