#pragma once

#include "hdar/provider_base.hpp"
#include <string>

namespace hdar {

// Apple Containerization provider — wraps the `container` CLI
// to create/execute/destroy real ARM64 Linux VM-backed containers.
class AppleContainerProvider : public ProviderBase {
public:
    AppleContainerProvider();

    std::string name() const override { return "apple-container"; }

    RuntimeRecord materialize(
        const std::string& runtime_id,
        const std::string& workspace_path,
        const std::string& image = "",
        const std::string& cpu_limit = "2",
        const std::string& memory_limit = "2g",
        const std::string& network_policy = "none") override;

    ExecutionResult execute(
        const std::string& runtime_id,
        const std::string& operation_type,
        const std::string& command,
        int timeout = 60) override;

    RuntimeRecord stop(const std::string& runtime_id) override;
    RuntimeRecord destroy(const std::string& runtime_id) override;
    JsonValue inspect(const std::string& runtime_id) override;
    std::vector<std::string> list_runtimes() override;

    static bool is_available();

private:
    std::map<std::string, RuntimeRecord> runtimes_;

    static std::string exec_cli(const std::string& cmd, int* exit_code = nullptr);
};

} // namespace hdar
