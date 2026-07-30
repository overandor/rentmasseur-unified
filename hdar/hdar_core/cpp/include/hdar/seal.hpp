#pragma once

#include "hdar/crypto.hpp"
#include "hdar/store.hpp"
#include "hdar/identity.hpp"
#include "hdar/receipt.hpp"
#include "hdar/capabilities.hpp"
#include <string>
#include <optional>

namespace hdar {

// Forward declaration
class LeaseManager;

struct CapsuleManifest {
    std::string agent_id;
    std::string agent_name;
    JsonValue epoch{JsonValue::object()};
    std::optional<std::string> parent_capsule_hash;

    std::string model_digest;
    std::string tokenizer_digest;
    JsonValue inference_requirements{JsonValue::object()};

    std::string objective;
    std::string continuation_point;
    std::string working_summary;

    std::optional<JsonValue> workspace_manifest;
    JsonValue capabilities{JsonValue::object()};
    std::string capability_note;

    JsonValue secret_references{JsonValue::array()};
    JsonValue pending_operations{JsonValue::array()};
    JsonValue runtime_compatibility{JsonValue::object()};

    std::string restoration_contract = "exact";

    JsonValue receipts{JsonValue::array()};

    std::string manifest_hash;
    std::string signer_fingerprint;
    std::string signature;
    double sealed_at = 0.0;

    // Bytes that are signed (excludes signature, manifest_hash, sealed_at)
    std::vector<uint8_t> canonical_bytes() const;
    std::string compute_hash() const;

    JsonValue to_json() const;
    static CapsuleManifest from_json(const JsonValue& v);
};

class CapsuleSealer {
public:
    CapsuleSealer(ContentStore& store, AgentIdentity& identity,
                  LeaseManager* lease_manager = nullptr);

    std::pair<CapsuleManifest, ReceiptChain> seal(
        const std::string& workspace_dir,
        const LineageEpoch& epoch,
        const std::string& objective = "",
        const std::string& continuation_point = "",
        const std::string& working_summary = "",
        const JsonValue& capabilities = JsonValue::object(),
        const std::string& capability_note = "",
        const std::optional<std::string>& parent_capsule_hash = std::nullopt,
        const std::string& model_digest = "",
        const std::string& tokenizer_digest = "",
        const JsonValue& inference_requirements = JsonValue::object(),
        const JsonValue& secret_references = JsonValue::array(),
        const JsonValue& pending_operations = JsonValue::array(),
        const JsonValue& runtime_compatibility = JsonValue::object(),
        const std::string& fencing_token = "");

    void write_capsule(const CapsuleManifest& manifest, const std::string& output_path) const;

    bool verify_manifest(const CapsuleManifest& manifest, const PublicKey& pk) const;
    bool verify_capsule_file(const std::string& capsule_path, const PublicKey& pk) const;

private:
    ContentStore& store_;
    AgentIdentity& identity_;
    LeaseManager* lease_manager_;
};

} // namespace hdar
