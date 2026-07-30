#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <optional>

namespace hdar {

struct ExecutionReceipt {
    std::string receipt_id;
    std::string capsule_hash;
    std::string host_id;
    std::string host_fingerprint;
    std::string host_public_key_hex;
    std::string runtime_id;
    std::string runtime_provider;
    double start_time = 0.0;
    double end_time = 0.0;

    JsonValue environment{JsonValue::object()};
    JsonValue operations{JsonValue::array()};
    JsonValue results{JsonValue::array()};
    JsonValue authority{JsonValue::object()};

    std::string receipt_hash;
    std::string signature;
    double timestamp = 0.0;

    std::vector<uint8_t> canonical_bytes() const;
    std::string compute_hash() const;

    void sign(const PrivateKey& host_sk);
    bool verify(const PublicKey& host_pk) const;

    JsonValue to_json() const;
    static ExecutionReceipt from_json(const JsonValue& v);
};

class ExecutionReceiptBuilder {
public:
    ExecutionReceiptBuilder(const std::string& capsule_hash,
                            const HostKeyPair& host_keys,
                            const std::string& runtime_id,
                            const std::string& runtime_provider);

    void set_environment(const JsonValue& env);
    void add_operation(const std::string& op_type, const JsonValue& result);
    void set_authority(const JsonValue& auth);

    ExecutionReceipt build_and_sign();

private:
    ExecutionReceipt receipt_;
    HostKeyPair host_keys_;
};

} // namespace hdar
