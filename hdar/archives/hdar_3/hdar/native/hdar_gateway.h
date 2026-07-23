// hdar_gateway.h — SSH ForceCommand gateway with capsule resolver.

#ifndef HDAR_GATEWAY_H
#define HDAR_GATEWAY_H

#include <string>
#include <vector>
#include <functional>
#include "hdar_crypto.h"
#include "hdar_store.h"
#include "hdar_lease.h"
#include "hdar_provider.h"
#include "hdar_continuity.h"

namespace hdar {

/// SSH session info extracted from environment.
struct SSHSessionInfo {
    std::string user;              // SSH user (maps to agent ID)
    std::string original_command;  // SSH_ORIGINAL_COMMAND
    std::string client_ip;         // SSH_CLIENT (first field)
    std::string connection;        // SSH_CONNECTION
};

/// Agent registration: maps SSH user to agent identity.
struct AgentRegistration {
    std::string ssh_user;
    std::string agent_id;
    std::string agent_name;
    std::string default_capsule_hash;
    std::string capabilities_json;
};

/// SSH gateway: routes SSH sessions through the continuity loop.
class SSHGateway {
public:
    using CommandHandler = std::function<std::string(const std::string& command, const std::string& runtime_id)>;

    SSHGateway(
        ContinuityLoop& loop,
        ContentStore& store,
        LeaseManager& lease_mgr,
        AppleContainerProvider& provider,
        const Ed25519KeyPair& owner_key
    );

    /// Register an agent mapping.
    void register_agent(const AgentRegistration& reg);

    /// Handle an incoming SSH session. Returns output string.
    std::string handle_session(const SSHSessionInfo& info);

    /// Resolve SSH user to agent registration.
    const AgentRegistration* resolve_agent(const std::string& ssh_user) const;

    /// List registered agents.
    const std::vector<AgentRegistration>& agents() const { return agents_; }

private:
    ContinuityLoop& loop_;
    ContentStore& store_;
    LeaseManager& lease_mgr_;
    AppleContainerProvider& provider_;
    Ed25519KeyPair owner_key_;
    std::vector<AgentRegistration> agents_;

    std::string generate_runtime_id(const std::string& agent_id);
};

} // namespace hdar

#endif // HDAR_GATEWAY_H
