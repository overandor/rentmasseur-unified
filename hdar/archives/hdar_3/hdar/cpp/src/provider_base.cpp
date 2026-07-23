#include "hdar/provider_base.hpp"

namespace hdar {

JsonValue RuntimeRecord::to_json() const {
    JsonValue v = JsonValue::object();
    v["provider"] = JsonValue::string(provider);
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["image_digest"] = JsonValue::string(image_digest);
    v["vm_identity"] = JsonValue::string(vm_identity);
    v["cpu_limit"] = JsonValue::string(cpu_limit);
    v["memory_limit"] = JsonValue::string(memory_limit);
    v["workspace_mount"] = JsonValue::string(workspace_mount);
    v["network_policy"] = JsonValue::string(network_policy);
    v["start_timestamp"] = JsonValue::number(start_timestamp);
    if (stop_timestamp)
        v["stop_timestamp"] = JsonValue::number(*stop_timestamp);
    else
        v["stop_timestamp"] = JsonValue::null();
    if (delete_timestamp)
        v["delete_timestamp"] = JsonValue::number(*delete_timestamp);
    else
        v["delete_timestamp"] = JsonValue::null();
    if (post_delete_inspection)
        v["post_delete_inspection"] = *post_delete_inspection;
    else
        v["post_delete_inspection"] = JsonValue::null();
    v["exists"] = JsonValue::boolean(exists);
    return v;
}

RuntimeRecord RuntimeRecord::from_json(const JsonValue& v) {
    RuntimeRecord r;
    r.provider = v.get("provider").string_val;
    r.runtime_id = v.get("runtime_id").string_val;
    r.image_digest = v.get("image_digest").string_val;
    r.vm_identity = v.get("vm_identity").string_val;
    r.cpu_limit = v.get("cpu_limit").string_val;
    r.memory_limit = v.get("memory_limit").string_val;
    r.workspace_mount = v.get("workspace_mount").string_val;
    r.network_policy = v.get("network_policy").string_val;
    r.start_timestamp = v.get("start_timestamp").double_val;
    const auto& st = v.get("stop_timestamp");
    if (st.type == JsonValue::Type::Double || st.type == JsonValue::Type::Int)
        r.stop_timestamp = st.double_val;
    const auto& dt = v.get("delete_timestamp");
    if (dt.type == JsonValue::Type::Double || dt.type == JsonValue::Type::Int)
        r.delete_timestamp = dt.double_val;
    const auto& pdi = v.get("post_delete_inspection");
    if (pdi.type != JsonValue::Type::Null)
        r.post_delete_inspection = pdi;
    r.exists = v.get("exists").bool_val;
    return r;
}

JsonValue ExecutionResult::to_json() const {
    JsonValue v = JsonValue::object();
    v["operation_type"] = JsonValue::string(operation_type);
    v["command"] = JsonValue::string(command);
    v["exit_code"] = JsonValue::integer(exit_code);
    v["stdout"] = JsonValue::string(stdout_text);
    v["stderr"] = JsonValue::string(stderr_text);
    v["duration_ms"] = JsonValue::number(duration_ms);
    JsonValue fc = JsonValue::array();
    for (const auto& f : files_changed)
        fc.push_back(JsonValue::string(f));
    v["files_changed"] = std::move(fc);
    v["success"] = JsonValue::boolean(success);
    return v;
}

bool ProviderBase::verify_destruction(const std::string& runtime_id) {
    auto listing = list_runtimes();
    for (const auto& id : listing)
        if (id == runtime_id) return false;
    auto insp = inspect(runtime_id);
    return !insp.get("exists").bool_val;
}

} // namespace hdar
