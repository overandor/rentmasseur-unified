#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <optional>

namespace hdar {

struct Receipt {
    std::string receipt_type;
    std::string agent_id;
    std::string epoch_id;
    double timestamp = 0.0;
    std::optional<std::string> prior_receipt_hash;
    std::string action;
    JsonValue action_payload{JsonValue::object()};
    std::string state_root;
    std::string receipt_hash;
    std::string signer_fingerprint;
    std::string signature;

    // Bytes that are signed and hashed (excludes signature and receipt_hash)
    std::vector<uint8_t> canonical_bytes() const;

    // Compute hash over canonical bytes + signature
    std::string compute_hash() const;

    // Sign with Ed25519 private key
    void sign(const PrivateKey& sk);

    // Verify Ed25519 signature and hash linkage
    bool verify(const PublicKey& pk) const;

    JsonValue to_json() const;
    static Receipt from_json(const JsonValue& v);
};

class ReceiptChain {
public:
    ReceiptChain(const std::string& agent_id, const std::string& epoch_id,
                 const PrivateKey& signing_key);

    const std::optional<std::string> head_hash() const;

    Receipt& append(const std::string& receipt_type, const std::string& action,
                    const JsonValue& payload = JsonValue::object(),
                    const std::string& state_root = "");

    bool verify(const PublicKey& pk) const;

    JsonValue to_json_array() const;
    static ReceiptChain from_json_array(const JsonValue& arr, const PrivateKey& sk);

    size_t size() const { return receipts_.size(); }
    const std::vector<Receipt>& receipts() const { return receipts_; }

private:
    std::string agent_id_;
    std::string epoch_id_;
    PrivateKey signing_key_;
    PublicKey public_key_;
    std::string fingerprint_;
    std::vector<Receipt> receipts_;
};

} // namespace hdar
