#include "hdar/remote_ssh.hpp"
#include <cstdio>
#include <array>
#include <chrono>
#include <filesystem>
#include <sstream>

namespace fs = std::filesystem;

namespace hdar {

RemoteSshProvider::RemoteSshProvider(const std::string& host,
                                      const std::string& ssh_user,
                                      const std::string& remote_base,
                                      int ssh_port)
    : host_(host)
    , ssh_user_(ssh_user)
    , remote_base_(remote_base)
    , ssh_port_(ssh_port) {}

std::string RemoteSshProvider::remote_dir(const std::string& runtime_id) const {
    return remote_base_ + "/" + runtime_id;
}

std::string RemoteSshProvider::ssh_cmd(const std::string& remote_command) const {
    std::string cmd = "ssh";
    if (ssh_port_ != 22) cmd += " -p " + std::to_string(ssh_port_);
    if (!ssh_user_.empty()) cmd += " " + ssh_user_ + "@";
    else cmd += " ";
    cmd += host_ + " '" + remote_command + "'";
    return cmd;
}

std::string RemoteSshProvider::scp_cmd(const std::string& local, const std::string& remote) const {
    std::string cmd = "scp";
    if (ssh_port_ != 22) cmd += " -P " + std::to_string(ssh_port_);
    if (!ssh_user_.empty()) cmd += " " + local + " " + ssh_user_ + "@" + host_ + ":" + remote;
    else cmd += " " + local + " " + host_ + ":" + remote;
    return cmd;
}

std::string RemoteSshProvider::exec_cli(const std::string& cmd, int* exit_code) {
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

RuntimeRecord RemoteSshProvider::materialize(
    const std::string& runtime_id,
    const std::string& workspace_path,
    const std::string& image,
    const std::string& cpu_limit,
    const std::string& memory_limit,
    const std::string& network_policy) {

    RuntimeRecord rec;
    rec.provider = "remote-ssh";
    rec.runtime_id = runtime_id;
    rec.image_digest = image;
    rec.cpu_limit = cpu_limit;
    rec.memory_limit = memory_limit;
    rec.workspace_mount = workspace_path;
    rec.network_policy = network_policy;
    rec.start_timestamp = epoch_seconds();

    std::string rdir = remote_dir(runtime_id);

    int rc = -1;
    exec_cli(ssh_cmd("mkdir -p " + rdir + "/workspace"), &rc);

    if (rc != 0) {
        rec.exists = false;
        runtimes_[runtime_id] = rec;
        return rec;
    }

    if (fs::exists(workspace_path) && fs::is_directory(workspace_path)) {
        std::string tar_cmd = "tar cf - -C " + workspace_path + " . | " +
                              ssh_cmd("tar xf - -C " + rdir + "/workspace");
        exec_cli(tar_cmd, &rc);
    }

    rec.exists = true;
    rec.vm_identity = host_ + ":" + rdir;
    runtimes_[runtime_id] = rec;
    return rec;
}

ExecutionResult RemoteSshProvider::execute(
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

    std::string rdir = remote_dir(runtime_id);
    std::string cmd = ssh_cmd("cd " + rdir + "/workspace && " + command);

    auto start = std::chrono::steady_clock::now();
    int rc = -1;
    result.stdout_text = exec_cli(cmd, &rc);
    result.exit_code = rc;
    result.success = (rc == 0);

    auto end = std::chrono::steady_clock::now();
    result.duration_ms = std::chrono::duration<double, std::milli>(end - start).count();

    return result;
}

RuntimeRecord RemoteSshProvider::stop(const std::string& runtime_id) {
    auto it = runtimes_.find(runtime_id);
    if (it == runtimes_.end())
        throw std::runtime_error("runtime not found: " + runtime_id);

    it->second.stop_timestamp = epoch_seconds();
    return it->second;
}

RuntimeRecord RemoteSshProvider::destroy(const std::string& runtime_id) {
    auto it = runtimes_.find(runtime_id);
    if (it == runtimes_.end())
        throw std::runtime_error("runtime not found: " + runtime_id);

    std::string rdir = remote_dir(runtime_id);
    int rc = -1;
    std::string del_output = exec_cli(ssh_cmd("rm -rf " + rdir), &rc);

    it->second.delete_timestamp = epoch_seconds();
    it->second.exists = false;

    JsonValue inspection = JsonValue::object();
    inspection["exists"] = JsonValue::boolean(false);
    inspection["provider"] = JsonValue::string("remote-ssh");
    inspection["runtime_id"] = JsonValue::string(runtime_id);
    inspection["remote_dir"] = JsonValue::string(rdir);
    inspection["delete_exit_code"] = JsonValue::integer(rc);
    it->second.post_delete_inspection = inspection;

    return it->second;
}

JsonValue RemoteSshProvider::inspect(const std::string& runtime_id) {
    JsonValue v = JsonValue::object();
    v["provider"] = JsonValue::string("remote-ssh");
    v["runtime_id"] = JsonValue::string(runtime_id);

    std::string rdir = remote_dir(runtime_id);
    int rc = -1;
    exec_cli(ssh_cmd("test -d " + rdir + " && echo EXISTS"), &rc);

    v["exists"] = JsonValue::boolean(rc == 0);
    v["remote_dir"] = JsonValue::string(rdir);
    v["host"] = JsonValue::string(host_);

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

std::vector<std::string> RemoteSshProvider::list_runtimes() {
    std::vector<std::string> result;
    int rc = -1;
    std::string output = exec_cli(
        ssh_cmd("ls -1 " + remote_base_ + " 2>/dev/null"), &rc);

    if (rc == 0) {
        std::istringstream iss(output);
        std::string line;
        while (std::getline(iss, line)) {
            while (!line.empty() && (line.back() == '\r' || line.back() == '\n'))
                line.pop_back();
            if (!line.empty())
                result.push_back(line);
        }
    }
    return result;
}

} // namespace hdar
