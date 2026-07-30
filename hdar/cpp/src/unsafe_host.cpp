#include "hdar/unsafe_host.hpp"
#include <cstdlib>
#include <chrono>
#include <filesystem>

namespace fs = std::filesystem;

namespace hdar {

UnsafeHostProvider::UnsafeHostProvider(const std::string& root)
    : sandbox_root_(root) {
    fs::create_directories(sandbox_root_);
}

RuntimeRecord UnsafeHostProvider::materialize(
    const std::string& runtime_id,
    const std::string& workspace_path,
    const std::string& image,
    const std::string& cpu_limit,
    const std::string& memory_limit,
    const std::string& network_policy) {

    std::string dir = runtime_dir(runtime_id);
    fs::create_directories(dir);

    // Copy workspace into sandbox
    if (fs::exists(workspace_path) && fs::is_directory(workspace_path)) {
        for (const auto& entry : fs::recursive_directory_iterator(workspace_path)) {
            if (entry.is_regular_file()) {
                std::string rel = fs::relative(entry.path(), workspace_path).string();
                std::string dest = dir + "/" + rel;
                fs::create_directories(fs::path(dest).parent_path());
                fs::copy_file(entry.path(), dest, fs::copy_options::overwrite_existing);
            }
        }
    }

    RuntimeRecord rec;
    rec.provider = "unsafe-host";
    rec.runtime_id = runtime_id;
    rec.cpu_limit = cpu_limit;
    rec.memory_limit = memory_limit;
    rec.workspace_mount = dir;
    rec.network_policy = network_policy;
    rec.start_timestamp = epoch_seconds();
    rec.exists = true;

    runtimes_[runtime_id] = rec;
    return rec;
}

ExecutionResult UnsafeHostProvider::execute(
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

    std::string dir = runtime_dir(runtime_id);
    std::string full_cmd = "cd " + dir + " && " + command + " 2>&1";

    auto start = std::chrono::steady_clock::now();

    FILE* pipe = popen(full_cmd.c_str(), "r");
    if (!pipe) {
        result.stderr_text = "popen failed";
        return result;
    }

    char buffer[4096];
    std::string output;
    while (fgets(buffer, sizeof(buffer), pipe) != nullptr)
        output += buffer;

    int status = pclose(pipe);
    result.exit_code = WEXITSTATUS(status);
    result.stdout_text = output;
    result.success = (result.exit_code == 0);

    auto end = std::chrono::steady_clock::now();
    result.duration_ms = std::chrono::duration<double, std::milli>(end - start).count();

    return result;
}

RuntimeRecord UnsafeHostProvider::stop(const std::string& runtime_id) {
    auto it = runtimes_.find(runtime_id);
    if (it == runtimes_.end())
        throw std::runtime_error("runtime not found: " + runtime_id);

    it->second.stop_timestamp = epoch_seconds();
    return it->second;
}

RuntimeRecord UnsafeHostProvider::destroy(const std::string& runtime_id) {
    auto it = runtimes_.find(runtime_id);
    if (it == runtimes_.end())
        throw std::runtime_error("runtime not found: " + runtime_id);

    std::string dir = runtime_dir(runtime_id);
    if (fs::exists(dir))
        fs::remove_all(dir);

    it->second.delete_timestamp = epoch_seconds();
    it->second.exists = false;

    JsonValue inspection = JsonValue::object();
    inspection["exists"] = JsonValue::boolean(false);
    inspection["provider"] = JsonValue::string("unsafe-host");
    inspection["runtime_id"] = JsonValue::string(runtime_id);
    inspection["sandbox_dir"] = JsonValue::string(dir);
    inspection["dir_exists"] = JsonValue::boolean(false);
    it->second.post_delete_inspection = inspection;

    return it->second;
}

JsonValue UnsafeHostProvider::inspect(const std::string& runtime_id) {
    auto it = runtimes_.find(runtime_id);
    JsonValue v = JsonValue::object();

    if (it == runtimes_.end()) {
        v["exists"] = JsonValue::boolean(false);
        v["provider"] = JsonValue::string("unsafe-host");
        v["runtime_id"] = JsonValue::string(runtime_id);
        return v;
    }

    bool dir_exists = fs::exists(runtime_dir(runtime_id));
    v["exists"] = JsonValue::boolean(it->second.exists && dir_exists);
    v["provider"] = JsonValue::string("unsafe-host");
    v["runtime_id"] = JsonValue::string(runtime_id);
    v["sandbox_dir"] = JsonValue::string(runtime_dir(runtime_id));
    v["dir_exists"] = JsonValue::boolean(dir_exists);
    return v;
}

std::vector<std::string> UnsafeHostProvider::list_runtimes() {
    std::vector<std::string> result;
    for (const auto& [id, rec] : runtimes_)
        if (rec.exists && fs::exists(runtime_dir(id)))
            result.push_back(id);
    return result;
}

} // namespace hdar
