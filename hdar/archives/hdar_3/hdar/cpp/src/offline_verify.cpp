#include "hdar/offline_verify.hpp"
#include "hdar/identity.hpp"

namespace hdar {

void VerificationResult::ok(const std::string& check) {
    ++passed;
    checks_passed.push_back(check);
}

void VerificationResult::bad(const std::string& check) {
    ++failed;
    checks_failed.push_back(check);
}

JsonValue VerificationResult::to_json() const {
    JsonValue v = JsonValue::object();
    v["passed"] = JsonValue::integer(passed);
    v["failed"] = JsonValue::integer(failed);
    v["overall_pass"] = JsonValue::boolean(failed == 0);

    auto str_arr = [](const std::vector<std::string>& vec) {
        JsonValue a = JsonValue::array();
        for (const auto& s : vec) a.push_back(JsonValue::string(s));
        return a;
    };
    v["checks_passed"] = str_arr(checks_passed);
    v["checks_failed"] = str_arr(checks_failed);
    return v;
}

OfflineVerifier::OfflineVerifier(const PublicKey& owner_pk)
    : owner_pk_(owner_pk) {}

VerificationResult OfflineVerifier::verify_capsule(const CapsuleManifest& manifest) {
    VerificationResult r;

    // 1. Manifest hash
    std::string expected_hash = manifest.compute_hash();
    if (expected_hash == manifest.manifest_hash)
        r.ok("manifest hash");
    else
        r.bad("manifest hash mismatch — manifest was modified");

    // 2. Manifest signature
    if (owner_pk_.verify_hex(manifest.canonical_bytes(), manifest.signature))
        r.ok("manifest signature");
    else
        r.bad("manifest signature invalid");

    // 3. Signer fingerprint
    std::string expected_fp = owner_pk_.fingerprint();
    if (manifest.signer_fingerprint == expected_fp)
        r.ok("signer fingerprint");
    else
        r.bad("signer fingerprint mismatch");

    // 4. Receipt chain
    if (manifest.receipts.type == JsonValue::Type::Array && !manifest.receipts.array_val.empty()) {
        std::optional<std::string> prev_hash;
        bool chain_ok = true;
        for (const auto& rj : manifest.receipts.array_val) {
            Receipt rec = Receipt::from_json(rj);
            if (rec.prior_receipt_hash != prev_hash) { chain_ok = false; break; }
            if (!rec.verify(owner_pk_)) { chain_ok = false; break; }
            prev_hash = rec.receipt_hash;
        }
        if (chain_ok)
            r.ok("receipt chain");
        else
            r.bad("receipt chain verification failed");
    } else {
        r.bad("no receipts in capsule");
    }

    r.overall_pass = (r.failed == 0);
    return r;
}

VerificationResult OfflineVerifier::verify_receipt_chain(const std::vector<Receipt>& receipts) {
    VerificationResult r;
    std::optional<std::string> prev_hash;
    for (const auto& rec : receipts) {
        if (rec.prior_receipt_hash != prev_hash) {
            r.bad("chain linkage broken at receipt " + rec.receipt_hash);
            r.overall_pass = false;
            return r;
        }
        if (!rec.verify(owner_pk_)) {
            r.bad("signature verification failed at receipt " + rec.receipt_hash);
            r.overall_pass = false;
            return r;
        }
        prev_hash = rec.receipt_hash;
    }
    r.ok("receipt chain integrity (" + std::to_string(receipts.size()) + " receipts)");
    r.overall_pass = true;
    return r;
}

VerificationResult OfflineVerifier::verify_execution_receipt(const ExecutionReceipt& er) {
    VerificationResult r;

    // Verify with host public key
    PublicKey host_pk = PublicKey::from_hex(er.host_public_key_hex);

    if (er.verify(host_pk))
        r.ok("execution receipt signature");
    else
        r.bad("execution receipt signature invalid");

    if (!er.host_fingerprint.empty() && er.host_fingerprint == host_pk.fingerprint())
        r.ok("host fingerprint matches public key");
    else
        r.bad("host fingerprint mismatch");

    // Verify host is not the owner
    if (host_pk.fingerprint() != owner_pk_.fingerprint())
        r.ok("host key is not owner key (authority boundary)");
    else
        r.bad("CRITICAL: host key matches owner key — authority boundary violated");

    r.overall_pass = (r.failed == 0);
    return r;
}

VerificationResult OfflineVerifier::verify_termination_receipt(const TerminationReceipt& tr) {
    VerificationResult r;

    // Termination receipts are signed by the owner (or host, depending on design)
    if (tr.verify(owner_pk_))
        r.ok("termination receipt signature");
    else
        r.bad("termination receipt signature invalid");

    if (tr.inspection && !tr.inspection->get("exists").bool_val)
        r.ok("post-delete inspection confirms runtime absent");
    else
        r.bad("post-delete inspection does not confirm absence");

    r.overall_pass = (r.failed == 0);
    return r;
}

VerificationResult OfflineVerifier::verify_host_attestation(const HostAttestation& ha) {
    VerificationResult r;

    PublicKey host_pk = PublicKey::from_hex(ha.host_public_key_hex);

    if (ha.verify(host_pk))
        r.ok("host attestation signature");
    else
        r.bad("host attestation signature invalid");

    if (ha.host_fingerprint == host_pk.fingerprint())
        r.ok("host fingerprint matches");
    else
        r.bad("host fingerprint mismatch");

    if (host_pk.fingerprint() != owner_pk_.fingerprint())
        r.ok("attestation key is not owner key");
    else
        r.bad("CRITICAL: attestation key matches owner key");

    r.overall_pass = (r.failed == 0);
    return r;
}

VerificationResult OfflineVerifier::verify_lineage(const std::vector<LineageEpoch>& epochs) {
    VerificationResult r;

    for (size_t i = 0; i < epochs.size(); ++i) {
        if (epochs[i].sequence != static_cast<int>(i)) {
            r.bad("epoch sequence gap at index " + std::to_string(i));
            r.overall_pass = false;
            return r;
        }
        if (i > 0) {
            if (!epochs[i].parent_epoch ||
                *epochs[i].parent_epoch != epochs[i-1].epoch_id) {
                r.bad("lineage parent hash mismatch at epoch " + std::to_string(i));
                r.overall_pass = false;
                return r;
            }
        }
    }

    r.ok("lineage chain (" + std::to_string(epochs.size()) + " epochs)");
    r.overall_pass = true;
    return r;
}

VerificationResult OfflineVerifier::verify_capability_continuity(
    const std::vector<Capability>& source_caps,
    const std::vector<Capability>& dest_caps) {

    VerificationResult r;
    CapabilityCompiler compiler;
    auto [ok, violations] = compiler.verify_non_expansion(source_caps, dest_caps);

    if (ok) {
        r.ok("capability non-expansion invariant");
    } else {
        for (const auto& v : violations)
            r.bad(v);
    }

    r.overall_pass = (r.failed == 0);
    return r;
}

VerificationResult OfflineVerifier::verify_quiescence(const JsonValue& report) {
    VerificationResult r;

    if (report.get("quiescent").bool_val)
        r.ok("semantic quiescence");
    else
        r.bad("blocking effects prevent quiescence");

    r.overall_pass = (r.failed == 0);
    return r;
}

VerificationResult OfflineVerifier::verify_full_chain(
    const CapsuleManifest& source_manifest,
    const ExecutionReceipt& exec_receipt,
    const TerminationReceipt& term_receipt,
    const CapsuleManifest& dest_manifest,
    const std::vector<Capability>& source_caps,
    const std::vector<Capability>& dest_caps) {

    VerificationResult r;

    // Source capsule
    auto src_result = verify_capsule(source_manifest);
    r.passed += src_result.passed;
    r.failed += src_result.failed;
    for (const auto& c : src_result.checks_passed) r.checks_passed.push_back("source: " + c);
    for (const auto& c : src_result.checks_failed) r.checks_failed.push_back("source: " + c);

    // Execution receipt
    auto exec_result = verify_execution_receipt(exec_receipt);
    r.passed += exec_result.passed;
    r.failed += exec_result.failed;
    for (const auto& c : exec_result.checks_passed) r.checks_passed.push_back("exec: " + c);
    for (const auto& c : exec_result.checks_failed) r.checks_failed.push_back("exec: " + c);

    // Termination receipt
    auto term_result = verify_termination_receipt(term_receipt);
    r.passed += term_result.passed;
    r.failed += term_result.failed;
    for (const auto& c : term_result.checks_passed) r.checks_passed.push_back("term: " + c);
    for (const auto& c : term_result.checks_failed) r.checks_failed.push_back("term: " + c);

    // Destination capsule
    auto dst_result = verify_capsule(dest_manifest);
    r.passed += dst_result.passed;
    r.failed += dst_result.failed;
    for (const auto& c : dst_result.checks_passed) r.checks_passed.push_back("dest: " + c);
    for (const auto& c : dst_result.checks_failed) r.checks_failed.push_back("dest: " + c);

    // Capability continuity
    auto cap_result = verify_capability_continuity(source_caps, dest_caps);
    r.passed += cap_result.passed;
    r.failed += cap_result.failed;
    for (const auto& c : cap_result.checks_passed) r.checks_passed.push_back("cap: " + c);
    for (const auto& c : cap_result.checks_failed) r.checks_failed.push_back("cap: " + c);

    // Lineage advancement
    auto src_epoch = LineageEpoch::from_json(source_manifest.epoch);
    auto dst_epoch = LineageEpoch::from_json(dest_manifest.epoch);
    if (dst_epoch.sequence > src_epoch.sequence &&
        dst_epoch.parent_epoch == src_epoch.epoch_id)
        r.ok("lineage advancement");
    else
        r.bad("lineage advancement invalid");

    r.overall_pass = (r.failed == 0);
    return r;
}

} // namespace hdar
