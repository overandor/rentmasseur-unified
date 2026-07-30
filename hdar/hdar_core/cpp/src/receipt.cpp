#include "hdar/receipt.hpp"

namespace hdar {

// ── Receipt ───────────────────────────────────────────────────

std::vector<uint8_t> Receipt::canonical_bytes() const {
    JsonValue v = JsonValue::object();
    v["receipt_type"] = JsonValue::string(receipt_type);
    v["agent_id"] = JsonValue::string(agent_id);
    v["epoch_id"] = JsonValue::string(epoch_id);
    v["timestamp"] = JsonValue::number(timestamp);
    if (prior_receipt_hash)
        v["prior_receipt_hash"] = JsonValue::string(*prior_receipt_hash);
    else
        v["prior_receipt_hash"] = JsonValue::null();
    v["action"] = JsonValue::string(action);
    v["action_payload"] = action_payload;
    v["state_root"] = JsonValue::string(state_root);
    v["signer_fingerprint"] = JsonValue::string(signer_fingerprint);
    return canonical_json_bytes(v);
}

std::string Receipt::compute_hash() const {
    auto bytes = canonical_bytes();
    // Append signature bytes
    auto sig = from_hex(signature);
    bytes.insert(bytes.end(), sig.begin(), sig.end());
    return sha256_hex(bytes);
}

void Receipt::sign(const PrivateKey& sk) {
    timestamp = epoch_seconds();
    auto bytes = canonical_bytes();
    signature = sk.sign_hex(bytes);
    receipt_hash = compute_hash();
}

bool Receipt::verify(const PublicKey& pk) const {
    auto bytes = canonical_bytes();
    if (!pk.verify_hex(bytes, signature))
        return false;
    return compute_hash() == receipt_hash;
}

JsonValue Receipt::to_json() const {
    JsonValue v = JsonValue::object();
    v["receipt_type"] = JsonValue::string(receipt_type);
    v["agent_id"] = JsonValue::string(agent_id);
    v["epoch_id"] = JsonValue::string(epoch_id);
    v["timestamp"] = JsonValue::number(timestamp);
    if (prior_receipt_hash)
        v["prior_receipt_hash"] = JsonValue::string(*prior_receipt_hash);
    else
        v["prior_receipt_hash"] = JsonValue::null();
    v["action"] = JsonValue::string(action);
    v["action_payload"] = action_payload;
    v["state_root"] = JsonValue::string(state_root);
    v["receipt_hash"] = JsonValue::string(receipt_hash);
    v["signer_fingerprint"] = JsonValue::string(signer_fingerprint);
    v["signature"] = JsonValue::string(signature);
    return v;
}

Receipt Receipt::from_json(const JsonValue& v) {
    Receipt r;
    r.receipt_type = v.get("receipt_type").string_val;
    r.agent_id = v.get("agent_id").string_val;
    r.epoch_id = v.get("epoch_id").string_val;
    r.timestamp = v.get("timestamp").double_val;
    const auto& ph = v.get("prior_receipt_hash");
    if (ph.type == JsonValue::Type::String)
        r.prior_receipt_hash = ph.string_val;
    r.action = v.get("action").string_val;
    r.action_payload = v.get("action_payload");
    r.state_root = v.get("state_root").string_val;
    r.receipt_hash = v.get("receipt_hash").string_val;
    r.signer_fingerprint = v.get("signer_fingerprint").string_val;
    r.signature = v.get("signature").string_val;
    return r;
}

// ── ReceiptChain ──────────────────────────────────────────────

ReceiptChain::ReceiptChain(const std::string& aid, const std::string& eid,
                           const PrivateKey& sk)
    : agent_id_(aid), epoch_id_(eid), signing_key_(sk),
      public_key_(sk.public_key()),
      fingerprint_(public_key_.fingerprint()) {}

const std::optional<std::string> ReceiptChain::head_hash() const {
    if (receipts_.empty()) return std::nullopt;
    return receipts_.back().receipt_hash;
}

Receipt& ReceiptChain::append(const std::string& type, const std::string& action,
                              const JsonValue& payload, const std::string& state_root) {
    Receipt r;
    r.receipt_type = type;
    r.agent_id = agent_id_;
    r.epoch_id = epoch_id_;
    r.prior_receipt_hash = head_hash();
    r.action = action;
    r.action_payload = payload;
    r.state_root = state_root;
    r.signer_fingerprint = fingerprint_;
    r.sign(signing_key_);
    receipts_.push_back(std::move(r));
    return receipts_.back();
}

bool ReceiptChain::verify(const PublicKey& pk) const {
    std::optional<std::string> prev_hash;
    for (const auto& r : receipts_) {
        if (r.prior_receipt_hash != prev_hash)
            return false;
        if (!r.verify(pk))
            return false;
        prev_hash = r.receipt_hash;
    }
    return true;
}

JsonValue ReceiptChain::to_json_array() const {
    JsonValue arr = JsonValue::array();
    for (const auto& r : receipts_)
        arr.push_back(r.to_json());
    return arr;
}

ReceiptChain ReceiptChain::from_json_array(const JsonValue& arr, const PrivateKey& sk) {
    if (arr.array_val.empty())
        throw std::runtime_error("cannot load empty receipt chain");
    const auto& first = arr.array_val[0];
    ReceiptChain chain(first.get("agent_id").string_val,
                       first.get("epoch_id").string_val, sk);
    for (const auto& rj : arr.array_val)
        chain.receipts_.push_back(Receipt::from_json(rj));
    return chain;
}

} // namespace hdar
