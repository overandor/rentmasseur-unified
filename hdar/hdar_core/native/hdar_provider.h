// hdar_provider.h — Real VM-backed execution provider via Apple Container CLI.

#ifndef HDAR_PROVIDER_H
#define HDAR_PROVIDER_H

#include <string>
#include <vector>
#include <cstdint>
#include <memory>

namespace hdar {

/// Runtime record: identity and lifecycle state of a VM.
struct RuntimeRecord {
    std::string provider;
    std::string runtime_id;
    std::string image;
    std::string vm_identity;
    std::string cpu_limit;
    std::string memory_limit;
    std::string workspace_mount;
    std::string network_policy;
    double start_timestamp = 0;
    double stop_timestamp = 0;
    double delete_timestamp = 0;
    bool exists = false;
    std::string os;
    std::string arch;
    std::string state;
    std::string post_delete_inspection;
};

/// Execution result from a command inside a VM.
struct ExecutionResult {
    std::string operation_type;
    std::string command;
    int exit_code = -1;
    std::string stdout_text;
    std::string stderr_text;
    double duration_ms = 0;
    bool success = false;
};

/// Real Apple Containerization provider — creates actual Linux VMs.
class AppleContainerProvider {
public:
    AppleContainerProvider();

    /// Create and start a real VM-backed container.
    RuntimeRecord materialize(
        const std::string& runtime_id,
        const std::string& workspace_path,
        const std::string& image = "ubuntu:24.04",
        const std::string& cpu_limit = "2",
        const std::string& memory_limit = "512m",
        const std::string& network_policy = "default"
    );

    /// Execute a command inside a running VM.
    ExecutionResult execute(
        const std::string& runtime_id,
        const std::string& operation_type,
        const std::string& command,
        int timeout = 60
    );

    /// Execute an argument vector without invoking a shell.
    ExecutionResult execute_argv(
        const std::string& runtime_id,
        const std::string& operation_type,
        const std::vector<std::string>& argv,
        int timeout = 60
    );

    /// Stop a VM.
    void stop(const std::string& runtime_id);

    /// Destroy a VM and record absence proof.
    RuntimeRecord destroy(const std::string& runtime_id);

    /// Inspect a VM. Returns JSON dict with "exists" field.
    std::string inspect(const std::string& runtime_id);

    /// List all containers.
    std::vector<std::string> list_runtimes();

    /// Verify a runtime no longer exists — the absence proof.
    bool verify_destruction(const std::string& runtime_id);

    const std::string& name() const { return name_; }

private:
    std::string cli_path_;
    std::string name_ = "apple-container";

    std::string run_cli(const std::vector<std::string>& args, int timeout = 120);

    /// Run CLI with full exit code, stdout, stderr capture via fork/execvp.
    /// Returns exit code; fills out_stdout and out_stderr.
    int run_cli_with_status(const std::vector<std::string>& args,
                            std::string& out_stdout,
                            std::string& out_stderr,
                            int timeout = 120);
};

} // namespace hdar

#endif // HDAR_PROVIDER_H
