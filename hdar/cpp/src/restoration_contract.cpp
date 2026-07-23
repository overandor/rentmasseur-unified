#include "hdar/restoration_contract.hpp"

namespace hdar {

std::string restoration_class_name(RestorationClass rc) {
    switch (rc) {
        case RestorationClass::EXACT:    return "exact";
        case RestorationClass::SEMANTIC: return "semantic";
        case RestorationClass::DEGRADED: return "degraded";
        case RestorationClass::FAILED:   return "failed";
    }
    return "unknown";
}

RestorationClass restoration_class_from_string(const std::string& s) {
    if (s == "exact")    return RestorationClass::EXACT;
    if (s == "semantic") return RestorationClass::SEMANTIC;
    if (s == "degraded") return RestorationClass::DEGRADED;
    return RestorationClass::FAILED;
}

JsonValue CompatibilityProfile::to_json() const {
    JsonValue v = JsonValue::object();
    v["source_arch"] = JsonValue::string(source_arch);
    v["source_os"] = JsonValue::string(source_os);
    v["source_accelerator"] = JsonValue::string(source_accelerator);
    v["dest_arch"] = JsonValue::string(dest_arch);
    v["dest_os"] = JsonValue::string(dest_os);
    v["dest_accelerator"] = JsonValue::string(dest_accelerator);
    v["model_available"] = JsonValue::boolean(model_available);
    v["workspace_compatible"] = JsonValue::boolean(workspace_compatible);
    v["capabilities_supported"] = JsonValue::boolean(capabilities_supported);
    JsonValue mf = JsonValue::array();
    for (const auto& m : missing_features)
        mf.push_back(JsonValue::string(m));
    v["missing_features"] = std::move(mf);
    return v;
}

CompatibilityProfile CompatibilityProfile::from_json(const JsonValue& v) {
    CompatibilityProfile p;
    p.source_arch = v.get("source_arch").string_val;
    p.source_os = v.get("source_os").string_val;
    p.source_accelerator = v.get("source_accelerator").string_val;
    p.dest_arch = v.get("dest_arch").string_val;
    p.dest_os = v.get("dest_os").string_val;
    p.dest_accelerator = v.get("dest_accelerator").string_val;
    p.model_available = v.get("model_available").bool_val;
    p.workspace_compatible = v.get("workspace_compatible").bool_val;
    p.capabilities_supported = v.get("capabilities_supported").bool_val;
    const auto& mf = v.get("missing_features");
    if (mf.type == JsonValue::Type::Array) {
        for (const auto& m : mf.array_val)
            p.missing_features.push_back(m.string_val);
    }
    return p;
}

JsonValue RestorationReport::to_json() const {
    JsonValue v = JsonValue::object();
    v["restoration_class"] = JsonValue::string(restoration_class_name(restoration_class));
    v["source_summary"] = JsonValue::string(source_summary);
    v["destination_summary"] = JsonValue::string(destination_summary);

    auto str_arr = [](const std::vector<std::string>& vec) {
        JsonValue a = JsonValue::array();
        for (const auto& s : vec) a.push_back(JsonValue::string(s));
        return a;
    };
    v["preserved_exact"] = str_arr(preserved_exact);
    v["preserved_semantic"] = str_arr(preserved_semantic);
    v["reconstructed"] = str_arr(reconstructed);
    v["discarded"] = str_arr(discarded);
    v["divergence_risks"] = str_arr(divergence_risks);
    v["compatibility"] = compatibility.to_json();
    v["capsule_hash"] = JsonValue::string(capsule_hash);
    v["timestamp"] = JsonValue::number(timestamp);
    return v;
}

RestorationReport RestorationReport::from_json(const JsonValue& v) {
    RestorationReport r;
    r.restoration_class = restoration_class_from_string(v.get("restoration_class").string_val);
    r.source_summary = v.get("source_summary").string_val;
    r.destination_summary = v.get("destination_summary").string_val;

    auto load_arr = [](const JsonValue& parent, const std::string& key) {
        std::vector<std::string> result;
        const auto& a = parent.get(key);
        if (a.type == JsonValue::Type::Array) {
            for (const auto& item : a.array_val)
                result.push_back(item.string_val);
        }
        return result;
    };
    r.preserved_exact = load_arr(v, "preserved_exact");
    r.preserved_semantic = load_arr(v, "preserved_semantic");
    r.reconstructed = load_arr(v, "reconstructed");
    r.discarded = load_arr(v, "discarded");
    r.divergence_risks = load_arr(v, "divergence_risks");
    r.compatibility = CompatibilityProfile::from_json(v.get("compatibility"));
    r.capsule_hash = v.get("capsule_hash").string_val;
    r.timestamp = v.get("timestamp").double_val;
    return r;
}

RestorationContract::RestorationContract() {}

void RestorationContract::populate_preservation_lists(RestorationReport& report,
                                                       const CompatibilityProfile& profile) {
    // Identity, lineage, receipts, capabilities are always preserved exactly
    report.preserved_exact = {
        "agent_identity", "lineage_epoch", "receipt_chain",
        "capability_set", "objective", "continuation_point"
    };

    // Workspace is preserved exactly if compatible
    if (profile.workspace_compatible) {
        report.preserved_exact.push_back("workspace_files");
    } else {
        report.preserved_semantic.push_back("workspace_files");
        report.divergence_risks.push_back("workspace may require format conversion");
    }

    // Model state
    if (profile.model_available) {
        if (profile.source_arch == profile.dest_arch &&
            profile.source_accelerator == profile.dest_accelerator) {
            report.preserved_exact.push_back("model_state");
        } else {
            report.preserved_semantic.push_back("model_state");
            report.divergence_risks.push_back("model state reconstructed on different architecture/accelerator");
        }
    } else {
        report.discarded.push_back("model_state");
        report.divergence_risks.push_back("model not available at destination — cold start required");
    }

    // Capabilities
    if (!profile.capabilities_supported) {
        report.discarded.push_back("unsupported_capabilities");
        report.divergence_risks.push_back("some capabilities not available at destination");
    }

    // Missing features
    for (const auto& feat : profile.missing_features) {
        report.discarded.push_back(feat);
        report.divergence_risks.push_back("missing: " + feat);
    }

    // Process state is always discarded in semantic restoration
    report.discarded.push_back("process_memory");
    report.discarded.push_back("open_descriptors");
    report.discarded.push_back("thread_state");
}

RestorationReport RestorationContract::classify(
    const std::string& source_arch, const std::string& source_os,
    const std::string& source_accel,
    const std::string& dest_arch, const std::string& dest_os,
    const std::string& dest_accel,
    bool model_available, bool workspace_compat,
    bool capabilities_supported,
    const std::vector<std::string>& missing_features,
    const std::string& capsule_hash) {

    CompatibilityProfile profile;
    profile.source_arch = source_arch;
    profile.source_os = source_os;
    profile.source_accelerator = source_accel;
    profile.dest_arch = dest_arch;
    profile.dest_os = dest_os;
    profile.dest_accelerator = dest_accel;
    profile.model_available = model_available;
    profile.workspace_compatible = workspace_compat;
    profile.capabilities_supported = capabilities_supported;
    profile.missing_features = missing_features;

    RestorationReport report;
    report.compatibility = profile;
    report.capsule_hash = capsule_hash;
    report.timestamp = epoch_seconds();
    report.source_summary = source_arch + "/" + source_os + "/" + source_accel;
    report.destination_summary = dest_arch + "/" + dest_os + "/" + dest_accel;

    // Classify
    bool arch_match = (source_arch == dest_arch);
    bool os_match = (source_os == dest_os);
    bool accel_match = (source_accel == dest_accel);

    if (arch_match && os_match && accel_match && model_available &&
        workspace_compat && capabilities_supported && missing_features.empty()) {
        report.restoration_class = RestorationClass::EXACT;
    } else if (workspace_compat && capabilities_supported &&
               (model_available || missing_features.empty())) {
        report.restoration_class = RestorationClass::SEMANTIC;
    } else if (!workspace_compat || !capabilities_supported || !missing_features.empty()) {
        report.restoration_class = RestorationClass::DEGRADED;
    } else {
        report.restoration_class = RestorationClass::FAILED;
    }

    populate_preservation_lists(report, profile);

    return report;
}

} // namespace hdar
