// hdar_provider.cpp — Real VM-backed execution via Apple Container CLI.
// Uses fork()/execvp() for proper exit code, stderr, and timeout capture.

#include "hdar_provider.h"
#include <cstdio>
#include <cstdlib>
#include <array>
#include <sstream>
#include <sys/stat.h>
#include <sys/wait.h>
#include <unistd.h>
#include <signal.h>
#include <fcntl.h>
#include <chrono>
#include <cstring>

namespace hdar {

static volatile sig_atomic_t s_alarm_fired = 0;
static void alarm_handler(int sig) {
    (void)sig;
    s_alarm_fired = 1;
}

int AppleContainerProvider::run_cli_with_status(
    const std::vector<std::string>& args,
    std::string& out_stdout,
    std::string& out_stderr,
    int timeout
) {
    int stdout_pipe[2], stderr_pipe[2];
    if (pipe(stdout_pipe) != 0 || pipe(stderr_pipe) != 0) {
        out_stderr = "pipe() failed";
        return -1;
    }

    pid_t pid = fork();
    if (pid < 0) {
        out_stderr = "fork() failed";
        close(stdout_pipe[0]); close(stdout_pipe[1]);
        close(stderr_pipe[0]); close(stderr_pipe[1]);
        return -1;
    }

    if (pid == 0) {
        // Child
        close(stdout_pipe[0]); close(stderr_pipe[0]);
        dup2(stdout_pipe[1], STDOUT_FILENO);
        dup2(stderr_pipe[1], STDERR_FILENO);
        close(stdout_pipe[1]); close(stderr_pipe[1]);

        // Build argv array
        std::vector<char*> argv;
        argv.push_back(const_cast<char*>(cli_path_.c_str()));
        for (const auto& a : args) {
            argv.push_back(const_cast<char*>(a.c_str()));
        }
        argv.push_back(nullptr);

        execvp(cli_path_.c_str(), argv.data());
        // execvp only returns on failure
        _exit(127);
    }

    // Parent
    close(stdout_pipe[1]); close(stderr_pipe[1]);

    // Set up timeout via alarm
    s_alarm_fired = 0;
    struct sigaction old_sa;
    struct sigaction sa;
    memset(&sa, 0, sizeof(sa));
    sa.sa_handler = alarm_handler;
    sigaction(SIGALRM, &sa, &old_sa);
    alarm(timeout);

    // Read stdout and stderr
    std::array<char, 4096> buf;
    fd_set rfds;
    int maxfd = (stdout_pipe[0] > stderr_pipe[0]) ? stdout_pipe[0] : stderr_pipe[0];
    bool stdout_open = true, stderr_open = true;

    while ((stdout_open || stderr_open) && !s_alarm_fired) {
        FD_ZERO(&rfds);
        if (stdout_open) FD_SET(stdout_pipe[0], &rfds);
        if (stderr_open) FD_SET(stderr_pipe[0], &rfds);

        int sel = select(maxfd + 1, &rfds, nullptr, nullptr, nullptr);
        if (sel < 0) {
            if (errno == EINTR) continue;
            break;
        }

        if (stdout_open && FD_ISSET(stdout_pipe[0], &rfds)) {
            ssize_t n = read(stdout_pipe[0], buf.data(), buf.size());
            if (n <= 0) { stdout_open = false; }
            else { out_stdout.append(buf.data(), n); }
        }
        if (stderr_open && FD_ISSET(stderr_pipe[0], &rfds)) {
            ssize_t n = read(stderr_pipe[0], buf.data(), buf.size());
            if (n <= 0) { stderr_open = false; }
            else { out_stderr.append(buf.data(), n); }
        }
    }

    alarm(0);
    sigaction(SIGALRM, &old_sa, nullptr);

    close(stdout_pipe[0]); close(stderr_pipe[0]);

    int status = 0;
    if (s_alarm_fired) {
        kill(pid, SIGKILL);
        waitpid(pid, &status, 0);
        out_stderr += "\n[TIMEOUT: process killed after " + std::to_string(timeout) + "s]";
        return -2;  // timeout exit code
    }

    waitpid(pid, &status, 0);
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    } else if (WIFSIGNALED(status)) {
        out_stderr += "\n[killed by signal " + std::to_string(WTERMSIG(status)) + "]";
        return -3;
    }
    return -1;
}

