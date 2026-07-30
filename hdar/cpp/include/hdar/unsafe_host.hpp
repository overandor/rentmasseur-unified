#pragma once

#include "hdar/provider_base.hpp"
#include <filesystem>

namespace hdar {

class UnsafeHostProvider : public ProviderBase {
public:
    explicit UnsafeHostProvider(const std::string& sandbox_root);

    std::string name() const override { return "unsafe-host"; }

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

private:
    std::string sandbox_root_;
    std::map<std::string, RuntimeRecord> runtimes_;

    std::string runtime_dir(const std::string& runtime_id) const {
        return sandbox_root_ + "/" + runtime_id;
    }
};

} // namespace hdar
