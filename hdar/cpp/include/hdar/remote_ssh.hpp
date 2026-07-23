#pragma once

#include "hdar/provider_base.hpp"
#include <string>

namespace hdar {

class RemoteSshProvider : public ProviderBase {
public:
    RemoteSshProvider(const std::string& host,
                      const std::string& ssh_user = "",
                      const std::string& remote_base = "/tmp/hdar-remote",
                      int ssh_port = 22);

    std::string name() const override { return "remote-ssh"; }

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

    const std::string& host() const { return host_; }

private:
    std::string host_;
    std::string ssh_user_;
    std::string remote_base_;
    int ssh_port_;
    std::map<std::string, RuntimeRecord> runtimes_;

    std::string remote_dir(const std::string& runtime_id) const;
    std::string ssh_cmd(const std::string& remote_command) const;
    std::string scp_cmd(const std::string& local, const std::string& remote) const;
    static std::string exec_cli(const std::string& cmd, int* exit_code = nullptr);
};

} // namespace hdar
