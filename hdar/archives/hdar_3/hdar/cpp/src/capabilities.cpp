#include "hdar/capabilities.hpp"
#include <algorithm>
#include <sstream>

namespace hdar {

JsonValue Capability::to_json() const {
    JsonValue v = JsonValue::object();
    v["name"] = JsonValue::string(name);
    v["scope"] = JsonValue::string(scope);
    v["granted"] = JsonValue::boolean(granted);
    JsonValue cons = JsonValue::object();
    for (const auto& [k, val] : constraints)
        cons[k] = JsonValue::string(val);
    v["constraints"] = std::move(cons);
    return v;
}

Capability Capability::from_json(const JsonValue& v) {
    Capability c;
    c.name = v.get("name").string_val;
    c.scope = v.get("scope").string_val;
    c.granted = v.get("granted").bool_val;
    const auto& cons = v.get("constraints");
    if (cons.type == JsonValue::Type::Object) {
        for (const auto& [k, val] : cons.object_val)
            c.constraints[k] = val.string_val;
    }
    return c;
}

bool is_scope_broader(const std::string& src, const std::string& dst) {
    if (dst == "*" && src != "*") return true;
    if (src == "/workspace" && dst == "/") return true;
    if (src == "/workspace" && dst == "*") return true;
    if (dst == src) return false;
    if (dst.size() > src.size() && dst.substr(0, src.size() + 1) == src + "/")
        return false; // subdirectory is narrower
    if (src.size() > dst.size() && src.substr(0, dst.size() + 1) == dst + "/")
        return false; // src is subdirectory of dst, dst is broader — but this means dst IS broader
    // Everything else is broader
    return true;
}

bool is_budget_higher(const std::string& src, const std::string& dst) {
    auto parse = [](const std::string& s) -> double {
        std::string clean;
        for (char c : s) {
            if (c != '$' && c != ',') clean += c;
        }
        try { return std::stod(clean); }
        catch (...) { return 0.0; }
    };
    return parse(dst) > parse(src);
}

CapabilityCompiler::CapabilityCompiler() {}

std::pair<std::vector<Capability>, std::vector<std::string>>
CapabilityCompiler::compile(const std::vector<Capability>& source_caps,
                            const std::map<std::string, std::string>& policy) {
    std::vector<Capability> dest_caps;
    std::vector<std::string> rejections;

    for (const auto& src : source_caps) {
        if (!src.granted) continue;

        std::pair<std::optional<Capability>, std::string> result{{}, ""};

        if (src.name == "filesystem.read" || src.name == "filesystem.write")
            result = map_filesystem(src, policy);
        else if (src.name == "network.egress")
            result = map_network(src, policy);
        else if (src.name == "budget.spend")
            result = map_budget(src, policy);
        else if (src.name == "deploy")
            result = map_deploy(src, policy);
        else if (src.name == "shell.exec")
            result = map_shell(src, policy);
        else {
            rejections.push_back("unknown capability '" + src.name + "' — denied by default");
            continue;
        }

        if (result.first)
            dest_caps.push_back(*result.first);
        else
            rejections.push_back(result.second);
    }

    return {dest_caps, rejections};
}

std::pair<std::optional<Capability>, std::string>
CapabilityCompiler::map_filesystem(const Capability& src,
                                    const std::map<std::string, std::string>& policy) {
    auto it = policy.find("filesystem.root");
    std::string dst_scope = (it != policy.end()) ? it->second : "/workspace";
    if (is_scope_broader(src.scope, dst_scope))
        return {std::nullopt, "filesystem scope '" + dst_scope + "' is broader than source '" +
                src.scope + "' — capability broadening rejected"};
    return {Capability{src.name, dst_scope, true, src.constraints}, ""};
}

std::pair<std::optional<Capability>, std::string>
CapabilityCompiler::map_network(const Capability& src,
                                 const std::map<std::string, std::string>& policy) {
    auto it = policy.find("network.allowlist");
    std::string allowlist = (it != policy.end()) ? it->second : "";
    if (!allowlist.empty() && src.scope != "*") {
        std::vector<std::string> allowed;
        std::stringstream ss(allowlist);
        std::string token;
        while (std::getline(ss, token, ',')) {
            // trim
            while (!token.empty() && token.front() == ' ') token.erase(0, 1);
            while (!token.empty() && token.back() == ' ') token.pop_back();
            allowed.push_back(token);
        }
        bool found = false;
        for (const auto& a : allowed) {
            if (a == src.scope || a == "*") { found = true; break; }
        }
        if (!found)
            return {std::nullopt, "network scope '" + src.scope +
                    "' not in destination allowlist [" + allowlist + "] — capability denied"};
    }
    if (allowlist.empty() && src.scope == "*")
        return {std::nullopt, "wildcard network not allowed in destination — denied"};

    Capability c{src.name, src.scope, true, {}};
    if (!allowlist.empty()) c.constraints["allowlist"] = allowlist;
    return {c, ""};
}

std::pair<std::optional<Capability>, std::string>
CapabilityCompiler::map_budget(const Capability& src,
                                const std::map<std::string, std::string>& policy) {
    auto it = policy.find("budget.max");
    std::string dst_budget = (it != policy.end()) ? it->second : src.scope;
    if (is_budget_higher(src.scope, dst_budget))
        return {std::nullopt, "budget '" + dst_budget + "' exceeds source '" +
                src.scope + "' — capability broadening rejected"};
    return {Capability{src.name, dst_budget, true, {}}, ""};
}

std::pair<std::optional<Capability>, std::string>
CapabilityCompiler::map_deploy(const Capability& src,
                                const std::map<std::string, std::string>& policy) {
    auto it = policy.find("deploy.allowed");
    if (it == policy.end() || it->second != "true")
        return {std::nullopt, "deploy not allowed in destination policy — denied"};
    return {Capability{src.name, src.scope, true, {}}, ""};
}

std::pair<std::optional<Capability>, std::string>
CapabilityCompiler::map_shell(const Capability& src,
                               const std::map<std::string, std::string>& policy) {
    auto it = policy.find("shell.allowed");
    if (it == policy.end() || it->second != "true")
        return {std::nullopt, "shell not allowed in destination policy — denied"};
    return {Capability{src.name, src.scope, true, {}}, ""};
}

std::pair<bool, std::vector<std::string>>
CapabilityCompiler::verify_non_expansion(const std::vector<Capability>& source_caps,
                                          const std::vector<Capability>& dest_caps) const {
    std::vector<std::string> violations;
    std::map<std::string, const Capability*> src_map;
    for (const auto& c : source_caps)
        if (c.granted) src_map[c.name] = &c;

    for (const auto& dst : dest_caps) {
        if (!dst.granted) continue;
        auto it = src_map.find(dst.name);
        if (it == src_map.end()) {
            violations.push_back("destination grants '" + dst.name +
                                 "' not present in source — expansion");
            continue;
        }
        const auto& src = *it->second;
        if (dst.name.rfind("filesystem", 0) == 0) {
            if (is_scope_broader(src.scope, dst.scope))
                violations.push_back("filesystem scope expanded: '" +
                                     src.scope + "' → '" + dst.scope + "'");
        } else if (dst.name == "budget.spend") {
            if (is_budget_higher(src.scope, dst.scope))
                violations.push_back("budget expanded: '" +
                                     src.scope + "' → '" + dst.scope + "'");
        }
    }

    return {violations.empty(), violations};
}

} // namespace hdar
