#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <optional>
#include <map>

namespace hdar {

struct RuntimeRecord {
    std::string provider;
    std::string runtime_id;
    std::string image_digest;
    std::string vm_identity;
    std::string cpu_limit;
    std::string memory_limit;
    std::string workspace_mount;
    std::string network_policy = "none";
    double start_timestamp = 0.0;
    std::optional<double> stop_timestamp;
    std::optional<double> delete_timestamp;
    std::optional<JsonValue> post_delete_inspection;
    bool exists = true;

    JsonValue to_json() const;
    static RuntimeRecord from_json(const JsonValue& v);
};

struct ExecutionResult {
    std::string operation_type;
    std::string command;
    int exit_code = -1;
    std::string stdout_text;
    std::string stderr_text;
    double duration_ms = 0.0;
    std::vector<std::string> files_changed;
    bool success = false;

    JsonValue to_json() const;
};

class ProviderBase {
public:
    virtual ~ProviderBase() = default;

    virtual std::string name() const = 0;

    virtual RuntimeRecord materialize(
        const std::string& runtime_id,
        const std::string& workspace_path,
        const std::string& image = "",
        const std::string& cpu_limit = "2",
        const std::string& memory_limit = "2g",
        const std::string& network_policy = "none") = 0;

    virtual ExecutionResult execute(
        const std::string& runtime_id,
        const std::string& operation_type,
        const std::string& command,
        int timeout = 60) = 0;

    virtual RuntimeRecord stop(const std::string& runtime_id) = 0;
    virtual RuntimeRecord destroy(const std::string& runtime_id) = 0;
    virtual JsonValue inspect(const std::string& runtime_id) = 0;
    virtual std::vector<std::string> list_runtimes() = 0;

    bool verify_destruction(const std::string& runtime_id);
};

} // namespace hdar
