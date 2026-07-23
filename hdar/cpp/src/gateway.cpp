#include "hdar/gateway.hpp"
#include <fstream>
#include <sstream>
#include <filesystem>

namespace fs = std::filesystem;

namespace hdar {

JsonValue GatewaySession::to_json() const {
    JsonValue v = JsonValue::object();
    v["session_id"] = JsonValue::string(session_id);
    v["agent_id"] = JsonValue::string(agent_id);
    v["user"] = JsonValue::string(user);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["fencing_token"] = JsonValue::string(fencing_token);
    v["connected_at"] = JsonValue::number(connected_at);
    v["active"] = JsonValue::boolean(active);
    return v;
}

SshGateway::SshGateway(LeaseManager& lease_manager,
                       ResolverFn resolver,
                       MaterializeFn materializer)
    : lease_manager_(lease_manager)
    , resolver_(resolver)
    , materializer_(materializer) {}

std::pair<GatewaySession, std::optional<std::string>> SshGateway::connect(
    const std::string& agent_id,
    const std::string& user) {

    // 1. Resolve agent to latest capsule
    auto manifest = resolver_(agent_id);
    if (!manifest)
        return {{}, "agent not found: " + agent_id};

    // 2. Acquire lease
    std::string runtime_id = "gw-" + generate_uuid_hex().substr(0, 8);
    auto [lease, error] = lease_manager_.acquire(
        agent_id, manifest->manifest_hash, 0, user, runtime_id);

    if (error)
        return {{}, *error};

    // 3. Materialize runtime
    auto [runtime, mat_err] = materializer_(*manifest, agent_id);
    if (mat_err) {
        lease_manager_.release(agent_id, lease->fencing_token);
        return {{}, *mat_err};
    }

    // 4. Create session
    GatewaySession session;
    session.session_id = generate_uuid_hex();
    session.agent_id = agent_id;
    session.user = user;
    session.runtime_id = runtime_id;
    session.fencing_token = lease->fencing_token;
    session.connected_at = epoch_seconds();
    session.active = true;

    sessions_[session.session_id] = session;

    return {session, std::nullopt};
}

ExecutionResult SshGateway::execute(const std::string& session_id,
                                    const std::string& command,
                                    int timeout) {
    auto it = sessions_.find(session_id);
    if (it == sessions_.end() || !it->second.active)
        throw std::runtime_error("session not found or inactive");

    if (execute_fn_) {
        return execute_fn_(it->second.runtime_id, command, timeout);
    }

    // No execute callback configured — this is an error, not a stub
    ExecutionResult result;
    result.operation_type = "ssh-gateway";
    result.command = command;
    result.exit_code = -1;
    result.stderr_text = "no execute callback configured for gateway";
    result.success = false;
    return result;
}

void SshGateway::set_execute_callback(ExecuteFn fn) {
    execute_fn_ = std::move(fn);
}

JsonValue SshGateway::disconnect(const std::string& session_id) {
    auto it = sessions_.find(session_id);
    if (it == sessions_.end())
        throw std::runtime_error("session not found");

    // Release lease
    lease_manager_.release(it->second.agent_id, it->second.fencing_token);

    // Mark inactive
    it->second.active = false;

    JsonValue result = JsonValue::object();
    result["disconnected"] = JsonValue::boolean(true);
    result["session_id"] = JsonValue::string(session_id);
    result["agent_id"] = JsonValue::string(it->second.agent_id);
    result["runtime_id"] = JsonValue::string(it->second.runtime_id);
    return result;
}

std::vector<GatewaySession> SshGateway::list_sessions() const {
    std::vector<GatewaySession> result;
    for (const auto& [id, session] : sessions_)
        if (session.active)
            result.push_back(session);
    return result;
}

std::string SshGateway::build_force_command(const std::string& gateway_binary) {
    return "ForceCommand " + gateway_binary + " --agent $SSH_ORIGINAL_COMMAND";
}

std::string SshGateway::build_authorized_keys_entry(
    const std::string& public_key,
    const std::string& agent_id,
    const std::string& gateway_binary) {

    std::string entry;
    entry += "command=\"" + gateway_binary + " --agent " + agent_id + "\"";
    entry += ",no-port-forwarding,no-X11-forwarding,no-pty";
    entry += ' ';
    entry += public_key;
    return entry;
}

JsonValue AgentRegistration::to_json() const {
    JsonValue v = JsonValue::object();
    v["ssh_user"] = JsonValue::string(ssh_user);
    v["agent_id"] = JsonValue::string(agent_id);
    v["agent_name"] = JsonValue::string(agent_name);
    v["default_capsule_hash"] = JsonValue::string(default_capsule_hash);
    v["capabilities_json"] = JsonValue::string(capabilities_json);
    v["authorized_public_key"] = JsonValue::string(authorized_public_key);
    return v;
}

AgentRegistration AgentRegistration::from_json(const JsonValue& v) {
    AgentRegistration r;
    r.ssh_user = v.get("ssh_user").string_val;
    r.agent_id = v.get("agent_id").string_val;
    r.agent_name = v.get("agent_name").string_val;
    r.default_capsule_hash = v.get("default_capsule_hash").string_val;
    r.capabilities_json = v.get("capabilities_json").string_val;
    r.authorized_public_key = v.get("authorized_public_key").string_val;
    return r;
}

void SshGateway::register_agent(const AgentRegistration& reg) {
    registrations_.push_back(reg);
}

std::vector<AgentRegistration> SshGateway::load_config(const std::string& config_path) {
    std::vector<AgentRegistration> regs;
    if (!fs::exists(config_path))
        return regs;

    std::ifstream f(config_path);
    std::stringstream ss;
    ss << f.rdbuf();
    std::string content = ss.str();

    // Parse JSON array of registrations
    // Minimal parser: extract each object from the array
    // We use the canonical_json infrastructure
    JsonValue root = JsonValue::null();

    // Parse manually since we don't have a full JSON parser
    // Look for "agents" array
    size_t agents_pos = content.find("\"agents\"");
    if (agents_pos == std::string::npos) return regs;

    size_t arr_start = content.find('[', agents_pos);
    if (arr_start == std::string::npos) return regs;

    int depth = 0;
    size_t obj_start = std::string::npos;
    for (size_t i = arr_start; i < content.size(); i++) {
        if (content[i] == '{') {
            if (depth == 0) obj_start = i;
            depth++;
        } else if (content[i] == '}') {
            depth--;
            if (depth == 0 && obj_start != std::string::npos) {
                // Extract object substring and parse with from_json
                // For now, extract fields manually
                std::string obj_str = content.substr(obj_start, i - obj_start + 1);

                AgentRegistration reg;

                auto extract_field = [&obj_str](const std::string& field) -> std::string {
                    std::string key = "\"" + field + "\"";
                    size_t pos = obj_str.find(key);
                    if (pos == std::string::npos) return "";
                    pos = obj_str.find(':', pos);
                    if (pos == std::string::npos) return "";
                    pos = obj_str.find('"', pos + 1);
                    if (pos == std::string::npos) return "";
                    size_t end = obj_str.find('"', pos + 1);
                    if (end == std::string::npos) return "";
                    return obj_str.substr(pos + 1, end - pos - 1);
                };

                reg.ssh_user = extract_field("ssh_user");
                reg.agent_id = extract_field("agent_id");
                reg.agent_name = extract_field("agent_name");
                reg.default_capsule_hash = extract_field("default_capsule_hash");
                reg.capabilities_json = extract_field("capabilities_json");
                reg.authorized_public_key = extract_field("authorized_public_key");

                regs.push_back(reg);
                obj_start = std::string::npos;
            }
        }
    }

    return regs;
}

void SshGateway::save_config(const std::string& config_path) const {
    auto parent = fs::path(config_path).parent_path();
    if (!parent.empty())
        fs::create_directories(parent);

    std::ofstream f(config_path);
    f << "{\"agents\":[";
    for (size_t i = 0; i < registrations_.size(); i++) {
        if (i > 0) f << ",";
        f << canonical_json(registrations_[i].to_json());
    }
    f << "]}";
}

std::string SshGateway::compute_config_hash(const std::string& config_path) {
    if (!fs::exists(config_path))
        return "";
    std::ifstream f(config_path);
    std::stringstream ss;
    ss << f.rdbuf();
    return sha256_hex(ss.str());
}

bool SshGateway::verify_config_integrity(const std::string& config_path,
                                           const std::string& expected_hash) {
    std::string current_hash = compute_config_hash(config_path);
    if (current_hash.empty()) return false;
    return current_hash == expected_hash;
}

} // namespace hdar
