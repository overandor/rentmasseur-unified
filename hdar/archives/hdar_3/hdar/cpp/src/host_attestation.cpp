#include "hdar/host_attestation.hpp"

namespace hdar {

std::vector<uint8_t> HostAttestation::canonical_bytes() const {
    JsonValue v = JsonValue::object();
    v["attestation_id"] = JsonValue::string(attestation_id);
    v["host_id"] = JsonValue::string(host_id);
    v["host_fingerprint"] = JsonValue::string(host_fingerprint);
    v["host_public_key_hex"] = JsonValue::string(host_public_key_hex);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["provider"] = JsonValue::string(provider);
    v["arch"] = JsonValue::string(arch);
    v["os"] = JsonValue::string(os);
    v["kernel"] = JsonValue::string(kernel);
    v["cpu_model"] = JsonValue::string(cpu_model);
    v["cpu_count"] = JsonValue::integer(cpu_count);
    v["memory_total"] = JsonValue::string(memory_total);
    v["accelerator"] = JsonValue::string(accelerator);
    v["network_policy"] = JsonValue::string(network_policy);
    v["timestamp"] = JsonValue::number(timestamp);
    return canonical_json_bytes(v);
}

std::string HostAttestation::compute_hash() const {
    auto bytes = canonical_bytes();
    auto sig = from_hex(signature);
    bytes.insert(bytes.end(), sig.begin(), sig.end());
    return sha256_hex(bytes);
}

void HostAttestation::sign(const PrivateKey& sk) {
    auto bytes = canonical_bytes();
    signature = sk.sign_hex(bytes);
    attestation_hash = compute_hash();
}

bool HostAttestation::verify(const PublicKey& pk) const {
    auto bytes = canonical_bytes();
    if (!pk.verify_hex(bytes, signature))
        return false;
    return compute_hash() == attestation_hash;
}

JsonValue HostAttestation::to_json() const {
    JsonValue v = JsonValue::object();
    v["attestation_id"] = JsonValue::string(attestation_id);
    v["host_id"] = JsonValue::string(host_id);
    v["host_fingerprint"] = JsonValue::string(host_fingerprint);
    v["host_public_key_hex"] = JsonValue::string(host_public_key_hex);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["provider"] = JsonValue::string(provider);
    v["arch"] = JsonValue::string(arch);
    v["os"] = JsonValue::string(os);
    v["kernel"] = JsonValue::string(kernel);
    v["cpu_model"] = JsonValue::string(cpu_model);
    v["cpu_count"] = JsonValue::integer(cpu_count);
    v["memory_total"] = JsonValue::string(memory_total);
    v["accelerator"] = JsonValue::string(accelerator);
    v["network_policy"] = JsonValue::string(network_policy);
    v["timestamp"] = JsonValue::number(timestamp);
    v["attestation_hash"] = JsonValue::string(attestation_hash);
    v["signature"] = JsonValue::string(signature);
    return v;
}

HostAttestation HostAttestation::from_json(const JsonValue& v) {
    HostAttestation a;
    a.attestation_id = v.get("attestation_id").string_val;
    a.host_id = v.get("host_id").string_val;
    a.host_fingerprint = v.get("host_fingerprint").string_val;
    a.host_public_key_hex = v.get("host_public_key_hex").string_val;
    a.runtime_id = v.get("runtime_id").string_val;
    a.provider = v.get("provider").string_val;
    a.arch = v.get("arch").string_val;
    a.os = v.get("os").string_val;
    a.kernel = v.get("kernel").string_val;
    a.cpu_model = v.get("cpu_model").string_val;
    a.cpu_count = static_cast<int>(v.get("cpu_count").int_val);
    a.memory_total = v.get("memory_total").string_val;
    a.accelerator = v.get("accelerator").string_val;
    a.network_policy = v.get("network_policy").string_val;
    a.timestamp = v.get("timestamp").double_val;
    a.attestation_hash = v.get("attestation_hash").string_val;
    a.signature = v.get("signature").string_val;
    return a;
}

HostAttestation build_host_attestation(
    const std::string& host_id,
    const HostKeyPair& host_keys,
    const std::string& runtime_id,
    const std::string& provider,
    const std::string& arch,
    const std::string& os,
    const std::string& kernel,
    const std::string& cpu_model,
    int cpu_count,
    const std::string& memory_total,
    const std::string& accelerator,
    const std::string& network_policy) {

    HostAttestation a;
    a.attestation_id = "att-" + generate_uuid_hex().substr(0, 12);
    a.host_id = host_id;
    a.host_fingerprint = host_keys.fingerprint();
    a.host_public_key_hex = host_keys.public_key_hex();
    a.runtime_id = runtime_id;
    a.provider = provider;
    a.arch = arch;
    a.os = os;
    a.kernel = kernel;
    a.cpu_model = cpu_model;
    a.cpu_count = cpu_count;
    a.memory_total = memory_total;
    a.accelerator = accelerator;
    a.network_policy = network_policy;
    a.timestamp = epoch_seconds();
    a.sign(host_keys.private_key);
    return a;
}

} // namespace hdar
