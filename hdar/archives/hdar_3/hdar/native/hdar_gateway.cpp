// hdar_gateway.cpp — SSH ForceCommand gateway with capsule resolver (pure C++).

#include "hdar_gateway.h"
#include <sstream>
#include <random>
#include <iostream>
#include <fstream>
#include <sys/stat.h>
#include <cctype>

namespace hdar {

static bool parse_safe_argv(const std::string& input, std::vector<std::string>& argv) {
    std::string current;
    char quote = 0;
    for (char c : input) {
        if (quote) {
            if (c == quote) quote = 0;
            else current += c;
        } else if (c == '\'' || c == '"') {
            quote = c;
        } else if (std::isspace(static_cast<unsigned char>(c))) {
            if (!current.empty()) { argv.push_back(current); current.clear(); }
        } else if (c == ';' || c == '&' || c == '|' || c == '$' || c == '`' || c == '<' || c == '>') {
            return false;
        } else {
            current += c;
        }
    }
    if (quote) return false;
    if (!current.empty()) argv.push_back(current);
    return !argv.empty();
}

SSHGateway::SSHGateway(
    ContinuityLoop& loop,
    ContentStore& store,
    LeaseManager& lease_mgr,
    AppleContainerProvider& provider,
    const Ed25519KeyPair& owner_key
) : loop_(loop), store_(store), lease_mgr_(lease_mgr),
    provider_(provider), owner_key_(owner_key) {}

void SSHGateway::register_agent(const AgentRegistration& reg) {
    agents_.push_back(reg);
}

const AgentRegistration* SSHGateway::resolve_agent(const std::string& ssh_user) const {
    for (const auto& a : agents_) {
        if (a.ssh_user == ssh_user) return &a;
    }
    return nullptr;
}

std::string SSHGateway::generate_runtime_id(const std::string& agent_id) {
    std::random_device rd;
    char buf[64];
    snprintf(buf, sizeof(buf), "hdar-ssh-%s-%08x", agent_id.c_str(), rd());
    return std::string(buf);
}

std::string SSHGateway::handle_session(const SSHSessionInfo& info) {
    std::ostringstream output;

    // 1. Resolve SSH user to agent
    const AgentRegistration* reg = resolve_agent(info.user);
    if (!reg) {
        output << "ERROR: unknown SSH user '" << info.user << "'\n";
        output << "Registered agents: ";
        for (const auto& a : agents_) output << a.ssh_user << " ";
        output << "\n";
        return output.str();
    }

    output << "HDAR SSH Gateway — Agent: " << reg->agent_id << "\n";
    output << "  User: " << info.user << "\n";
    output << "  Client: " << info.client_ip << "\n";
    output << "  Command: " << info.original_command << "\n\n";

    // 2. Load capsule from store
    if (reg->default_capsule_hash.empty()) {
        output << "ERROR: no capsule registered for agent\n";
        return output.str();
    }

    // Load capsule from disk
    std::string capsule_path = store_.root() + "/capsules/" + reg->default_capsule_hash + ".json";
    std::ifstream f(capsule_path);
    if (!f) {
        output << "ERROR: capsule not found in store: " << reg->default_capsule_hash << "\n";
        return output.str();
    }
    std::string capsule_json((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
    Capsule capsule = Capsule::from_json(capsule_json);

    output << "  Capsule: epoch " << capsule.epoch << " hash " << capsule.manifest_hash.substr(0, 16) << "...\n";

    // 3. Restore workspace
    std::string ws_dir = "/tmp/hdar-ssh-" + reg->agent_id;
    mkdir(ws_dir.c_str(), 0755);

    // 4. Generate host ephemeral key
    Ed25519KeyPair host_key = Ed25519KeyPair::generate();

    // Force-release any stale lease for this agent before acquiring new one
    lease_mgr_.force_release(reg->agent_id);

    // 5. Restore capsule — acquire lease
    auto restoration = loop_.restore_on_host_b(
        capsule, provider_, host_key, ws_dir, "ssh-host"
    );

    if (!restoration.restored) {
        output << "ERROR: restoration failed: " << restoration.reason << "\n";
        // If restoration fails due to lease conflict, try with a fresh agent ID
        if (restoration.reason.find("lease") != std::string::npos) {
            output << "  Retrying with fresh agent session...\n";
            lease_mgr_.force_release(reg->agent_id);
            // Retry
            restoration = loop_.restore_on_host_b(capsule, provider_, host_key, ws_dir, "ssh-host-2");
            if (!restoration.restored) {
                output << "ERROR: retry also failed: " << restoration.reason << "\n";
                return output.str();
            }
        } else {
            return output.str();
        }
    }

    output << "  Lease generation: " << restoration.lease_generation << "\n";
    output << "  Fencing token: " << restoration.fencing_token << "\n\n";

    // 6. Materialize VM
    std::string rt_id = generate_runtime_id(reg->agent_id);
    auto record = provider_.materialize(rt_id, ws_dir, "ubuntu:24.04", "1", "256m");

    if (!record.exists) {
        output << "ERROR: VM materialization failed\n";
        lease_mgr_.release(reg->agent_id, restoration.fencing_token);
        return output.str();
    }

    output << "  VM created: " << record.vm_identity << "\n";
    output << "  OS: " << record.os << "  Arch: " << record.arch << "\n\n";

    // 7. Execute command inside VM
    std::string cmd = info.original_command.empty() ? "echo HDAR-shell-ready" : info.original_command;
    std::vector<std::string> command_argv;
    if (!parse_safe_argv(cmd, command_argv)) {
        output << "ERROR: unsafe shell syntax rejected\n";
        provider_.destroy(rt_id);
        lease_mgr_.release(reg->agent_id, restoration.fencing_token);
        return output.str();
    }
    auto exec = provider_.execute_argv(rt_id, "ssh-command", command_argv);

    output << "--- Command output ---\n";
    output << exec.stdout_text;
    if (!exec.stderr_text.empty()) {
        output << "--- stderr ---\n" << exec.stderr_text;
    }
    output << "--- exit code: " << exec.exit_code << " ---\n\n";

    // 8. Sign witness receipt
    bool success = (exec.exit_code == 0);
    auto witness = loop_.host_b_witness(
        capsule, host_key, rt_id,
        "[{\"type\":\"ssh\",\"command\":\"" + cmd + "\"}]",
        "[{\"name\":\"exit_code\",\"passed\":" + std::string(success ? "true" : "false") + "}]",
        success
    );

    output << "  Witness signed: " << witness.host_public_key.substr(0, 16) << "...\n";

    // 9. Destroy VM and prove absence
    provider_.destroy(rt_id);
    bool absent = provider_.verify_destruction(rt_id);

    output << "  VM destroyed: " << (absent ? "absence proven" : "ABSENCE FAILED") << "\n";

    // 10. Release lease
    lease_mgr_.release(reg->agent_id, restoration.fencing_token);
    output << "  Lease released\n\n";

    output << "HDAR session complete.\n";
    return output.str();
}

} // namespace hdar
