#include "hdar/state_machine.hpp"
#include <set>
#include <map>

namespace hdar {

std::string state_name(AgentState s) {
    switch (s) {
        case AgentState::DORMANT: return "DORMANT";
        case AgentState::ACQUIRING_LEASE: return "ACQUIRING_LEASE";
        case AgentState::MATERIALIZING: return "MATERIALIZING";
        case AgentState::VERIFYING_INPUT: return "VERIFYING_INPUT";
        case AgentState::RUNNING: return "RUNNING";
        case AgentState::QUIESCING: return "QUIESCING";
        case AgentState::SEALING: return "SEALING";
        case AgentState::DESTROYING: return "DESTROYING";
        case AgentState::QUARANTINED: return "QUARANTINED";
        case AgentState::DEGRADED: return "DEGRADED";
        case AgentState::UNKNOWN_EFFECT: return "UNKNOWN_EFFECT";
        case AgentState::LEASE_LOST: return "LEASE_LOST";
        case AgentState::RESTORE_REJECTED: return "RESTORE_REJECTED";
        case AgentState::DESTRUCTION_UNCONFIRMED: return "DESTRUCTION_UNCONFIRMED";
    }
    return "UNKNOWN";
}

static std::map<AgentState, std::set<AgentState>> build_transitions() {
    return {
        {AgentState::DORMANT, {AgentState::ACQUIRING_LEASE}},
        {AgentState::ACQUIRING_LEASE, {AgentState::MATERIALIZING, AgentState::LEASE_LOST, AgentState::DORMANT}},
        {AgentState::MATERIALIZING, {AgentState::VERIFYING_INPUT, AgentState::RESTORE_REJECTED, AgentState::QUARANTINED}},
        {AgentState::VERIFYING_INPUT, {AgentState::RUNNING, AgentState::RESTORE_REJECTED, AgentState::QUARANTINED}},
        {AgentState::RUNNING, {AgentState::QUIESCING, AgentState::UNKNOWN_EFFECT, AgentState::LEASE_LOST, AgentState::QUARANTINED}},
        {AgentState::QUIESCING, {AgentState::SEALING, AgentState::UNKNOWN_EFFECT}},
        {AgentState::SEALING, {AgentState::DESTROYING, AgentState::QUARANTINED}},
        {AgentState::DESTROYING, {AgentState::DORMANT, AgentState::DESTRUCTION_UNCONFIRMED}},
        {AgentState::QUARANTINED, {AgentState::DORMANT}},
        {AgentState::DEGRADED, {AgentState::RUNNING, AgentState::DORMANT}},
        {AgentState::UNKNOWN_EFFECT, {AgentState::QUIESCING, AgentState::QUARANTINED}},
        {AgentState::LEASE_LOST, {AgentState::DORMANT}},
        {AgentState::RESTORE_REJECTED, {AgentState::DORMANT}},
        {AgentState::DESTRUCTION_UNCONFIRMED, {AgentState::DORMANT, AgentState::QUARANTINED}},
    };
}

bool LifecycleStateMachine::is_valid_transition(AgentState from, AgentState to) {
    static auto transitions = build_transitions();
    auto it = transitions.find(from);
    if (it == transitions.end()) return false;
    return it->second.count(to) > 0;
}

LifecycleStateMachine::LifecycleStateMachine(const std::string& aid)
    : agent_id_(aid), transition_time_(epoch_seconds()) {}

bool LifecycleStateMachine::transition(AgentState to, const std::string& reason,
                                        const JsonValue& metadata) {
    if (!is_valid_transition(state_, to))
        return false;

    StateTransition t;
    t.from_state = state_;
    t.to_state = to;
    t.timestamp = epoch_seconds();
    t.reason = reason;
    t.metadata = metadata;
    history_.push_back(std::move(t));
    state_ = to;
    transition_time_ = epoch_seconds();
    return true;
}

bool LifecycleStateMachine::can_seal() const {
    return state_ == AgentState::QUIESCING || state_ == AgentState::SEALING;
}

bool LifecycleStateMachine::is_failure() const {
    return state_ == AgentState::QUARANTINED ||
           state_ == AgentState::DEGRADED ||
           state_ == AgentState::UNKNOWN_EFFECT ||
           state_ == AgentState::LEASE_LOST ||
           state_ == AgentState::RESTORE_REJECTED ||
           state_ == AgentState::DESTRUCTION_UNCONFIRMED;
}

JsonValue LifecycleStateMachine::to_json() const {
    JsonValue v = JsonValue::object();
    v["agent_id"] = JsonValue::string(agent_id_);
    v["state"] = JsonValue::string(state_name(state_));

    JsonValue trans_arr = JsonValue::array();
    for (const auto& t : history_) {
        JsonValue to = JsonValue::object();
        to["from"] = JsonValue::string(state_name(t.from_state));
        to["to"] = JsonValue::string(state_name(t.to_state));
        to["timestamp"] = JsonValue::number(t.timestamp);
        to["reason"] = JsonValue::string(t.reason);
        to["metadata"] = t.metadata;
        trans_arr.push_back(std::move(to));
    }
    v["transitions"] = std::move(trans_arr);
    return v;
}

} // namespace hdar
