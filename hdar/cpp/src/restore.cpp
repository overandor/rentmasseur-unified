#include "hdar/restore.hpp"

namespace hdar {

CapsuleRestorer::CapsuleRestorer(ContentStore& store) : store_(store) {}

CapsuleManifest CapsuleRestorer::load_capsule(const std::string& path) const {
    std::string content = read_file_to_string(path);
    JsonValue json = parse_json(content);
    return CapsuleManifest::from_json(json);
}

bool CapsuleRestorer::verify_manifest(const CapsuleManifest& manifest,
                                       const PublicKey& owner_pk) const {
    if (manifest.compute_hash() != manifest.manifest_hash)
        return false;
    return owner_pk.verify_hex(manifest.canonical_bytes(), manifest.signature);
}

bool CapsuleRestorer::verify_receipts(const CapsuleManifest& manifest,
                                       const PublicKey& owner_pk) const {
    if (manifest.receipts.type != JsonValue::Type::Array || manifest.receipts.array_val.empty())
        return false;

    std::optional<std::string> prev_hash;
    for (const auto& rj : manifest.receipts.array_val) {
        Receipt r = Receipt::from_json(rj);
        if (r.prior_receipt_hash != prev_hash)
            return false;
        if (!r.verify(owner_pk))
            return false;
        prev_hash = r.receipt_hash;
    }
    return true;
}

std::pair<WorkspaceManifest, bool> CapsuleRestorer::restore_workspace(
    const CapsuleManifest& manifest, const std::string& dest_dir) const {

    if (!manifest.workspace_manifest)
        throw std::runtime_error("capsule has no workspace manifest");

    auto ws_manifest = WorkspaceManifest::from_json(*manifest.workspace_manifest);
    store_.restore_workspace(ws_manifest, dest_dir);

    auto restored = store_.hash_workspace(dest_dir);
    bool hash_matches = (restored.root_hash == ws_manifest.root_hash);

    return {restored, hash_matches};
}

JsonValue CapsuleRestorer::restore(const std::string& capsule_path,
                                    const std::string& dest_dir,
                                    const PublicKey* owner_pk) const {
    auto manifest = load_capsule(capsule_path);

    bool sig_valid = false;
    bool receipts_valid = false;
    if (owner_pk) {
        sig_valid = verify_manifest(manifest, *owner_pk);
        receipts_valid = verify_receipts(manifest, *owner_pk);
    }

    auto [restored_manifest, hash_matches] = restore_workspace(manifest, dest_dir);

    JsonValue result = JsonValue::object();
    result["agent_id"] = JsonValue::string(manifest.agent_id);
    result["agent_name"] = JsonValue::string(manifest.agent_name);
    result["epoch"] = manifest.epoch;
    result["objective"] = JsonValue::string(manifest.objective);
    result["continuation_point"] = JsonValue::string(manifest.continuation_point);
    result["working_summary"] = JsonValue::string(manifest.working_summary);
    result["restoration_contract"] = JsonValue::string(manifest.restoration_contract);

    if (manifest.workspace_manifest) {
        result["workspace_root_hash"] = JsonValue::string(
            manifest.workspace_manifest->get("root_hash").string_val);
    }
    result["restored_root_hash"] = JsonValue::string(restored_manifest.root_hash);
    result["workspace_hash_matches"] = JsonValue::boolean(hash_matches);
    result["signature_valid"] = JsonValue::boolean(sig_valid);
    result["receipts_valid"] = JsonValue::boolean(receipts_valid);
    result["file_count"] = JsonValue::integer(static_cast<int64_t>(restored_manifest.files.size()));
    result["total_size"] = JsonValue::integer(static_cast<int64_t>(restored_manifest.total_size));
    result["capabilities"] = manifest.capabilities;
    result["capability_note"] = JsonValue::string(manifest.capability_note);
    result["pending_operations"] = manifest.pending_operations;

    return result;
}

} // namespace hdar
