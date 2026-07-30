#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <optional>

namespace hdar {

struct TerminationReceipt {
    std::string receipt_id;
    std::string runtime_id;
    std::string provider;
    double stop_time = 0.0;
    double delete_time = 0.0;
    std::optional<JsonValue> inspection;
    std::string fencing_token_revoked;
    std::string receipt_hash;
    std::string signature;
    double timestamp = 0.0;

    std::vector<uint8_t> canonical_bytes() const;
    std::string compute_hash() const;

    void sign(const PrivateKey& sk);
    bool verify(const PublicKey& pk) const;

    JsonValue to_json() const;
    static TerminationReceipt from_json(const JsonValue& v);
};

TerminationReceipt build_termination_receipt(
    const std::string& runtime_id,
    const std::string& provider,
    const JsonValue& inspection,
    const std::string& fencing_token,
    const PrivateKey& signing_key);

} // namespace hdar
