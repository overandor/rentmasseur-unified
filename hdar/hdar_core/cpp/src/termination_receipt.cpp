#include "hdar/termination_receipt.hpp"

namespace hdar {

std::vector<uint8_t> TerminationReceipt::canonical_bytes() const {
    JsonValue v = JsonValue::object();
    v["receipt_id"] = JsonValue::string(receipt_id);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["provider"] = JsonValue::string(provider);
    v["stop_time"] = JsonValue::number(stop_time);
    v["delete_time"] = JsonValue::number(delete_time);
    if (inspection)
        v["inspection"] = *inspection;
    else
        v["inspection"] = JsonValue::null();
    v["fencing_token_revoked"] = JsonValue::string(fencing_token_revoked);
    return canonical_json_bytes(v);
}

std::string TerminationReceipt::compute_hash() const {
    auto bytes = canonical_bytes();
    auto sig = from_hex(signature);
    bytes.insert(bytes.end(), sig.begin(), sig.end());
    return sha256_hex(bytes);
}

void TerminationReceipt::sign(const PrivateKey& sk) {
    timestamp = epoch_seconds();
    auto bytes = canonical_bytes();
    signature = sk.sign_hex(bytes);
    receipt_hash = compute_hash();
}

bool TerminationReceipt::verify(const PublicKey& pk) const {
    auto bytes = canonical_bytes();
    if (!pk.verify_hex(bytes, signature))
        return false;
    return compute_hash() == receipt_hash;
}

JsonValue TerminationReceipt::to_json() const {
    JsonValue v = JsonValue::object();
    v["receipt_id"] = JsonValue::string(receipt_id);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["provider"] = JsonValue::string(provider);
    v["stop_time"] = JsonValue::number(stop_time);
    v["delete_time"] = JsonValue::number(delete_time);
    if (inspection)
        v["inspection"] = *inspection;
    else
        v["inspection"] = JsonValue::null();
    v["fencing_token_revoked"] = JsonValue::string(fencing_token_revoked);
    v["receipt_hash"] = JsonValue::string(receipt_hash);
    v["signature"] = JsonValue::string(signature);
    v["timestamp"] = JsonValue::number(timestamp);
    return v;
}

TerminationReceipt TerminationReceipt::from_json(const JsonValue& v) {
    TerminationReceipt r;
    r.receipt_id = v.get("receipt_id").string_val;
    r.runtime_id = v.get("runtime_id").string_val;
    r.provider = v.get("provider").string_val;
    r.stop_time = v.get("stop_time").double_val;
    r.delete_time = v.get("delete_time").double_val;
    const auto& insp = v.get("inspection");
    if (insp.type != JsonValue::Type::Null)
        r.inspection = insp;
    r.fencing_token_revoked = v.get("fencing_token_revoked").string_val;
    r.receipt_hash = v.get("receipt_hash").string_val;
    r.signature = v.get("signature").string_val;
    r.timestamp = v.get("timestamp").double_val;
    return r;
}

TerminationReceipt build_termination_receipt(
    const std::string& runtime_id,
    const std::string& provider,
    const JsonValue& inspection,
    const std::string& fencing_token,
    const PrivateKey& signing_key) {

    TerminationReceipt r;
    r.receipt_id = "term-" + generate_uuid_hex().substr(0, 12);
    r.runtime_id = runtime_id;
    r.provider = provider;
    r.stop_time = epoch_seconds();
    r.delete_time = epoch_seconds();
    r.inspection = inspection;
    r.fencing_token_revoked = fencing_token;
    r.sign(signing_key);
    return r;
}

} // namespace hdar
