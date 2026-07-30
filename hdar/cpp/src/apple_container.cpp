#include "hdar/apple_container.hpp"
#include <cstdio>
#include <array>
#include <chrono>
#include <filesystem>

namespace fs = std::filesystem;

namespace hdar {

AppleContainerProvider::AppleContainerProvider() {}

std::string AppleContainerProvider::exec_cli(const std::string& cmd, int* exit_code) {
    std::string result;
    FILE* pipe = popen(cmd.c_str(), "r");
    if (!pipe) {
        if (exit_code) *exit_code = -1;
        return "";
    }
    std::array<char, 4096> buf;
    while (fgets(buf.data(), buf.size(), pipe) != nullptr)
        result += buf.data();
    int status = pclose(pipe);
    if (exit_code) *exit_code = WEXITSTATUS(status);
    return result;
}

bool AppleContainerProvider::is_available() {
    int rc = -1;
    exec_cli("which container 2>/dev/null", &rc);
    return rc == 0;
}

RuntimeRecord AppleContainerProvider::materialize(
    const std::string& runtime_id,
    const std::string& workspace_path,
    const std::string& image,
    const std::string& cpu_limit,
    const std::string& memory_limit,
    const std::string& network_policy) {

    // 1. Create the container (stopped)
    std::string img = image.empty() ? "ubuntu:24.04" : image;
    std::string create_cmd = "container create --name " + runtime_id;
    if (!cpu_limit.empty()) create_cmd += " -c " + cpu_limit;
    if (!memory_limit.empty()) create_cmd += " -m " + memory_limit;
    create_cmd += " " + img + " sleep infinity 2>&1";

    int rc = -1;
    std::string create_out = exec_cli(create_cmd, &rc);

    RuntimeRecord rec;
    rec.provider = "apple-container";
    rec.runtime_id = runtime_id;
    rec.image_digest = img;
    rec.cpu_limit = cpu_limit;
    rec.memory_limit = memory_limit;
    rec.workspace_mount = workspace_path;
    rec.network_policy = network_policy;
    rec.start_timestamp = epoch_seconds();

    if (rc != 0) {
        rec.exists = false;
        runtimes_[runtime_id] = rec;
        return rec;
    }

    // 2. Start the container
    std::string start_cmd = "container start " + runtime_id + " 2>&1";
    rc = -1;
    exec_cli(start_cmd, &rc);

    rec.exists = (rc == 0);

    // 3. Inspect to get VM identity
    if (rec.exists) {
        std::string inspect_cmd = "container inspect " + runtime_id + " 2>/dev/null";
        std::string inspect_out = exec_cli(inspect_cmd);
        // Try to parse JSON inspect output for VM details
        try {
            JsonValue inspect_json = parse_json(inspect_out);
            if (inspect_json.type == JsonValue::Type::Array && !inspect_json.array_val.empty()) {
                auto& cfg = inspect_json.array_val[0].get("configuration");
                rec.vm_identity = cfg.get("id").string_val;
            }
        } catch (...) {
            rec.vm_identity = inspect_out.substr(0, 256);
        }
    }

    runtimes_[runtime_id] = rec;
    return rec;
}

ExecutionResult AppleContainerProvider::execute(
    const std::string& runtime_id,
    const std::string& operation_type,
    const std::string& command,
    int timeout) {

    ExecutionResult result;
    result.operation_type = operation_type;
    result.command = command;

    auto it = runtimes_.find(runtime_id);
    if (it == runtimes_.end() || !it->second.exists) {
        result.stderr_text = "runtime not found or not running";
        return result;
    }

    // container exec <runtime_id> sh -c "<command>"
    std::string cmd = "container exec " + runtime_id + " sh -c \"" + command + "\" 2>&1";

    auto start = std::chrono::steady_clock::now();
    int rc = -1;
    result.stdout_text = exec_cli(cmd, &rc);
    result.exit_code = rc;
    result.success = (rc == 0);

    auto end = std::chrono::steady_clock::now();
    result.duration_ms = std::chrono::duration<double, std::milli>(end - start).count();

    return result;
}

RuntimeRecord AppleContainerProvider::stop(const std::string& runtime_id) {
    auto it = runtimes_.find(runtime_id);
    if (it == runtimes_.end())
        throw std::runtime_error("runtime not found: " + runtime_id);

    exec_cli("container kill " + runtime_id + " 2>/dev/null");
    it->second.stop_timestamp = epoch_seconds();
    return it->second;
}

RuntimeRecord AppleContainerProvider::destroy(const std::string& runtime_id) {
    auto it = runtimes_.find(runtime_id);
    if (it == runtimes_.end())
        throw std::runtime_error("runtime not found: " + runtime_id);

    // Kill if still running, then force delete
    exec_cli("container kill " + runtime_id + " 2>/dev/null");
    int rc = -1;
    std::string del_output = exec_cli("container delete --force " + runtime_id + " 2>&1", &rc);

    it->second.delete_timestamp = epoch_seconds();
    it->second.exists = false;

    // Post-delete inspection — verify container is gone
    int inspect_rc = -1;
    std::string inspect_out = exec_cli("container inspect " + runtime_id + " 2>&1", &inspect_rc);

    JsonValue inspection = JsonValue::object();
    inspection["exists"] = JsonValue::boolean(inspect_rc == 0);
    inspection["provider"] = JsonValue::string("apple-container");
    inspection["runtime_id"] = JsonValue::string(runtime_id);
    inspection["delete_exit_code"] = JsonValue::integer(rc);
    inspection["inspect_exit_code"] = JsonValue::integer(inspect_rc);
    inspection["inspect_output"] = JsonValue::string(inspect_out);
    it->second.post_delete_inspection = inspection;

    return it->second;
}

JsonValue AppleContainerProvider::inspect(const std::string& runtime_id) {
    JsonValue v = JsonValue::object();

    // Check if container exists via CLI
    // container inspect returns non-zero if container doesn't exist
    int rc = -1;
    std::string inspect_out = exec_cli("container inspect " + runtime_id + " 2>/dev/null", &rc);

    bool exists = (rc == 0);

    v["exists"] = JsonValue::boolean(exists);
    v["provider"] = JsonValue::string("apple-container");
    v["runtime_id"] = JsonValue::string(runtime_id);

    if (exists) {
        // Parse inspect output for state
        try {
            JsonValue parsed = parse_json(inspect_out);
            if (parsed.type == JsonValue::Type::Array && !parsed.array_val.empty()) {
                auto& item = parsed.array_val[0];
                v["state"] = item.get("status").get("state");
                v["platform"] = item.get("configuration").get("platform");
            }
        } catch (...) {
            v["inspect_raw"] = JsonValue::string(inspect_out);
        }
    }

    auto it = runtimes_.find(runtime_id);
    if (it != runtimes_.end()) {
        v["start_timestamp"] = JsonValue::number(it->second.start_timestamp);
        if (it->second.stop_timestamp)
            v["stop_timestamp"] = JsonValue::number(*it->second.stop_timestamp);
        if (it->second.delete_timestamp)
            v["delete_timestamp"] = JsonValue::number(*it->second.delete_timestamp);
    }

    return v;
}

std::vector<std::string> AppleContainerProvider::list_runtimes() {
    std::vector<std::string> result;
    std::string output = exec_cli("container list --all --quiet 2>/dev/null");
    std::istringstream iss(output);
    std::string line;
    while (std::getline(iss, line)) {
        while (!line.empty() && (line.back() == '\r' || line.back() == '\n'))
            line.pop_back();
        if (!line.empty())
            result.push_back(line);
    }
    return result;
}

} // namespace hdar
