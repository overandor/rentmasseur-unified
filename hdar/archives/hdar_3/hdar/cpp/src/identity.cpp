#include "hdar/identity.hpp"

namespace hdar {

// ── LineageEpoch ──────────────────────────────────────────────

LineageEpoch LineageEpoch::genesis(const std::string& aid) {
    LineageEpoch e;
    e.epoch_id = generate_uuid_hex();
    e.agent_id = aid;
    e.sequence = 0;
    e.parent_epoch = std::nullopt;
    e.created_at = epoch_seconds();
    return e;
}

LineageEpoch LineageEpoch::child(const LineageEpoch& parent) {
    LineageEpoch e;
    e.epoch_id = generate_uuid_hex();
    e.agent_id = parent.agent_id;
    e.sequence = parent.sequence + 1;
    e.parent_epoch = parent.epoch_id;
    e.created_at = epoch_seconds();
    return e;
}

JsonValue LineageEpoch::to_json() const {
    JsonValue v = JsonValue::object();
    v["epoch_id"] = JsonValue::string(epoch_id);
    v["agent_id"] = JsonValue::string(agent_id);
    v["sequence"] = JsonValue::integer(sequence);
    if (parent_epoch)
        v["parent_epoch"] = JsonValue::string(*parent_epoch);
    else
        v["parent_epoch"] = JsonValue::null();
    v["created_at"] = JsonValue::number(created_at);
    return v;
}

LineageEpoch LineageEpoch::from_json(const JsonValue& v) {
    LineageEpoch e;
    e.epoch_id = v.get("epoch_id").string_val;
    e.agent_id = v.get("agent_id").string_val;
    e.sequence = static_cast<int>(v.get("sequence").int_val);
    const auto& pe = v.get("parent_epoch");
    if (pe.type == JsonValue::Type::String)
        e.parent_epoch = pe.string_val;
    e.created_at = v.get("created_at").double_val;
    return e;
}

// ── AgentIdentity ─────────────────────────────────────────────

AgentIdentity AgentIdentity::create(const std::string& name, const std::string& aid) {
    AgentIdentity id;
    id.agent_id = aid.empty() ? generate_agent_id() : aid;
    id.name = name;
    id.signing_key = PrivateKey::generate();
    id.created_at = epoch_seconds();
    return id;
}

AgentIdentity AgentIdentity::create_with_key(const std::string& name,
                                              const PrivateKey& key,
                                              const std::string& aid) {
    AgentIdentity id;
    id.agent_id = aid.empty() ? generate_agent_id() : aid;
    id.name = name;
    id.signing_key = key;
    id.created_at = epoch_seconds();
    return id;
}

std::vector<uint8_t> AgentIdentity::sign(const uint8_t* data, size_t len) const {
    return signing_key.sign(data, len);
}

std::vector<uint8_t> AgentIdentity::sign(const std::vector<uint8_t>& data) const {
    return signing_key.sign(data);
}

std::string AgentIdentity::sign_hex(const std::vector<uint8_t>& data) const {
    return signing_key.sign_hex(data);
}

JsonValue AgentIdentity::to_public_json() const {
    JsonValue v = JsonValue::object();
    v["agent_id"] = JsonValue::string(agent_id);
    v["name"] = JsonValue::string(name);
    v["fingerprint"] = JsonValue::string(fingerprint());
    v["public_key"] = JsonValue::string(public_key().hex());
    v["created_at"] = JsonValue::number(created_at);
    return v;
}

} // namespace hdar
