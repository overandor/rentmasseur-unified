#pragma once

#include "hdar/crypto.hpp"
#include <string>
#include <vector>
#include <map>

namespace hdar {

enum class RestorationClass {
    EXACT,
    SEMANTIC,
    DEGRADED,
    FAILED
};

std::string restoration_class_name(RestorationClass rc);
RestorationClass restoration_class_from_string(const std::string& s);

struct CompatibilityProfile {
    std::string source_arch;
    std::string source_os;
    std::string source_accelerator;
    std::string dest_arch;
    std::string dest_os;
    std::string dest_accelerator;
    bool model_available = false;
    bool workspace_compatible = true;
    bool capabilities_supported = true;
    std::vector<std::string> missing_features;

    JsonValue to_json() const;
    static CompatibilityProfile from_json(const JsonValue& v);
};

struct RestorationReport {
    RestorationClass restoration_class = RestorationClass::EXACT;
    std::string source_summary;
    std::string destination_summary;
    std::vector<std::string> preserved_exact;
    std::vector<std::string> preserved_semantic;
    std::vector<std::string> reconstructed;
    std::vector<std::string> discarded;
    std::vector<std::string> divergence_risks;
    CompatibilityProfile compatibility;
    std::string capsule_hash;
    double timestamp = 0.0;

    JsonValue to_json() const;
    static RestorationReport from_json(const JsonValue& v);
};

class RestorationContract {
public:
    RestorationContract();

    RestorationReport classify(
        const std::string& source_arch,
        const std::string& source_os,
        const std::string& source_accelerator,
        const std::string& dest_arch,
        const std::string& dest_os,
        const std::string& dest_accelerator,
        bool model_available,
        bool workspace_compatible,
        bool capabilities_supported,
        const std::vector<std::string>& missing_features,
        const std::string& capsule_hash = "");

private:
    void populate_preservation_lists(RestorationReport& report,
                                      const CompatibilityProfile& profile);
};

} // namespace hdar
