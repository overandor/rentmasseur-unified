#include "hdar/effects.hpp"
#include "hdar/lease.hpp"
#include <fstream>
#include <sstream>
#include <filesystem>

namespace hdar {

// ── ExternalEffect ────────────────────────────────────────────

bool ExternalEffect::is_blocking() const {
    return BLOCKING_STATES.count(status) > 0;
}

bool ExternalEffect::is_terminal() const {
    return TERMINAL_STATES.count(status) > 0;
}

JsonValue ExternalEffect::to_json() const {
    JsonValue v = JsonValue::object();
    v["operation_id"] = JsonValue::string(operation_id);
    v["intent_digest"] = JsonValue::string(intent_digest);
    v["capability_used"] = JsonValue::string(capability_used);
    v["request_digest"] = JsonValue::string(request_digest);
    v["status"] = JsonValue::string(status);
    if (provider_receipt)
        v["provider_receipt"] = *provider_receipt;
    else
        v["provider_receipt"] = JsonValue::null();
    if (reconciliation_method)
        v["reconciliation_method"] = JsonValue::string(*reconciliation_method);
    else
        v["reconciliation_method"] = JsonValue::null();
    v["created_at"] = JsonValue::number(created_at);
    if (committed_at)
        v["committed_at"] = JsonValue::number(*committed_at);
    else
        v["committed_at"] = JsonValue::null();
    return v;
}

ExternalEffect ExternalEffect::from_json(const JsonValue& v) {
    ExternalEffect e;
    e.operation_id = v.get("operation_id").string_val;
    e.intent_digest = v.get("intent_digest").string_val;
    e.capability_used = v.get("capability_used").string_val;
    e.request_digest = v.get("request_digest").string_val;
    e.status = v.get("status").string_val;
    const auto& pr = v.get("provider_receipt");
    if (pr.type != JsonValue::Type::Null)
        e.provider_receipt = pr;
    const auto& rm = v.get("reconciliation_method");
    if (rm.type == JsonValue::Type::String)
        e.reconciliation_method = rm.string_val;
    e.created_at = v.get("created_at").double_val;
    const auto& ca = v.get("committed_at");
    if (ca.type == JsonValue::Type::Double || ca.type == JsonValue::Type::Int)
        e.committed_at = ca.double_val;
    return e;
}

// ── EffectRegistry ────────────────────────────────────────────

EffectRegistry::EffectRegistry(const std::string& path, LeaseManager* lm,
                                const std::string& aid)
    : ledger_path_(path), lease_manager_(lm), agent_id_(aid) {
    auto parent = std::filesystem::path(path).parent_path();
    if (!parent.empty())
        std::filesystem::create_directories(parent);
}

void EffectRegistry::check_fencing(const std::string& token) const {
    if (lease_manager_ && !agent_id_.empty()) {
        if (token.empty())
            throw std::runtime_error("fencing token required but not provided");
        if (!lease_manager_->validate_token(agent_id_, token))
            throw std::runtime_error(
                "stale or invalid fencing token — this runtime's lease "
                "generation is no longer authoritative");
    }
}

std::vector<JsonValue> EffectRegistry::load_ledger() const {
    std::vector<JsonValue> records;
    if (!std::filesystem::exists(ledger_path_))
        return records;
    std::ifstream f(ledger_path_);
    std::string line;
    while (std::getline(f, line)) {
        if (line.empty()) continue;
        try {
            records.push_back(parse_json(line));
        } catch (const std::exception&) {
            // Skip malformed lines
        }
    }
    return records;
}

void EffectRegistry::append_ledger(const JsonValue& record) {
    std::ofstream f(ledger_path_, std::ios::app);
    f << canonical_json(record) << "\n";
}

std::map<std::string, ExternalEffect> EffectRegistry::current_state(
    const std::string& aid) const {
    std::map<std::string, ExternalEffect> state;
    auto it = in_memory_effects_.find(aid);
    if (it != in_memory_effects_.end())
        state = it->second;
    return state;
}

ExternalEffect EffectRegistry::register_effect(
    const std::string& aid,
    const std::string& capability,
    const std::vector<uint8_t>& payload,
    const std::string& op_id,
    const std::string& fencing_token) {

    check_fencing(fencing_token);

    std::string operation_id = op_id.empty() ? ("op-" + generate_uuid_hex().substr(0, 12)) : op_id;
    std::string digest = sha256_hex(payload);

    auto cur = current_state(aid);
    auto it = cur.find(operation_id);
    if (it != cur.end() && it->second.status == "committed") {
        ExternalEffect e;
        e.operation_id = operation_id;
        e.intent_digest = digest;
        e.capability_used = capability;
        e.request_digest = digest;
        e.status = "committed";
        e.committed_at = it->second.committed_at;
        in_memory_effects_[aid][operation_id] = e;
        return e;
    }

    ExternalEffect e;
    e.operation_id = operation_id;
    e.intent_digest = digest;
    e.capability_used = capability;
    e.request_digest = digest;
    e.status = "starting";
    e.created_at = epoch_seconds();

    JsonValue record = JsonValue::object();
    record["agent"] = JsonValue::string(aid);
    // Merge with effect fields
    JsonValue effect_json = e.to_json();
    for (const auto& [k, v] : effect_json.object_val)
        record[k] = v;
    append_ledger(record);

    in_memory_effects_[aid][operation_id] = e;
    return e;
}

ExternalEffect EffectRegistry::submit(const std::string& aid, const std::string& op_id,
                                       const std::string& fencing_token) {
    check_fencing(fencing_token);
    return update(aid, op_id, "submitted");
}

ExternalEffect EffectRegistry::commit(const std::string& aid, const std::string& op_id,
                                       const JsonValue& receipt, const std::string& fencing_token) {
    check_fencing(fencing_token);
    std::optional<JsonValue> pr;
    if (receipt.type != JsonValue::Type::Null)
        pr = receipt;
    return update(aid, op_id, "committed", pr, epoch_seconds());
}

ExternalEffect EffectRegistry::mark_unknown(const std::string& aid, const std::string& op_id,
                                               const std::string& fencing_token) {
    check_fencing(fencing_token);
    return update(aid, op_id, "unknown");
}

ExternalEffect EffectRegistry::cancel(const std::string& aid, const std::string& op_id,
                                         const std::string& fencing_token) {
    check_fencing(fencing_token);
    return update(aid, op_id, "cancelled");
}

ExternalEffect EffectRegistry::update(const std::string& aid, const std::string& op_id,
                                       const std::string& status,
                                       const std::optional<JsonValue>& provider_receipt,
                                       std::optional<double> committed_at) {
    auto cur = current_state(aid);
    auto it = cur.find(op_id);
    if (it == cur.end())
        throw std::runtime_error("unknown operation_id: " + op_id);

    const auto& existing = it->second;
    ExternalEffect updated;
    updated.operation_id = op_id;
    updated.intent_digest = existing.intent_digest;
    updated.capability_used = existing.capability_used;
    updated.request_digest = existing.request_digest;
    updated.status = status;
    updated.provider_receipt = provider_receipt.has_value() ? provider_receipt : existing.provider_receipt;
    updated.reconciliation_method = existing.reconciliation_method;
    updated.created_at = existing.created_at;
    updated.committed_at = committed_at.has_value() ? committed_at : existing.committed_at;

    JsonValue record = JsonValue::object();
    record["agent"] = JsonValue::string(aid);
    JsonValue effect_json = updated.to_json();
    for (const auto& [k, v] : effect_json.object_val)
        record[k] = v;
    append_ledger(record);

    in_memory_effects_[aid][op_id] = updated;
    return updated;
}

JsonValue EffectRegistry::check_quiescence(const std::string& aid) const {
    auto cur = current_state(aid);
    std::vector<ExternalEffect> blocking;
    for (const auto& [id, e] : cur)
        if (e.is_blocking()) blocking.push_back(e);

    JsonValue result = JsonValue::object();
    result["agent"] = JsonValue::string(aid);
    result["quiescent"] = JsonValue::boolean(blocking.empty());

    JsonValue blocking_arr = JsonValue::array();
    for (const auto& e : blocking)
        blocking_arr.push_back(e.to_json());
    result["blocking_effects"] = std::move(blocking_arr);

    result["verdict"] = JsonValue::string(
        blocking.empty() ? "SAFE TO SEAL" : "REFUSE TO SEAL — external effects in flight");
    result["effects_total"] = JsonValue::integer(static_cast<int64_t>(cur.size()));

    return result;
}

JsonValue EffectRegistry::reconcile(const std::string& aid,
                                    std::function<std::string(const std::string&, const ExternalEffect&)> probe_fn) {
    auto cur = current_state(aid);
    JsonValue results = JsonValue::array();
    int reconciled = 0;

    for (const auto& [id, e] : cur) {
        if (e.status != "unknown") continue;

        std::string truth = probe_fn(id, e);
        if (truth == "committed")
            commit(aid, id);
        else if (truth == "cancelled")
            cancel(aid, id);
        else if (truth == "proven_not_started")
            update(aid, id, "proven_not_started");
        else
            update(aid, id, "reconciliation_failed");

        JsonValue r = JsonValue::object();
        r["operation_id"] = JsonValue::string(id);
        r["capability_used"] = JsonValue::string(e.capability_used);
        r["resolved_to"] = JsonValue::string(truth);
        r["action"] = JsonValue::string(
            truth == "committed" ? "do NOT re-execute" :
            truth == "proven_not_started" ? "safe to retry" :
            "reconciliation failed — manual review required");
        results.push_back(std::move(r));
        ++reconciled;
    }

    auto q = check_quiescence(aid);
    JsonValue result = JsonValue::object();
    result["agent"] = JsonValue::string(aid);
    result["reconciled"] = JsonValue::integer(reconciled);
    result["results"] = std::move(results);
    result["now_quiescent"] = q.get("quiescent");
    return result;
}

bool EffectRegistry::is_duplicate(const std::string& aid, const std::string& op_id) const {
    auto cur = current_state(aid);
    auto it = cur.find(op_id);
    return it != cur.end() && it->second.status == "committed";
}

} // namespace hdar
