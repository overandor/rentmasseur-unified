#include "hdar/controller.hpp"

namespace hdar {

LifecycleController::LifecycleController(
    const AgentIdentity& identity,
    ProviderBase* provider,
    ContentStore& store,
    const ControllerConfig& config)
    : identity_(identity)
    , provider_(provider)
    , store_(store)
    , config_(config)
    , sm_(identity.agent_id)
    , effects_(config.effects_ledger, nullptr, identity.agent_id)
    , lease_manager_(config.lease_db, config.lease_ttl)
    , sealer_(store, const_cast<AgentIdentity&>(identity), &lease_manager_) {}

std::pair<RuntimeRecord, std::optional<std::string>> LifecycleController::wake(
    const std::string& capsule_hash,
    const std::string& workspace_dir,
    const std::string& destination_runtime) {

    sm_.transition(AgentState::ACQUIRING_LEASE, "wake requested");

    std::string runtime_name = destination_runtime.empty()
        ? ("runtime-" + generate_uuid_hex().substr(0, 8))
        : destination_runtime;

    auto [lease, error] = lease_manager_.acquire(
        identity_.agent_id, capsule_hash, 0,
        identity_.agent_id, runtime_name);

    if (error) {
        sm_.transition(AgentState::LEASE_LOST, *error);
        return {{}, *error};
    }

    lease_ = lease;
    fencing_token_ = lease->fencing_token;

    // Re-create effects registry with lease manager now that we have a lease
    effects_ = EffectRegistry(config_.effects_ledger, &lease_manager_, identity_.agent_id);

    sm_.transition(AgentState::MATERIALIZING, "lease acquired gen=" +
                   std::to_string(lease->lease_generation));

    current_runtime_id_ = runtime_name;
    auto runtime = provider_->materialize(runtime_name, workspace_dir);
    runtime_ = runtime;

    if (!runtime.exists) {
        sm_.transition(AgentState::RESTORE_REJECTED, "materialization failed");
        return {runtime, "materialization failed"};
    }

    sm_.transition(AgentState::VERIFYING_INPUT, "runtime materialized");
    sm_.transition(AgentState::RUNNING, "verification passed");

    return {runtime, std::nullopt};
}

ExecutionResult LifecycleController::execute(
    const std::string& operation_type,
    const std::string& command,
    int timeout) {

    if (!sm_.is_running())
        throw std::runtime_error("cannot execute: agent not in RUNNING state");

    return provider_->execute(current_runtime_id_, operation_type, command, timeout);
}

ExternalEffect LifecycleController::register_effect(
    const std::string& capability,
    const std::vector<uint8_t>& payload,
    const std::string& operation_id) {

    return effects_.register_effect(
        identity_.agent_id, capability, payload, operation_id, fencing_token_);
}

ExternalEffect LifecycleController::commit_effect(
    const std::string& operation_id,
    const JsonValue& provider_receipt) {

    return effects_.commit(
        identity_.agent_id, operation_id, provider_receipt, fencing_token_);
}

ExternalEffect LifecycleController::mark_effect_unknown(const std::string& operation_id) {
    return effects_.mark_unknown(identity_.agent_id, operation_id);
}

JsonValue LifecycleController::check_quiescence() const {
    return effects_.check_quiescence(identity_.agent_id);
}

JsonValue LifecycleController::collapse(
    const LineageEpoch& epoch,
    const std::string& objective,
    const std::string& continuation_point,
    const std::string& working_summary,
    const JsonValue& capabilities,
    const std::string& capability_note,
    const std::optional<std::string>& parent_capsule_hash,
    const std::string& fencing_token) {

    // 0. Validate fencing token — stale holder cannot collapse
    if (!fencing_token.empty()) {
        if (!lease_manager_.validate_token(identity_.agent_id, fencing_token)) {
            sm_.transition(AgentState::LEASE_LOST,
                           "stale fencing token — cannot collapse");
            JsonValue result = JsonValue::object();
            result["collapsed"] = JsonValue::boolean(false);
            result["reason"] = JsonValue::string(
                "stale or invalid fencing token — this runtime's lease "
                "is no longer authoritative");
            result["runtime_id"] = JsonValue::string(current_runtime_id_);
            return result;
        }
    }

    // 1. Check quiescence
    auto q = check_quiescence();
    if (!q.get("quiescent").bool_val) {
        sm_.transition(AgentState::UNKNOWN_EFFECT, "blocking effects prevent seal");
        JsonValue result = JsonValue::object();
        result["collapsed"] = JsonValue::boolean(false);
        result["reason"] = JsonValue::string("blocking effects prevent seal");
        result["quiescence"] = q;
        return result;
    }

    // 2. Transition to quiescing
    sm_.transition(AgentState::QUIESCING, "quiescent");

    // 3. Seal capsule
    sm_.transition(AgentState::SEALING, "sealing capsule");

    std::string workspace_dir = runtime_ && !runtime_->workspace_mount.empty()
        ? runtime_->workspace_mount
        : config_.workspace_root + "/" + current_runtime_id_;
    auto [manifest, chain] = sealer_.seal(
        workspace_dir, epoch, objective, continuation_point, working_summary,
        capabilities, capability_note, parent_capsule_hash,
        "", "", JsonValue::object(), JsonValue::array(), JsonValue::array(),
        JsonValue::object(), fencing_token_);

    // 4. Write capsule
    std::string capsule_path = config_.store_dir + "/capsules/" +
                               manifest.manifest_hash.substr(0, 16) + ".json";
    sealer_.write_capsule(manifest, capsule_path);

    // 5. Destroy runtime
    sm_.transition(AgentState::DESTROYING, "destroying runtime");
    auto destroyed = provider_->destroy(current_runtime_id_);

    // 6. Verify destruction
    bool destruction_confirmed = provider_->verify_destruction(current_runtime_id_);
    if (!destruction_confirmed) {
        sm_.transition(AgentState::DESTRUCTION_UNCONFIRMED, "destruction not confirmed");
    } else {
        sm_.transition(AgentState::DORMANT, "destruction confirmed, dormant");
    }

    // 7. Release lease
    lease_manager_.release(identity_.agent_id, fencing_token_);
    lease_ = std::nullopt;
    fencing_token_.clear();
    runtime_ = std::nullopt;

    JsonValue result = JsonValue::object();
    result["collapsed"] = JsonValue::boolean(true);
    result["manifest_hash"] = JsonValue::string(manifest.manifest_hash);
    result["capsule_path"] = JsonValue::string(capsule_path);
    result["destruction_confirmed"] = JsonValue::boolean(destruction_confirmed);
    result["final_state"] = JsonValue::string(state_name(sm_.state()));
    result["manifest"] = manifest.to_json();
    return result;
}

} // namespace hdar
