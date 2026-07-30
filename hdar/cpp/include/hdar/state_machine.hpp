#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <map>

namespace hdar {

enum class AgentState {
    DORMANT,
    ACQUIRING_LEASE,
    MATERIALIZING,
    VERIFYING_INPUT,
    RUNNING,
    QUIESCING,
    SEALING,
    DESTROYING,
    // failure states
    QUARANTINED,
    DEGRADED,
    UNKNOWN_EFFECT,
    LEASE_LOST,
    RESTORE_REJECTED,
    DESTRUCTION_UNCONFIRMED
};

std::string state_name(AgentState s);

struct StateTransition {
    AgentState from_state;
    AgentState to_state;
    double timestamp = 0.0;
    std::string reason;
    JsonValue metadata{JsonValue::object()};
};

class LifecycleStateMachine {
public:
    explicit LifecycleStateMachine(const std::string& agent_id);

    bool transition(AgentState to, const std::string& reason = "",
                    const JsonValue& metadata = JsonValue::object());

    bool can_seal() const;
    bool is_running() const { return state_ == AgentState::RUNNING; }
    bool is_dormant() const { return state_ == AgentState::DORMANT; }
    bool is_failure() const;

    AgentState state() const { return state_; }
    const std::vector<StateTransition>& history() const { return history_; }

    JsonValue to_json() const;

private:
    std::string agent_id_;
    AgentState state_ = AgentState::DORMANT;
    std::vector<StateTransition> history_;
    double transition_time_ = 0.0;

    static bool is_valid_transition(AgentState from, AgentState to);
};

} // namespace hdar
