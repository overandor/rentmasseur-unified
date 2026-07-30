#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <map>
#include <utility>

namespace hdar {

struct Capability {
    std::string name;
    std::string scope;
    bool granted = true;
    std::map<std::string, std::string> constraints;

    JsonValue to_json() const;
    static Capability from_json(const JsonValue& v);
};

bool is_scope_broader(const std::string& src_scope, const std::string& dst_scope);
bool is_budget_higher(const std::string& src, const std::string& dst);

class CapabilityCompiler {
public:
    CapabilityCompiler();

    std::pair<std::vector<Capability>, std::vector<std::string>>
    compile(const std::vector<Capability>& source_caps,
            const std::map<std::string, std::string>& destination_policy);

    std::pair<bool, std::vector<std::string>>
    verify_non_expansion(const std::vector<Capability>& source_caps,
                         const std::vector<Capability>& dest_caps) const;

private:
    std::pair<std::optional<Capability>, std::string>
    map_filesystem(const Capability& src, const std::map<std::string, std::string>& policy);
    std::pair<std::optional<Capability>, std::string>
    map_network(const Capability& src, const std::map<std::string, std::string>& policy);
    std::pair<std::optional<Capability>, std::string>
    map_budget(const Capability& src, const std::map<std::string, std::string>& policy);
    std::pair<std::optional<Capability>, std::string>
    map_deploy(const Capability& src, const std::map<std::string, std::string>& policy);
    std::pair<std::optional<Capability>, std::string>
    map_shell(const Capability& src, const std::map<std::string, std::string>& policy);
};

} // namespace hdar
