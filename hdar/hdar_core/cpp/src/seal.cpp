#include "hdar/seal.hpp"
#include "hdar/lease.hpp"

namespace hdar {

// ── CapsuleManifest ───────────────────────────────────────────

std::vector<uint8_t> CapsuleManifest::canonical_bytes() const {
    JsonValue d = to_json();
    // Remove signature, manifest_hash, sealed_at
    d.object_val.erase("signature");
    d.object_val.erase("manifest_hash");
    d.object_val.erase("sealed_at");
    return canonical_json_bytes(d);
}

std::string CapsuleManifest::compute_hash() const {
    return sha256_hex(canonical_bytes());
}

JsonValue CapsuleManifest::to_json() const {
    JsonValue v = JsonValue::object();
    v["agent_id"] = JsonValue::string(agent_id);
    v["agent_name"] = JsonValue::string(agent_name);
    v["epoch"] = epoch;
    if (parent_capsule_hash)
        v["parent_capsule_hash"] = JsonValue::string(*parent_capsule_hash);
    else
        v["parent_capsule_hash"] = JsonValue::null();
    v["model_digest"] = JsonValue::string(model_digest);
    v["tokenizer_digest"] = JsonValue::string(tokenizer_digest);
    v["inference_requirements"] = inference_requirements;
    v["objective"] = JsonValue::string(objective);
    v["continuation_point"] = JsonValue::string(continuation_point);
    v["working_summary"] = JsonValue::string(working_summary);
    if (workspace_manifest)
        v["workspace_manifest"] = *workspace_manifest;
    else
        v["workspace_manifest"] = JsonValue::null();
    v["capabilities"] = capabilities;
    v["capability_note"] = JsonValue::string(capability_note);
    v["secret_references"] = secret_references;
    v["pending_operations"] = pending_operations;
    v["runtime_compatibility"] = runtime_compatibility;
    v["restoration_contract"] = JsonValue::string(restoration_contract);
    v["receipts"] = receipts;
    v["manifest_hash"] = JsonValue::string(manifest_hash);
    v["signer_fingerprint"] = JsonValue::string(signer_fingerprint);
    v["signature"] = JsonValue::string(signature);
    v["sealed_at"] = JsonValue::number(sealed_at);
    return v;
}

CapsuleManifest CapsuleManifest::from_json(const JsonValue& d) {
    CapsuleManifest m;
    m.agent_id = d.get("agent_id").string_val;
    m.agent_name = d.get("agent_name").string_val;
    m.epoch = d.get("epoch");
    const auto& pch = d.get("parent_capsule_hash");
    if (pch.type == JsonValue::Type::String)
        m.parent_capsule_hash = pch.string_val;
    m.model_digest = d.get("model_digest").string_val;
    m.tokenizer_digest = d.get("tokenizer_digest").string_val;
    m.inference_requirements = d.get("inference_requirements");
    m.objective = d.get("objective").string_val;
    m.continuation_point = d.get("continuation_point").string_val;
    m.working_summary = d.get("working_summary").string_val;
    const auto& wm = d.get("workspace_manifest");
    if (wm.type == JsonValue::Type::Object)
        m.workspace_manifest = wm;
    m.capabilities = d.get("capabilities");
    m.capability_note = d.get("capability_note").string_val;
    m.secret_references = d.get("secret_references");
    m.pending_operations = d.get("pending_operations");
    m.runtime_compatibility = d.get("runtime_compatibility");
    m.restoration_contract = d.get("restoration_contract").string_val;
    if (m.restoration_contract.empty()) m.restoration_contract = "exact";
    m.receipts = d.get("receipts");
    m.manifest_hash = d.get("manifest_hash").string_val;
    m.signer_fingerprint = d.get("signer_fingerprint").string_val;
    m.signature = d.get("signature").string_val;
    m.sealed_at = d.get("sealed_at").double_val;
    return m;
}

// ── CapsuleSealer ─────────────────────────────────────────────

CapsuleSealer::CapsuleSealer(ContentStore& store, AgentIdentity& identity,
                             LeaseManager* lm)
    : store_(store), identity_(identity), lease_manager_(lm) {}

std::pair<CapsuleManifest, ReceiptChain> CapsuleSealer::seal(
    const std::string& workspace_dir,
    const LineageEpoch& epoch,
    const std::string& objective,
    const std::string& continuation_point,
    const std::string& working_summary,
    const JsonValue& capabilities,
    const std::string& capability_note,
    const std::optional<std::string>& parent_capsule_hash,
    const std::string& model_digest,
    const std::string& tokenizer_digest,
    const JsonValue& inference_requirements,
    const JsonValue& secret_references,
    const JsonValue& pending_operations,
    const JsonValue& runtime_compatibility,
    const std::string& fencing_token) {

    // 0. Validate fencing token if lease manager is present
    if (lease_manager_ && !fencing_token.empty()) {
        if (!lease_manager_->validate_token(identity_.agent_id, fencing_token)) {
            throw std::runtime_error(
                "stale or invalid fencing token — this runtime's lease generation "
                "is no longer authoritative; cannot seal capsule");
        }
    }

    // 1. Ingest workspace
    auto ws_manifest = store_.ingest_workspace(workspace_dir);

    // 2. Build receipt chain
    ReceiptChain chain(identity_.agent_id, epoch.epoch_id, identity_.signing_key);

    // 3. Append SEAL receipt
    JsonValue seal_payload = JsonValue::object();
    seal_payload["workspace_root_hash"] = JsonValue::string(ws_manifest.root_hash);
    seal_payload["file_count"] = JsonValue::integer(static_cast<int64_t>(ws_manifest.files.size()));
    seal_payload["total_size"] = JsonValue::integer(static_cast<int64_t>(ws_manifest.total_size));
    seal_payload["objective"] = JsonValue::string(objective);

    chain.append("SEAL", "capsule_sealed", seal_payload, ws_manifest.root_hash);

    // 4. Build manifest
    CapsuleManifest manifest;
    manifest.agent_id = identity_.agent_id;
    manifest.agent_name = identity_.name;
    manifest.epoch = epoch.to_json();
    manifest.parent_capsule_hash = parent_capsule_hash;
    manifest.model_digest = model_digest;
    manifest.tokenizer_digest = tokenizer_digest;
    manifest.inference_requirements = inference_requirements;
    manifest.objective = objective;
    manifest.continuation_point = continuation_point;
    manifest.working_summary = working_summary;
    manifest.workspace_manifest = ws_manifest.to_json();
    manifest.capabilities = capabilities;
    manifest.capability_note = capability_note;
    manifest.secret_references = secret_references;
    manifest.pending_operations = pending_operations;
    manifest.runtime_compatibility = runtime_compatibility;
    manifest.restoration_contract = "exact";
    manifest.receipts = chain.to_json_array();
    manifest.signer_fingerprint = identity_.fingerprint();
    manifest.sealed_at = epoch_seconds();

    // 5. Sign manifest
    manifest.manifest_hash = manifest.compute_hash();
    manifest.signature = identity_.sign_hex(manifest.canonical_bytes());

    return {manifest, chain};
}

void CapsuleSealer::write_capsule(const CapsuleManifest& manifest,
                                   const std::string& output_path) const {
    auto parent = std::filesystem::path(output_path).parent_path();
    if (!parent.empty())
        std::filesystem::create_directories(parent);
    write_string_to_file(output_path, canonical_json(manifest.to_json()));
}

bool CapsuleSealer::verify_manifest(const CapsuleManifest& manifest,
                                     const PublicKey& pk) const {
    return pk.verify_hex(manifest.canonical_bytes(), manifest.signature);
}

bool CapsuleSealer::verify_capsule_file(const std::string& capsule_path,
                                         const PublicKey& pk) const {
    std::string content = read_file_to_string(capsule_path);
    if (content.empty())
        return false;
    try {
        JsonValue json = parse_json(content);
        auto manifest = CapsuleManifest::from_json(json);
        return verify_manifest(manifest, pk);
    } catch (const std::exception&) {
        return false;
    }
}

} // namespace hdar
