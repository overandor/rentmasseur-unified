#pragma once

#include "hdar/crypto.hpp"
#include "hdar/state_machine.hpp"
#include "hdar/effects.hpp"
#include "hdar/lease.hpp"
#include "hdar/provider_base.hpp"
#include "hdar/identity.hpp"
#include "hdar/seal.hpp"
#include <memory>
#include <optional>

namespace hdar {

struct ControllerConfig {
    std::string workspace_root;
    std::string store_dir;
    std::string lease_db;
    std::string effects_ledger;
    int lease_ttl = 900;
};

class LifecycleController {
public:
    LifecycleController(const AgentIdentity& identity,
                        ProviderBase* provider,
                        ContentStore& store,
                        const ControllerConfig& config);

    // Wake: acquire lease, materialize runtime
    std::pair<RuntimeRecord, std::optional<std::string>> wake(
        const std::string& capsule_hash,
        const std::string& workspace_dir,
        const std::string& destination_runtime = "");

    // Execute an operation
    ExecutionResult execute(const std::string& operation_type,
                            const std::string& command,
                            int timeout = 60);

    // Effect management
    ExternalEffect register_effect(const std::string& capability,
                                    const std::vector<uint8_t>& payload,
                                    const std::string& operation_id = "");
    ExternalEffect commit_effect(const std::string& operation_id,
                                  const JsonValue& provider_receipt = JsonValue::null());
    ExternalEffect mark_effect_unknown(const std::string& operation_id);

    // Check if safe to seal
    JsonValue check_quiescence() const;

    // Collapse: quiesce, seal, destroy, release
    JsonValue collapse(const LineageEpoch& epoch,
                       const std::string& objective = "",
                       const std::string& continuation_point = "",
                       const std::string& working_summary = "",
                       const JsonValue& capabilities = JsonValue::object(),
                       const std::string& capability_note = "",
                       const std::optional<std::string>& parent_capsule_hash = std::nullopt,
                       const std::string& fencing_token = "");

    // Getters
    AgentState state() const { return sm_.state(); }
    const std::optional<Lease>& current_lease() const { return lease_; }
    const std::optional<RuntimeRecord>& current_runtime() const { return runtime_; }
    const std::string& fencing_token() const { return fencing_token_; }

private:
    AgentIdentity identity_;
    ProviderBase* provider_;
    ContentStore& store_;
    ControllerConfig config_;

    LifecycleStateMachine sm_;
    EffectRegistry effects_;
    LeaseManager lease_manager_;
    CapsuleSealer sealer_;

    std::optional<Lease> lease_;
    std::optional<RuntimeRecord> runtime_;
    std::string fencing_token_;
    std::string current_runtime_id_;
};

} // namespace hdar
