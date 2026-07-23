#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <optional>

namespace hdar {

struct LineageEpoch {
    std::string epoch_id;
    std::string agent_id;
    int sequence = 0;
    std::optional<std::string> parent_epoch;
    double created_at = 0.0;

    static LineageEpoch genesis(const std::string& agent_id);
    static LineageEpoch child(const LineageEpoch& parent);

    JsonValue to_json() const;
    static LineageEpoch from_json(const JsonValue& v);
};

struct AgentIdentity {
    std::string agent_id;
    std::string name;
    PrivateKey signing_key;
    double created_at = 0.0;

    static AgentIdentity create(const std::string& name,
                                 const std::string& agent_id = "");
    static AgentIdentity create_with_key(const std::string& name,
                                          const PrivateKey& key,
                                          const std::string& agent_id = "");

    PublicKey public_key() const { return signing_key.public_key(); }
    std::string fingerprint() const { return public_key().fingerprint(); }

    std::vector<uint8_t> sign(const uint8_t* data, size_t len) const;
    std::vector<uint8_t> sign(const std::vector<uint8_t>& data) const;
    std::string sign_hex(const std::vector<uint8_t>& data) const;

    JsonValue to_public_json() const;
};

} // namespace hdar
