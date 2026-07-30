#include "hdar/execution_receipt.hpp"

namespace hdar {

std::vector<uint8_t> ExecutionReceipt::canonical_bytes() const {
    JsonValue v = JsonValue::object();
    v["receipt_id"] = JsonValue::string(receipt_id);
    v["capsule_hash"] = JsonValue::string(capsule_hash);
    v["host_id"] = JsonValue::string(host_id);
    v["host_fingerprint"] = JsonValue::string(host_fingerprint);
    v["host_public_key_hex"] = JsonValue::string(host_public_key_hex);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["runtime_provider"] = JsonValue::string(runtime_provider);
    v["start_time"] = JsonValue::number(start_time);
    v["end_time"] = JsonValue::number(end_time);
    v["environment"] = environment;
    v["operations"] = operations;
    v["results"] = results;
    v["authority"] = authority;
    return canonical_json_bytes(v);
}

std::string ExecutionReceipt::compute_hash() const {
    auto bytes = canonical_bytes();
    auto sig = from_hex(signature);
    bytes.insert(bytes.end(), sig.begin(), sig.end());
    return sha256_hex(bytes);
}

void ExecutionReceipt::sign(const PrivateKey& host_sk) {
    timestamp = epoch_seconds();
    auto bytes = canonical_bytes();
    signature = host_sk.sign_hex(bytes);
    receipt_hash = compute_hash();
}

bool ExecutionReceipt::verify(const PublicKey& host_pk) const {
    auto bytes = canonical_bytes();
    if (!host_pk.verify_hex(bytes, signature))
        return false;
    return compute_hash() == receipt_hash;
}

JsonValue ExecutionReceipt::to_json() const {
    JsonValue v = JsonValue::object();
    v["receipt_id"] = JsonValue::string(receipt_id);
    v["capsule_hash"] = JsonValue::string(capsule_hash);
    v["host_id"] = JsonValue::string(host_id);
    v["host_fingerprint"] = JsonValue::string(host_fingerprint);
    v["host_public_key_hex"] = JsonValue::string(host_public_key_hex);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["runtime_provider"] = JsonValue::string(runtime_provider);
    v["start_time"] = JsonValue::number(start_time);
    v["end_time"] = JsonValue::number(end_time);
    v["environment"] = environment;
    v["operations"] = operations;
    v["results"] = results;
    v["authority"] = authority;
    v["receipt_hash"] = JsonValue::string(receipt_hash);
    v["signature"] = JsonValue::string(signature);
    v["timestamp"] = JsonValue::number(timestamp);
    return v;
}

ExecutionReceipt ExecutionReceipt::from_json(const JsonValue& v) {
    ExecutionReceipt r;
    r.receipt_id = v.get("receipt_id").string_val;
    r.capsule_hash = v.get("capsule_hash").string_val;
    r.host_id = v.get("host_id").string_val;
    r.host_fingerprint = v.get("host_fingerprint").string_val;
    r.host_public_key_hex = v.get("host_public_key_hex").string_val;
    r.runtime_id = v.get("runtime_id").string_val;
    r.runtime_provider = v.get("runtime_provider").string_val;
    r.start_time = v.get("start_time").double_val;
    r.end_time = v.get("end_time").double_val;
    r.environment = v.get("environment");
    r.operations = v.get("operations");
    r.results = v.get("results");
    r.authority = v.get("authority");
    r.receipt_hash = v.get("receipt_hash").string_val;
    r.signature = v.get("signature").string_val;
    r.timestamp = v.get("timestamp").double_val;
    return r;
}

// ── ExecutionReceiptBuilder ───────────────────────────────────

ExecutionReceiptBuilder::ExecutionReceiptBuilder(
    const std::string& capsule_hash,
    const HostKeyPair& host_keys,
    const std::string& runtime_id,
    const std::string& runtime_provider)
    : host_keys_(host_keys) {

    receipt_.receipt_id = "exec-" + generate_uuid_hex().substr(0, 12);
    receipt_.capsule_hash = capsule_hash;
    receipt_.host_id = host_keys.host_id;
    receipt_.host_fingerprint = host_keys.fingerprint();
    receipt_.host_public_key_hex = host_keys.public_key_hex();
    receipt_.runtime_id = runtime_id;
    receipt_.runtime_provider = runtime_provider;
    receipt_.start_time = epoch_seconds();
}

void ExecutionReceiptBuilder::set_environment(const JsonValue& env) {
    receipt_.environment = env;
}

void ExecutionReceiptBuilder::add_operation(const std::string& op_type, const JsonValue& result) {
    JsonValue op = JsonValue::object();
    op["type"] = JsonValue::string(op_type);
    op["result"] = result;
    op["timestamp"] = JsonValue::number(epoch_seconds());
    receipt_.operations.push_back(op);
    receipt_.results.push_back(result);
}

void ExecutionReceiptBuilder::set_authority(const JsonValue& auth) {
    receipt_.authority = auth;
}

ExecutionReceipt ExecutionReceiptBuilder::build_and_sign() {
    receipt_.end_time = epoch_seconds();
    receipt_.sign(host_keys_.private_key);
    return receipt_;
}

} // namespace hdar
