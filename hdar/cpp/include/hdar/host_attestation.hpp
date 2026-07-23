#pragma once

#include "hdar/crypto.hpp"
#include <string>

namespace hdar {

struct HostAttestation {
    std::string attestation_id;
    std::string host_id;
    std::string host_fingerprint;
    std::string host_public_key_hex;
    std::string runtime_id;
    std::string provider;
    std::string arch;
    std::string os;
    std::string kernel;
    std::string cpu_model;
    int cpu_count = 0;
    std::string memory_total;
    std::string accelerator;
    std::string network_policy;
    double timestamp = 0.0;

    std::string attestation_hash;
    std::string signature;

    std::vector<uint8_t> canonical_bytes() const;
    std::string compute_hash() const;

    void sign(const PrivateKey& sk);
    bool verify(const PublicKey& pk) const;

    JsonValue to_json() const;
    static HostAttestation from_json(const JsonValue& v);
};

HostAttestation build_host_attestation(
    const std::string& host_id,
    const HostKeyPair& host_keys,
    const std::string& runtime_id,
    const std::string& provider,
    const std::string& arch = "arm64",
    const std::string& os = "linux",
    const std::string& kernel = "",
    const std::string& cpu_model = "",
    int cpu_count = 0,
    const std::string& memory_total = "",
    const std::string& accelerator = "none",
    const std::string& network_policy = "none");

} // namespace hdar
