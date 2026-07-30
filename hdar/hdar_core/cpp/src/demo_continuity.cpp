#include "hdar/crypto.hpp"
#include "hdar/store.hpp"
#include "hdar/identity.hpp"
#include "hdar/continuity.hpp"
#include "hdar/unsafe_host.hpp"
#include "hdar/apple_container.hpp"

#include <iostream>
#include <filesystem>
#include <fstream>

namespace fs = std::filesystem;

int main() {
    std::cout << "=== HDAR C++ Decisive Continuity Demo ===\n\n";

    std::string test_dir = "/tmp/hdar-continuity-" + hdar::generate_uuid_hex().substr(0, 8);
    std::string workspace = test_dir + "/workspace";
    fs::create_directories(workspace);
    std::ofstream(workspace + "/task_input.txt") << "initial task data";

    // Create owner keys
    auto owner = hdar::OwnerKeyPair::generate();
    std::cout << "Owner fingerprint: " << owner.fingerprint() << "\n";

    // Create content store
    hdar::ContentStore store(test_dir + "/store");

    // Select provider — try Apple Container, fall back to UnsafeHostProvider
    std::unique_ptr<hdar::ProviderBase> provider_a;
    std::unique_ptr<hdar::ProviderBase> provider_b;

    bool use_apple = hdar::AppleContainerProvider::is_available();
    if (use_apple) {
        // Test if Apple Container actually works by trying a simple materialize
        auto test_provider = std::make_unique<hdar::AppleContainerProvider>();
        auto test_rt = test_provider->materialize("hdar-test-" + hdar::generate_uuid_hex().substr(0, 4), "/tmp");
        if (test_rt.exists) {
            test_provider->destroy(test_rt.runtime_id);
            std::cout << "Using Apple Containerization provider\n";
            provider_a = std::make_unique<hdar::AppleContainerProvider>();
            provider_b = std::make_unique<hdar::AppleContainerProvider>();
        } else {
            std::cout << "Apple Container CLI found but not functional — using UnsafeHostProvider\n";
            use_apple = false;
        }
    }
    if (!use_apple) {
        std::cout << "Using UnsafeHostProvider\n";
        provider_a = std::make_unique<hdar::UnsafeHostProvider>(test_dir + "/sandbox-a");
        provider_b = std::make_unique<hdar::UnsafeHostProvider>(test_dir + "/sandbox-b");
    }

    // Destination policy (attenuated)
    std::map<std::string, std::string> dest_policy = {
        {"filesystem.root", "/workspace"},
        {"network.allowlist", "api.example.com"},
        {"budget.max", "$50"},
    };

    // Run continuity loop
    hdar::ContinuityLoop loop(owner, store, provider_a.get(), provider_b.get());
    auto result = loop.run(workspace, "complete the task", dest_policy,
                           "echo 'task executed' > task_output.txt");

    // Print results
    std::cout << "\n--- Continuity Loop Results ---\n";
    std::cout << "Success: " << (result.success ? "YES" : "NO") << "\n";
    std::cout << "Assertions: " << result.assertions_passed << " passed, "
              << result.assertions_failed << " failed\n";

    std::cout << "\n--- Assertion Details ---\n";
    for (const auto& detail : result.assertion_details) {
        std::cout << "  " << detail << "\n";
    }

    std::cout << "\n--- Offline Verification ---\n";
    std::cout << "  Passed: " << result.verification.passed << "\n";
    std::cout << "  Failed: " << result.verification.failed << "\n";
    for (const auto& c : result.verification.checks_passed)
        std::cout << "  [OK] " << c << "\n";
    for (const auto& c : result.verification.checks_failed)
        std::cout << "  [BAD] " << c << "\n";

    std::cout << "\n--- Restoration ---\n";
    std::cout << "  Class: " << hdar::restoration_class_name(result.restoration_report.restoration_class) << "\n";

    if (!result.error.empty())
        std::cout << "\nError: " << result.error << "\n";

    // Cleanup
    fs::remove_all(test_dir);

    std::cout << "\n=== Final: " << result.assertions_passed << "/" 
              << (result.assertions_passed + result.assertions_failed) << " assertions passed ===\n";
    return result.assertions_failed > 0 ? 1 : 0;
}
