#pragma once

#include "hdar/crypto.hpp"
#include "hdar/provider_base.hpp"
#include "hdar/lease.hpp"
#include "hdar/effects.hpp"
#include "hdar/controller.hpp"
#include "hdar/identity.hpp"
#include "hdar/store.hpp"
#include <string>
#include <vector>
#include <functional>
#include <atomic>

namespace hdar {

struct ReliabilityResult {
    int cycles_run = 0;
    int cycles_passed = 0;
    int cycles_failed = 0;
    std::vector<std::string> failures;
    std::vector<std::string> cleanup_verifications;
    std::vector<std::string> failure_injections;

    JsonValue to_json() const;
};

class ReliabilityHarness {
public:
    using FailureInjector = std::function<void(int cycle, const std::string& runtime_id)>;

    ReliabilityHarness(ProviderBase* provider,
                       ContentStore& store,
                       const std::string& workspace_dir);

    ReliabilityResult run_cycles(int num_cycles = 100);

    void set_failure_injector(FailureInjector injector);
    void inject_failure(int cycle, const std::string& kind);

    const std::vector<std::string>& injected_failures() const { return injected_; }

private:
    ProviderBase* provider_;
    ContentStore& store_;
    std::string workspace_dir_;
    FailureInjector injector_;
    std::vector<std::string> injected_;

    bool verify_cleanup(const std::string& runtime_id);
    bool single_cycle(int cycle_num, ReliabilityResult& result);
};

} // namespace hdar
