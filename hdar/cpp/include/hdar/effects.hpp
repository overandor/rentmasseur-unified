#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <map>
#include <optional>
#include <functional>
#include <set>

namespace hdar {

// Forward declaration
class LeaseManager;

static const std::set<std::string> BLOCKING_STATES = {
    "starting", "submitted", "unknown", "reconciliation_failed"
};

static const std::set<std::string> TERMINAL_STATES = {
    "committed", "cancelled", "proven_not_started"
};

struct ExternalEffect {
    std::string operation_id;
    std::string intent_digest;
    std::string capability_used;
    std::string request_digest;
    std::string status;
    std::optional<JsonValue> provider_receipt;
    std::optional<std::string> reconciliation_method;
    double created_at = 0.0;
    std::optional<double> committed_at;

    bool is_blocking() const;
    bool is_terminal() const;

    JsonValue to_json() const;
    static ExternalEffect from_json(const JsonValue& v);
};

class EffectRegistry {
public:
    EffectRegistry(const std::string& ledger_path,
                   LeaseManager* lease_manager = nullptr,
                   const std::string& agent_id = "");

    ExternalEffect register_effect(
        const std::string& agent_id,
        const std::string& capability_used,
        const std::vector<uint8_t>& request_payload,
        const std::string& operation_id = "",
        const std::string& fencing_token = "");

    ExternalEffect submit(const std::string& agent_id, const std::string& operation_id,
                          const std::string& fencing_token = "");
    ExternalEffect commit(const std::string& agent_id, const std::string& operation_id,
                          const JsonValue& provider_receipt = JsonValue::null(),
                          const std::string& fencing_token = "");
    ExternalEffect mark_unknown(const std::string& agent_id, const std::string& operation_id,
                                const std::string& fencing_token = "");
    ExternalEffect cancel(const std::string& agent_id, const std::string& operation_id,
                          const std::string& fencing_token = "");

    JsonValue check_quiescence(const std::string& agent_id) const;

    JsonValue reconcile(const std::string& agent_id,
                        std::function<std::string(const std::string&, const ExternalEffect&)> probe_fn);

    bool is_duplicate(const std::string& agent_id, const std::string& operation_id) const;

private:
    std::string ledger_path_;
    LeaseManager* lease_manager_;
    std::string agent_id_;
    std::map<std::string, std::map<std::string, ExternalEffect>> in_memory_effects_;

    void check_fencing(const std::string& fencing_token) const;
    std::vector<JsonValue> load_ledger() const;
    void append_ledger(const JsonValue& record);
    std::map<std::string, ExternalEffect> current_state(const std::string& agent_id) const;
    ExternalEffect update(const std::string& agent_id, const std::string& operation_id,
                           const std::string& status,
                           const std::optional<JsonValue>& provider_receipt = std::nullopt,
                           std::optional<double> committed_at = std::nullopt);
};

} // namespace hdar
