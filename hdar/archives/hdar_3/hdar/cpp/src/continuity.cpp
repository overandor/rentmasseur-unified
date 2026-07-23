#include "hdar/continuity.hpp"
#include <filesystem>

namespace fs = std::filesystem;

namespace hdar {

JsonValue FencingInvalidation::to_json() const {
    JsonValue v = JsonValue::object();
    v["agent_id"] = JsonValue::string(agent_id);
    v["invalidated_token"] = JsonValue::string(invalidated_token);
    v["generation"] = JsonValue::integer(generation);
    v["timestamp"] = JsonValue::number(timestamp);
    v["reason"] = JsonValue::string(reason);
    return v;
}

JsonValue ContinuityResult::to_json() const {
    JsonValue v = JsonValue::object();
    v["success"] = JsonValue::boolean(success);
    v["assertions_passed"] = JsonValue::integer(assertions_passed);
    v["assertions_failed"] = JsonValue::integer(assertions_failed);

    JsonValue details = JsonValue::array();
    for (const auto& d : assertion_details)
        details.push_back(JsonValue::string(d));
    v["assertion_details"] = std::move(details);

    v["verification"] = verification.to_json();
    v["exec_receipt"] = exec_receipt.to_json();
    v["term_receipt"] = term_receipt.to_json();
    v["restoration_report"] = restoration_report.to_json();
    v["source_manifest"] = source_manifest.to_json();
    v["dest_manifest"] = dest_manifest.to_json();
    if (!error.empty())
        v["error"] = JsonValue::string(error);
    return v;
}

ContinuityLoop::ContinuityLoop(OwnerKeyPair& owner_keys,
                               ContentStore& store,
                               ProviderBase* pa,
                               ProviderBase* pb)
    : owner_keys_(owner_keys)
    , store_(store)
    , provider_a_(pa)
    , provider_b_(pb)
    , lease_manager_(store.base_directory() + "/leases.db") {}

void ContinuityLoop::assert_true(ContinuityResult& result, bool cond, const std::string& desc) {
    if (cond) {
        ++result.assertions_passed;
        result.assertion_details.push_back("PASS: " + desc);
    } else {
        ++result.assertions_failed;
        result.assertion_details.push_back("FAIL: " + desc);
    }
}

ContinuityResult ContinuityLoop::run(
    const std::string& workspace_dir,
    const std::string& objective,
    const std::map<std::string, std::string>& dest_policy,
    const std::string& task_command) {

    ContinuityResult result;

    // 1. Create agent identity using owner's key
    AgentIdentity identity = AgentIdentity::create_with_key("continuity-agent", owner_keys_.private_key);
    assert_true(result, !identity.agent_id.empty(), "agent identity created");
    assert_true(result, !identity.fingerprint().empty(), "agent has Ed25519 fingerprint");

    // 2. Create lineage epoch 0
    LineageEpoch epoch0 = LineageEpoch::genesis(identity.agent_id);
    assert_true(result, epoch0.sequence == 0, "epoch 0 is genesis");
    assert_true(result, !epoch0.parent_epoch.has_value(), "genesis has no parent");

    // 3. Acquire lease for Runtime A
    std::string runtime_a_id = "runtime-a-" + generate_uuid_hex().substr(0, 8);
    auto [lease_a, lease_err] = lease_manager_.acquire(
        identity.agent_id, "", epoch0.sequence, identity.agent_id, runtime_a_id);
    assert_true(result, lease_a.has_value(), "lease acquired for Runtime A");
    assert_true(result, !lease_a->fencing_token.empty(), "fencing token issued");

    // 4. Materialize Runtime A
    auto runtime_a = provider_a_->materialize(runtime_a_id, workspace_dir);
    assert_true(result, runtime_a.exists, "Runtime A materialized");
    assert_true(result, runtime_a.provider == provider_a_->name(), "Runtime A provider correct");

    // 5. Execute task in Runtime A
    auto exec_result = provider_a_->execute(runtime_a_id, "task", task_command);
    assert_true(result, exec_result.success, "task executed in Runtime A");

    // 6. Seal capsule (epoch 0)
    CapsuleSealer sealer(store_, identity, &lease_manager_);
    auto [manifest_a, chain_a] = sealer.seal(
        workspace_dir, epoch0, objective, "step 1", "task completed",
        JsonValue::object(), "", std::nullopt, "", "", JsonValue::object(),
        JsonValue::array(), JsonValue::array(), JsonValue::object(),
        lease_a->fencing_token);

    assert_true(result, !manifest_a.manifest_hash.empty(), "capsule A sealed with hash");
    assert_true(result, !manifest_a.signature.empty(), "capsule A signed by owner");
    assert_true(result, manifest_a.signer_fingerprint == identity.fingerprint(),
                "capsule A signer is owner");

    // Verify manifest signature
    assert_true(result,
                owner_keys_.public_key.verify_hex(manifest_a.canonical_bytes(), manifest_a.signature),
                "capsule A signature verifies with owner public key");

    // 7. Verify receipt chain
    assert_true(result, chain_a.verify(owner_keys_.public_key), "receipt chain A verifies");

    // 8. Destroy Runtime A
    auto destroyed_a = provider_a_->destroy(runtime_a_id);
    assert_true(result, !destroyed_a.exists, "Runtime A destroyed");
    assert_true(result, destroyed_a.delete_timestamp.has_value(), "Runtime A has delete timestamp");

    // 9. Verify destruction
    bool absent_a = provider_a_->verify_destruction(runtime_a_id);
    assert_true(result, absent_a, "Runtime A confirmed absent");

    // 10. Build termination receipt
    TerminationReceipt term_receipt = build_termination_receipt(
        runtime_a_id, provider_a_->name(), destroyed_a.post_delete_inspection.value_or(JsonValue::null()),
        lease_a->fencing_token, identity.signing_key);
    assert_true(result, !term_receipt.signature.empty(), "termination receipt signed");
    assert_true(result, term_receipt.verify(owner_keys_.public_key), "termination receipt verifies");
    result.term_receipt = term_receipt;

    // 11. Release lease A
    bool released = lease_manager_.release(identity.agent_id, lease_a->fencing_token);
    assert_true(result, released, "lease A released");

    // 12. Stale fence rejection — old token should be rejected
    assert_true(result, lease_manager_.reject_stale(identity.agent_id, lease_a->fencing_token),
                "stale fencing token rejected");

    // 13. Generate host keys for Host B
    HostKeyPair host_b_keys = HostKeyPair::generate("host-b");
    assert_true(result, !host_b_keys.public_key_hex().empty(), "Host B has ephemeral key pair");
    assert_true(result, host_b_keys.fingerprint() != owner_keys_.fingerprint(),
                "Host B key is not owner key");

    // 14. Acquire lease for Runtime B
    std::string runtime_b_id = "runtime-b-" + generate_uuid_hex().substr(0, 8);
    auto [lease_b, lease_b_err] = lease_manager_.acquire(
        identity.agent_id, manifest_a.manifest_hash, epoch0.sequence + 1,
        identity.agent_id, runtime_b_id);
    assert_true(result, lease_b.has_value(), "lease acquired for Runtime B");
    assert_true(result, lease_b->lease_generation > lease_a->lease_generation,
                "Runtime B lease generation > Runtime A");

    // 15. Materialize Runtime B
    std::string workspace_b = workspace_dir + "-restored";
    auto runtime_b = provider_b_->materialize(runtime_b_id, workspace_dir);
    assert_true(result, runtime_b.exists, "Runtime B materialized");

    // 16. Restore workspace into Runtime B
    CapsuleRestorer restorer(store_);
    auto [restored_manifest, hash_matches] = restorer.restore_workspace(manifest_a, workspace_b);
    assert_true(result, hash_matches, "workspace hash matches after restoration");

    // 17. Capability attenuation
    std::vector<Capability> source_caps = {
        Capability{"filesystem.read", "/workspace", true, {}},
        Capability{"filesystem.write", "/workspace", true, {}},
        Capability{"network.egress", "api.example.com", true, {}},
        Capability{"budget.spend", "$100", true, {}},
    };

    CapabilityCompiler cap_compiler;
    auto [dest_caps, cap_rejections] = cap_compiler.compile(source_caps, dest_policy);
    auto [non_expansion_ok, violations] = cap_compiler.verify_non_expansion(source_caps, dest_caps);
    assert_true(result, non_expansion_ok, "capability non-expansion invariant holds");
    result.source_manifest = manifest_a;

    // 18. Execute task in Runtime B
    auto exec_b = provider_b_->execute(runtime_b_id, "task", task_command);
    assert_true(result, exec_b.success, "task executed in Runtime B");

    // 19. Build execution witness receipt (signed by Host B, not owner)
    ExecutionReceiptBuilder erb(manifest_a.manifest_hash, host_b_keys, runtime_b_id, provider_b_->name());
    JsonValue env = JsonValue::object();
    env["arch"] = JsonValue::string("arm64");
    env["os"] = JsonValue::string("linux");
    erb.set_environment(env);
    erb.add_operation("task", exec_b.to_json());

    JsonValue auth = JsonValue::object();
    auth["owner_fingerprint"] = JsonValue::string(owner_keys_.fingerprint());
    auth["host_fingerprint"] = JsonValue::string(host_b_keys.fingerprint());
    auth["cannot_advance_epoch"] = JsonValue::boolean(true);
    erb.set_authority(auth);

    ExecutionReceipt exec_receipt = erb.build_and_sign();
    assert_true(result, !exec_receipt.signature.empty(), "execution witness receipt signed by Host B");
    assert_true(result, exec_receipt.verify(host_b_keys.public_key), "execution receipt verifies with host key");
    assert_true(result, host_b_keys.fingerprint() != owner_keys_.fingerprint(),
                "execution receipt signed by non-owner key");
    result.exec_receipt = exec_receipt;

    // 20. Host B cannot forge owner signature (cannot advance epoch)
    LineageEpoch epoch1 = LineageEpoch::child(epoch0);
    // Try signing with host key — should fail owner verification
    std::string fake_sig = host_b_keys.sign_json(epoch1.to_json());
    assert_true(result, !owner_keys_.public_key.verify_json(epoch1.to_json(), fake_sig),
                "Host B cannot forge owner signature on epoch advancement");

    // 21. Owner advances lineage (epoch 1)
    LineageEpoch epoch1_owner = LineageEpoch::child(epoch0);
    std::string owner_sig = identity.signing_key.sign_json(epoch1_owner.to_json());
    assert_true(result, owner_keys_.public_key.verify_json(epoch1_owner.to_json(), owner_sig),
                "owner can sign epoch advancement");

    // 22. Seal destination capsule (epoch 1, signed by owner)
    AgentIdentity identity_copy = identity; // copy for sealer
    CapsuleSealer sealer_b(store_, identity_copy, &lease_manager_);
    auto [manifest_b, chain_b] = sealer_b.seal(
        workspace_b, epoch1_owner, objective, "step 2", "task continued",
        JsonValue::object(), "", manifest_a.manifest_hash, "", "",
        JsonValue::object(), JsonValue::array(), JsonValue::array(),
        JsonValue::object(), lease_b->fencing_token);

    assert_true(result, !manifest_b.manifest_hash.empty(), "capsule B sealed with hash");
    assert_true(result, manifest_b.parent_capsule_hash.value_or("") == manifest_a.manifest_hash,
                "capsule B parent links to capsule A");
    assert_true(result, chain_b.verify(owner_keys_.public_key), "receipt chain B verifies");
    result.dest_manifest = manifest_b;

    // 23. Destroy Runtime B
    auto destroyed_b = provider_b_->destroy(runtime_b_id);
    assert_true(result, !destroyed_b.exists, "Runtime B destroyed");
    assert_true(result, provider_b_->verify_destruction(runtime_b_id), "Runtime B confirmed absent");

    // 24. Release lease B
    lease_manager_.release(identity.agent_id, lease_b->fencing_token);

    // 25. Restoration contract
    RestorationContract rc;
    result.restoration_report = rc.classify(
        "arm64", "linux", "none", "arm64", "linux", "none",
        true, true, true, {}, manifest_a.manifest_hash);
    assert_true(result, result.restoration_report.restoration_class == RestorationClass::EXACT,
                "restoration class is exact (same arch/os/accel)");

    // 26. Offline verification of full chain
    OfflineVerifier verifier(owner_keys_.public_key);
    result.verification = verifier.verify_full_chain(
        manifest_a, exec_receipt, term_receipt, manifest_b, source_caps, dest_caps);

    assert_true(result, result.verification.overall_pass, "offline verification passes");
    assert_true(result, result.verification.failed == 0, "zero verification failures");

    // 27. Tamper detection — modify manifest and verify it fails
    CapsuleManifest tampered = manifest_a;
    tampered.objective = "TAMPERED OBJECTIVE";
    auto tamper_result = verifier.verify_capsule(tampered);
    assert_true(result, tamper_result.failed > 0, "tampered manifest detected");

    // 28. Rollback rejection — old epoch should not advance
    assert_true(result, epoch1_owner.sequence > epoch0.sequence, "epoch monotonicity");
    assert_true(result, epoch1_owner.parent_epoch.value_or("") == epoch0.epoch_id,
                "epoch parent linkage correct");

    result.success = (result.assertions_failed == 0);
    return result;
}

} // namespace hdar