AppleContainerProvider::AppleContainerProvider() {
    const char* fallbacks[] = {"/opt/homebrew/bin/container", "/usr/local/bin/container", "/usr/bin/container", nullptr};
    for (int i = 0; fallbacks[i]; ++i) {
        struct stat st;
        if (stat(fallbacks[i], &st) == 0 && (st.st_mode & S_IXUSR)) {
            cli_path_ = fallbacks[i];
            break;
        }
    }

    if (cli_path_.empty()) {
        fprintf(stderr, "FATAL: Apple 'container' CLI not found. Install with: brew install container\n");
    }
}

std::string AppleContainerProvider::run_cli(const std::vector<std::string>& args, int timeout) {
    std::string out, err;
    int rc = run_cli_with_status(args, out, err, timeout);
    // Merge stderr into stdout for backward compat with callers that check output text
    if (!err.empty()) {
        if (!out.empty()) out += "\n";
        out += err;
    }
    return out;
}

RuntimeRecord AppleContainerProvider::materialize(
    const std::string& runtime_id,
    const std::string& workspace_path,
    const std::string& image,
    const std::string& cpu_limit,
    const std::string& memory_limit,
    const std::string& network_policy
) {
    RuntimeRecord record;
    record.provider = name_;
    record.runtime_id = runtime_id;
    record.image = image;
    record.cpu_limit = cpu_limit;
    record.memory_limit = memory_limit;
    record.workspace_mount = workspace_path;
    record.network_policy = network_policy;
    record.start_timestamp = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    std::vector<std::string> args = {"run", "--name", runtime_id, "-c", cpu_limit,
                                      "-m", memory_limit, "-d"};
    if (!workspace_path.empty()) {
        args.push_back("-v");
        args.push_back(workspace_path + ":/workspace");
    }
    if (network_policy == "none") {
        args.push_back("--network");
        args.push_back("none");
    }
    args.push_back(image);
    args.push_back("sleep");
    args.push_back("infinity");

    std::string output = run_cli(args, 60);

    // Inspect to verify
    std::string insp = inspect(runtime_id);
    if (insp.find("\"exists\":true") != std::string::npos) {
        record.exists = true;
        // Parse fields from our simplified JSON
        auto extract = [&](const std::string& key) -> std::string {
            std::string pat = "\"" + key + "\":\"";
            size_t pos = insp.find(pat);
            if (pos == std::string::npos) return "";
            size_t s = pos + pat.size();
            size_t e = insp.find("\"", s);
            return insp.substr(s, e - s);
        };
        record.os = extract("os");
        record.arch = extract("arch");
        record.state = extract("state");
        record.vm_identity = extract("id");
        if (record.vm_identity.empty()) record.vm_identity = runtime_id;
    }

    return record;
}

ExecutionResult AppleContainerProvider::execute(
    const std::string& runtime_id,
    const std::string& operation_type,
    const std::string& command,
    int timeout
) {
    // Shell strings are intentionally rejected. Callers must provide argv.
    ExecutionResult result;
    result.operation_type = operation_type;
    result.command = command;
    result.stderr_text = "shell command execution is disabled; use execute_argv";
    result.exit_code = -4;
    return result;
}

ExecutionResult AppleContainerProvider::execute_argv(
    const std::string& runtime_id,
    const std::string& operation_type,
    const std::vector<std::string>& argv,
    int timeout
) {
    ExecutionResult result;
    result.operation_type = operation_type;
    for (size_t i = 0; i < argv.size(); ++i) {
        if (i) result.command += " ";
        result.command += argv[i];
    }

    double start = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()).count();

    if (argv.empty()) {
        result.stderr_text = "empty argv";
        result.exit_code = -4;
        return result;
    }
    std::vector<std::string> exec_args = {"exec", runtime_id};
    exec_args.insert(exec_args.end(), argv.begin(), argv.end());
    std::string out, err;
    int rc = run_cli_with_status(exec_args, out, err, timeout);

    double end = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    result.duration_ms = (end - start) * 1000;
    result.stdout_text = out;
    result.stderr_text = err;
    result.exit_code = rc;
    result.success = (rc == 0);

    return result;
}

