#include "hdar/reliability.hpp"
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

namespace hdar {

JsonValue ReliabilityResult::to_json() const {
    JsonValue v = JsonValue::object();
    v["cycles_run"] = JsonValue::integer(cycles_run);
    v["cycles_passed"] = JsonValue::integer(cycles_passed);
    v["cycles_failed"] = JsonValue::integer(cycles_failed);

    JsonValue fails = JsonValue::array();
    for (const auto& f : failures) fails.push_back(JsonValue::string(f));
    v["failures"] = std::move(fails);

    JsonValue cleanups = JsonValue::array();
    for (const auto& c : cleanup_verifications) cleanups.push_back(JsonValue::string(c));
    v["cleanup_verifications"] = std::move(cleanups);

    JsonValue injections = JsonValue::array();
    for (const auto& i : failure_injections) injections.push_back(JsonValue::string(i));
    v["failure_injections"] = std::move(injections);

    return v;
}

ReliabilityHarness::ReliabilityHarness(ProviderBase* provider,
                                       ContentStore& store,
                                       const std::string& workspace_dir)
    : provider_(provider)
    , store_(store)
    , workspace_dir_(workspace_dir) {}

void ReliabilityHarness::set_failure_injector(FailureInjector injector) {
    injector_ = std::move(injector);
}

void ReliabilityHarness::inject_failure(int cycle, const std::string& kind) {
    injected_.push_back("cycle " + std::to_string(cycle) + ": " + kind);
}

bool ReliabilityHarness::verify_cleanup(const std::string& runtime_id) {
    auto listing = provider_->list_runtimes();
    for (const auto& id : listing) {
        if (id == runtime_id) return false;
    }
    auto insp = provider_->inspect(runtime_id);
    return !insp.get("exists").bool_val;
}

bool ReliabilityHarness::single_cycle(int cycle_num, ReliabilityResult& result) {
    std::string runtime_id = "rel-rt-" + std::to_string(cycle_num) + "-" +
                             generate_uuid_hex().substr(0, 8);

    try {
        if (injector_) injector_(cycle_num, runtime_id);

        auto record = provider_->materialize(runtime_id, workspace_dir_);
        if (!record.exists) {
            result.failures.push_back("cycle " + std::to_string(cycle_num) +
                                      ": materialization failed");
            return false;
        }

        auto exec = provider_->execute(runtime_id, "reliability-check",
                                       "echo cycle_" + std::to_string(cycle_num));
        if (!exec.success) {
            result.failures.push_back("cycle " + std::to_string(cycle_num) +
                                      ": execution failed: " + exec.stderr_text);
            return false;
        }

        auto destroyed = provider_->destroy(runtime_id);
        if (destroyed.exists) {
            result.failures.push_back("cycle " + std::to_string(cycle_num) +
                                      ": destroy did not clear exists flag");
            return false;
        }

        if (!verify_cleanup(runtime_id)) {
            result.failures.push_back("cycle " + std::to_string(cycle_num) +
                                      ": cleanup verification failed — runtime still listed");
            return false;
        }

        result.cleanup_verifications.push_back(
            "cycle " + std::to_string(cycle_num) + ": runtime " + runtime_id +
            " confirmed absent");
        return true;
    } catch (const std::exception& e) {
        result.failures.push_back("cycle " + std::to_string(cycle_num) +
                                  ": exception: " + e.what());
        return false;
    }
}

ReliabilityResult ReliabilityHarness::run_cycles(int num_cycles) {
    ReliabilityResult result;

    for (int i = 0; i < num_cycles; i++) {
        result.cycles_run++;
        if (single_cycle(i, result)) {
            result.cycles_passed++;
        } else {
            result.cycles_failed++;
        }
    }

    result.failure_injections = injected_;
    return result;
}

} // namespace hdar
