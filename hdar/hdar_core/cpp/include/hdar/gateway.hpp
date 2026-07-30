#pragma once

#include "hdar/crypto.hpp"
#include "hdar/identity.hpp"
#include "hdar/lease.hpp"
#include "hdar/provider_base.hpp"
#include "hdar/seal.hpp"
#include <string>
#include <optional>
#include <functional>

namespace hdar {

struct GatewaySession {
    std::string session_id;
    std::string agent_id;
    std::string user;
    std::string runtime_id;
    std::string fencing_token;
    double connected_at = 0.0;
    bool active = false;

    JsonValue to_json() const;
};

struct AgentRegistration {
    std::string ssh_user;
    std::string agent_id;
    std::string agent_name;
    std::string default_capsule_hash;
    std::string capabilities_json;
    std::string authorized_public_key;

    JsonValue to_json() const;
    static AgentRegistration from_json(const JsonValue& v);
};

class SshGateway {
public:
    using ResolverFn = std::function<std::optional<CapsuleManifest>(const std::string& agent_id)>;
    using MaterializeFn = std::function<std::pair<RuntimeRecord, std::optional<std::string>>(
        const CapsuleManifest& manifest, const std::string& agent_id)>;
    using ExecuteFn = std::function<ExecutionResult(
        const std::string& runtime_id, const std::string& command, int timeout)>;

    SshGateway(LeaseManager& lease_manager,
               ResolverFn resolver,
               MaterializeFn materializer);

    // Process an incoming SSH connection
    // In production, this would be called from sshd ForceCommand
    std::pair<GatewaySession, std::optional<std::string>> connect(
        const std::string& agent_id,
        const std::string& user);

    // Execute a command in the session
    ExecutionResult execute(const std::string& session_id,
                            const std::string& command,
                            int timeout = 60);

    // Disconnect and collapse
    JsonValue disconnect(const std::string& session_id);

    // List active sessions
    std::vector<GatewaySession> list_sessions() const;

    // Load agent registrations from a JSON config file
    static std::vector<AgentRegistration> load_config(const std::string& config_path);

    // Save registrations to a JSON config file (persistence)
    void save_config(const std::string& config_path) const;

    // Register an agent from a config entry
    void register_agent(const AgentRegistration& reg);

    // Set the execute callback for routing commands to providers
    void set_execute_callback(ExecuteFn fn);

    // List registered agents
    const std::vector<AgentRegistration>& registrations() const { return registrations_; }

    // Verify config integrity (tamper detection)
    static bool verify_config_integrity(const std::string& config_path,
                                          const std::string& expected_hash);

    // Compute config hash for tamper detection
    static std::string compute_config_hash(const std::string& config_path);

    // Build the sshd_config ForceCommand line
    static std::string build_force_command(const std::string& gateway_binary);

    // Build authorized_keys entry with forced command
    static std::string build_authorized_keys_entry(
        const std::string& public_key,
        const std::string& agent_id,
        const std::string& gateway_binary = "/usr/local/bin/hdar-gateway");

private:
    LeaseManager& lease_manager_;
    ResolverFn resolver_;
    MaterializeFn materializer_;
    ExecuteFn execute_fn_;
    std::map<std::string, GatewaySession> sessions_;
    std::map<std::string, ProviderBase*> session_providers_;
    std::vector<AgentRegistration> registrations_;
};

} // namespace hdar