void AppleContainerProvider::stop(const std::string& runtime_id) {
    std::string out, err;
    int rc = run_cli_with_status({"stop", runtime_id}, out, err, 30);
    if (rc != 0 && rc != -2) {
        std::string combined = out + "\n" + err;
        if (combined.find("not found") == std::string::npos &&
            combined.find("not running") == std::string::npos &&
            combined.find("already stopped") == std::string::npos) {
            throw std::runtime_error("container stop failed for '" + runtime_id +
                                     "': exit=" + std::to_string(rc) +
                                     " stderr=" + err);
        }
    }
}

RuntimeRecord AppleContainerProvider::destroy(const std::string& runtime_id) {
    RuntimeRecord record;
    record.provider = name_;
    record.runtime_id = runtime_id;

    stop(runtime_id);

    std::string rm_out, rm_err;
    int rm_rc = run_cli_with_status({"rm", runtime_id}, rm_out, rm_err, 30);
    if (rm_rc != 0) {
        std::string combined = rm_out + "\n" + rm_err;
        if (combined.find("not found") == std::string::npos &&
            combined.find("no such") == std::string::npos) {
            throw std::runtime_error("container rm failed for '" + runtime_id +
                                     "': exit=" + std::to_string(rm_rc) +
                                     " stderr=" + rm_err);
        }
    }
    record.delete_timestamp = std::chrono::duration<double>(
        std::chrono::system_clock::now().time_since_epoch()).count();
    record.exists = false;
    record.post_delete_inspection = inspect(runtime_id);

    return record;
}

std::string AppleContainerProvider::inspect(const std::string& runtime_id) {
    std::vector<std::string> args = {"inspect", runtime_id};
    std::string out, err;
    int rc = run_cli_with_status(args, out, err, 30);

    std::string output = out;
    if (!err.empty()) output += "\n" + err;

    if (rc != 0) {
        return "{\"exists\":false,\"error\":\"container not found: " + runtime_id + "\"}";
    }

    // Try to parse JSON array
    if (output.find("[") != std::string::npos) {
        if (output.find("\"id\"") != std::string::npos || output.find("\"status\"") != std::string::npos) {
            std::string result = "{\"exists\":true";

            // Extract OS
            size_t os_pos = output.find("\"os\"");
            if (os_pos != std::string::npos) {
                size_t s = output.find("\"", os_pos + 4) + 1;
                size_t e = output.find("\"", s);
                result += ",\"os\":\"" + output.substr(s, e - s) + "\"";
            } else {
                result += ",\"os\":\"linux\"";
            }

            // Extract architecture
            size_t arch_pos = output.find("\"architecture\"");
            if (arch_pos != std::string::npos) {
                size_t s = output.find("\"", arch_pos + 14) + 1;
                size_t e = output.find("\"", s);
                result += ",\"arch\":\"" + output.substr(s, e - s) + "\"";
            } else {
                result += ",\"arch\":\"aarch64\"";
            }

            // Extract state
            size_t state_pos = output.find("\"state\"");
            if (state_pos != std::string::npos) {
                size_t s = output.find("\"", state_pos + 7) + 1;
                size_t e = output.find("\"", s);
                result += ",\"state\":\"" + output.substr(s, e - s) + "\"";
            }

            // Extract id
            size_t id_pos = output.find("\"id\"");
            if (id_pos != std::string::npos) {
                size_t s = output.find("\"", id_pos + 4) + 1;
                size_t e = output.find("\"", s);
                result += ",\"id\":\"" + output.substr(s, e - s) + "\"";
            }

            result += "}";
            return result;
        }
    }

    return "{\"exists\":false,\"error\":\"invalid inspect response\"}";
}

std::vector<std::string> AppleContainerProvider::list_runtimes() {
    std::vector<std::string> ids;
    std::string output = run_cli({"ls", "-a"}, 30);

    std::istringstream ss(output);
    std::string line;
    bool first = true;
    while (std::getline(ss, line)) {
        if (first) { first = false; continue; }
        std::istringstream ls(line);
        std::string id;
        if (ls >> id) ids.push_back(id);
    }
    return ids;
}

bool AppleContainerProvider::verify_destruction(const std::string& runtime_id) {
    auto runtimes = list_runtimes();
    for (const auto& r : runtimes) {
        if (r == runtime_id) return false;
    }
    std::string insp = inspect(runtime_id);
    return insp.find("\"exists\":false") != std::string::npos;
}

} // namespace hdar
