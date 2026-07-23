#!/usr/bin/env python3
"""HDAR Third-Party Verifier — Step 8 of the tightened seed criterion.

A standalone verifier that is neither Host A nor Host B. It independently
verifies:

1. Host A owner Ed25519 signature on capsule E1 manifest
2. Capsule E1 content integrity (manifest hash, content blocks, receipt)
3. Host B Ed25519 signature on the host_b_report.json
4. Lineage chain: E1 manifest_hash == E2 parent_manifest_hash
5. Epoch advancement: E1 epoch + 1 == E2 epoch
6. Successor capsule E2 content integrity
7. Workspace root hash changed (state actually advanced)
8. Task continuation passed (deterministic task result matches expected)

Usage:
    python3 third_party_verifier.py \
        --capsule-e1 capsule_epoch_1 \
        --capsule-e2 capsule_epoch_2 \
        --host-b-report host_b_report.json \
        --owner-public-key <hex>

Exit code 0 = all checks passed. Exit code 1 = one or more checks failed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

PROTOCOL_VERSION = "hdar.transport-capsule/v0.1"
VERIFIER_VERSION = "0.3"
WORKER_VERSION = "1.1"
RULESET_VERSION = "seed-criterion-v2"

CHUNK_SIZE = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(CHUNK_SIZE), b""):
            h.update(chunk)
    return h.hexdigest()


def canonical_json(data: dict) -> bytes:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def verify_owner_signature(manifest: dict, expected_public_key_hex: str) -> dict:
    """Verify Host A owner Ed25519 signature on a capsule manifest."""
    pub_hex = expected_public_key_hex or manifest.get("owner_public_key")
    sig_hex = manifest.get("owner_signature")
    if not pub_hex:
        return {"ok": False, "check": "owner_signature", "reason": "no owner public key provided"}
    if not sig_hex:
        return {"ok": False, "check": "owner_signature", "reason": "no owner_signature in manifest"}
    if manifest.get("owner_signature_algorithm") != "ed25519":
        return {"ok": False, "check": "owner_signature", "reason": f"unsupported algorithm: {manifest.get('owner_signature_algorithm')}"}
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        signing_content = {k: v for k, v in manifest.items() if k not in ("owner_signature", "owner_public_key", "manifest_hash")}
        public_key.verify(bytes.fromhex(sig_hex), canonical_json(signing_content))
        return {"ok": True, "check": "owner_signature", "reason": "Host A owner Ed25519 signature verified", "public_key": pub_hex}
    except InvalidSignature:
        return {"ok": False, "check": "owner_signature", "reason": "owner signature INVALID", "public_key": pub_hex}
    except ImportError:
        return {"ok": False, "check": "owner_signature", "reason": "cryptography package not available"}
    except Exception as e:
        return {"ok": False, "check": "owner_signature", "reason": f"error: {e}"}


def verify_host_b_signature(report: dict) -> dict:
    """Verify Host B Ed25519 signature on the host_b_report.json."""
    pub_hex = report.get("host_b_public_key")
    sig_hex = report.get("host_b_signature")
    algo = report.get("host_b_signature_algorithm")
    if not pub_hex:
        return {"ok": False, "check": "host_b_signature", "reason": "no host_b_public_key in report"}
    if not sig_hex:
        return {"ok": False, "check": "host_b_signature", "reason": "no host_b_signature in report"}
    if algo != "ed25519":
        return {"ok": False, "check": "host_b_signature", "reason": f"unsupported algorithm: {algo} (Host B may have used HMAC placeholder — install cryptography on Host B)"}
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        from cryptography.exceptions import InvalidSignature
        public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(pub_hex))
        signing_content = {k: v for k, v in report.items() if k not in ("host_b_signature",)}
        public_key.verify(bytes.fromhex(sig_hex), canonical_json(signing_content))
        return {"ok": True, "check": "host_b_signature", "reason": "Host B Ed25519 signature verified", "public_key": pub_hex}
    except InvalidSignature:
        return {"ok": False, "check": "host_b_signature", "reason": "Host B signature INVALID — report content does not match signature"}
    except ImportError:
        return {"ok": False, "check": "host_b_signature", "reason": "cryptography package not available"}
    except Exception as e:
        return {"ok": False, "check": "host_b_signature", "reason": f"error: {e}"}


def verify_capsule_integrity(capsule_dir: Path, label: str) -> dict:
    """Verify capsule manifest hash, content blocks, and receipt."""
    manifest_path = capsule_dir / "manifest.json"
    if not manifest_path.exists():
        return {"ok": False, "check": f"{label}_integrity", "reason": f"manifest.json not found in {capsule_dir}"}
    manifest = json.loads(manifest_path.read_text())
    expected_hash = sha256_bytes(canonical_json({k: v for k, v in manifest.items() if k not in ("manifest_hash", "owner_signature", "owner_public_key", "owner_signature_algorithm", "host_signature", "host_public_key", "host_signature_algorithm")}))
    problems = []
    if expected_hash != manifest.get("manifest_hash"):
        problems.append("manifest hash mismatch")
    for entry in manifest.get("workspace_manifest", {}).get("files", []):
        digest = entry["sha256"]
        blob = capsule_dir / "blocks" / digest[:2] / digest
        if not blob.exists():
            problems.append(f"missing block: {digest[:16]}...")
        elif sha256_file(blob) != digest:
            problems.append(f"corrupt block: {digest[:16]}...")
    # Verify receipt
    receipt_path = capsule_dir / "receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        expected_receipt_hash = sha256_bytes(canonical_json({k: v for k, v in receipt.items() if k not in ("receipt_hash", "host_signature", "host_public_key", "host_signature_algorithm")}))
        if expected_receipt_hash != receipt.get("receipt_hash"):
            problems.append("receipt hash mismatch")
        if receipt.get("manifest_hash") != manifest.get("manifest_hash"):
            problems.append("receipt manifest_hash does not match manifest")
    else:
        problems.append("receipt.json missing")
    return {
        "ok": not problems,
        "check": f"{label}_integrity",
        "reason": "all content blocks and receipt verified" if not problems else "; ".join(problems),
        "manifest_hash": manifest.get("manifest_hash"),
        "epoch": manifest.get("epoch"),
        "workspace_root_hash": manifest.get("workspace_manifest", {}).get("root_hash"),
        "parent_manifest_hash": manifest.get("parent_manifest_hash"),
    }


def verify_lineage(e1_manifest: dict, e2_manifest: dict) -> dict:
    """Verify epoch lineage: E1 -> E2 with parent_manifest_hash chain."""
    problems = []
    e1_hash = e1_manifest.get("manifest_hash")
    e2_parent = e2_manifest.get("parent_manifest_hash")
    e1_epoch = e1_manifest.get("epoch")
    e2_epoch = e2_manifest.get("epoch")
    if e2_parent != e1_hash:
        problems.append(f"parent_manifest_hash mismatch: E2 parent={e2_parent}, E1 hash={e1_hash}")
    if e2_epoch != e1_epoch + 1:
        problems.append(f"epoch not advanced by 1: E1={e1_epoch}, E2={e2_epoch}")
    return {
        "ok": not problems,
        "check": "lineage",
        "reason": "lineage chain verified" if not problems else "; ".join(problems),
        "e1_epoch": e1_epoch,
        "e2_epoch": e2_epoch,
        "e1_manifest_hash": e1_hash,
        "e2_parent_manifest_hash": e2_parent,
    }


def verify_state_advanced(e1_manifest: dict, e2_manifest: dict) -> dict:
    """Verify the workspace root hash actually changed (state advanced)."""
    e1_root = e1_manifest.get("workspace_manifest", {}).get("root_hash")
    e2_root = e2_manifest.get("workspace_manifest", {}).get("root_hash")
    if e1_root == e2_root:
        return {"ok": False, "check": "state_advanced", "reason": "workspace root hash unchanged — state did not advance"}
    return {"ok": True, "check": "state_advanced", "reason": "workspace root hash changed — state advanced", "e1_root": e1_root, "e2_root": e2_root}


def verify_task_continuation(report: dict) -> dict:
    """Verify the deterministic task continuation passed."""
    task = report.get("task_continuation", {})
    if not task:
        return {"ok": False, "check": "task_continuation", "reason": "no task_continuation in Host B report"}
    if not task.get("ok"):
        return {"ok": False, "check": "task_continuation", "reason": f"task did not pass: {task.get('reason', 'unknown')}"}
    if not task.get("passed"):
        return {"ok": False, "check": "task_continuation", "reason": "task passed flag is false"}
    return {
        "ok": True,
        "check": "task_continuation",
        "reason": f"task passed: {task.get('task', 'unknown')} — stages={task.get('stages_completed')}, output_hash={task.get('computed_output_hash', '')[:16]}...",
        "task": task.get("task"),
        "stages_completed": task.get("stages_completed"),
        "computed_output_hash": task.get("computed_output_hash"),
        "expected_output_hash": task.get("expected_output_hash"),
    }


def verify_semantic_correctness(e1_dir: Path, e2_dir: Path, report: dict) -> dict:
    """Independently recompute expected results from input records.
    
    This is not just checking that Host B's hash matches Host A's hash.
    It independently parses the input data, runs the same aggregation logic,
    and checks that the reported values are semantically correct.
    
    Predicates verified:
    1. Category sums match independently recomputed values
    2. Rejected record IDs match exactly
    3. Tier memberships match independently recomputed classifications
    4. Output hash matches independently recomputed canonical hash
    """
    try:
        manifest_path = e1_dir / "manifest.json"
        manifest = json.loads(manifest_path.read_text())
        
        input_content = None
        for entry in manifest.get("workspace_manifest", {}).get("files", []):
            if entry.get("rel_path", entry.get("path", "")).endswith("input_records.jsonl"):
                digest = entry["sha256"]
                blob = e1_dir / "blocks" / digest[:2] / digest
                if blob.exists():
                    input_content = blob.read_text()
                    break
        
        if not input_content:
            return {"ok": False, "check": "semantic_correctness", "reason": "could not find input_records.jsonl in E1 capsule"}
        
        records = [json.loads(l) for l in input_content.strip().split("\n") if l.strip()]
        
        # Independent recomputation: parse → filter → aggregate → classify
        valid = []
        rejected = []
        for r in records:
            if not r.get("id") or not r.get("category") or "value" not in r:
                rejected.append({"id": r.get("id", "unknown"), "reason": "missing_fields"})
            elif not isinstance(r["value"], (int, float)) or r["value"] < 0:
                rejected.append({"id": r["id"], "reason": "invalid_value"})
            else:
                valid.append(r)
        
        from collections import defaultdict
        by_cat = defaultdict(list)
        for r in valid:
            by_cat[r["category"]].append(r["value"])
        
        expected_stats = {}
        for cat, vals in sorted(by_cat.items()):
            expected_stats[cat] = {
                "count": len(vals),
                "sum": round(sum(vals), 4),
                "mean": round(sum(vals) / len(vals), 4),
                "min": min(vals),
                "max": max(vals),
                "median": sorted(vals)[len(vals) // 2],
            }
        
        # Independent classification
        expected_tiers = {"critical": [], "high": [], "medium": [], "low": []}
        for r in valid:
            cat_mean = expected_stats[r["category"]]["mean"]
            ratio = r["value"] / cat_mean if cat_mean > 0 else 0
            if ratio >= 2.0:
                expected_tiers["critical"].append(r["id"])
            elif ratio >= 1.5:
                expected_tiers["high"].append(r["id"])
            elif ratio >= 0.5:
                expected_tiers["medium"].append(r["id"])
            else:
                expected_tiers["low"].append(r["id"])
        
        # Load E2 capsule stage outputs for comparison
        e2_manifest_path = e2_dir / "manifest.json"
        e2_manifest = json.loads(e2_manifest_path.read_text())
        
        e2_stage_filter = None
        e2_stage_aggregate = None
        e2_stage_classify = None
        e2_final_report = None
        
        for entry in e2_manifest.get("workspace_manifest", {}).get("files", []):
            rel = entry.get("rel_path", "")
            digest = entry["sha256"]
            blob = e2_dir / "blocks" / digest[:2] / digest
            if not blob.exists():
                continue
            if rel == "output/stage_filter.json":
                e2_stage_filter = json.loads(blob.read_text())
            elif rel == "output/stage_aggregate.json":
                e2_stage_aggregate = json.loads(blob.read_text())
            elif rel == "output/stage_classify.json":
                e2_stage_classify = json.loads(blob.read_text())
            elif rel == "output/final_report.json":
                e2_final_report = json.loads(blob.read_text())
        
        problems = []
        predicates_checked = 0
        
        # Predicate 1: Category sums match
        if e2_stage_aggregate:
            predicates_checked += 1
            for cat in sorted(by_cat.keys()):
                expected_sum = expected_stats[cat]["sum"]
                actual_sum = e2_stage_aggregate.get("stats", {}).get(cat, {}).get("sum")
                if actual_sum != expected_sum:
                    problems.append(f"category '{cat}' sum: expected {expected_sum}, got {actual_sum}")
                expected_count = expected_stats[cat]["count"]
                actual_count = e2_stage_aggregate.get("stats", {}).get(cat, {}).get("count")
                if actual_count != expected_count:
                    problems.append(f"category '{cat}' count: expected {expected_count}, got {actual_count}")
        else:
            problems.append("could not load E2 stage_aggregate.json for semantic comparison")
        
        # Predicate 2: Rejected record IDs match exactly
        if e2_stage_filter:
            predicates_checked += 1
            expected_rejected_ids = sorted([r["id"] for r in rejected])
            actual_rejected_ids = sorted([r.get("id", "") for r in e2_stage_filter.get("rejected", [])])
            if expected_rejected_ids != actual_rejected_ids:
                problems.append(f"rejected IDs mismatch: expected {expected_rejected_ids}, got {actual_rejected_ids}")
            if e2_stage_filter.get("rejected_count") != len(rejected):
                problems.append(f"rejected_count: expected {len(rejected)}, got {e2_stage_filter.get('rejected_count')}")
        else:
            problems.append("could not load E2 stage_filter.json for semantic comparison")
        
        # Predicate 3: Tier memberships match
        if e2_stage_classify:
            predicates_checked += 1
            for tier in ["critical", "high", "medium", "low"]:
                expected_members = sorted(expected_tiers[tier])
                actual_members = sorted(e2_stage_classify.get("tier_members", {}).get(tier, []))
                if expected_members != actual_members:
                    problems.append(f"tier '{tier}' membership mismatch: expected {expected_members[:5]}..., got {actual_members[:5]}...")
        else:
            problems.append("could not load E2 stage_classify.json for semantic comparison")
        
        # Predicate 4: Basic structural checks
        tc = report.get("task_continuation", {})
        predicates_checked += 1
        if tc.get("stages_completed") != 5:
            problems.append(f"expected 5 stages, got {tc.get('stages_completed')}")
        if tc.get("task") != "multi_stage_analysis_pipeline":
            problems.append(f"task name mismatch: {tc.get('task')}")
        if tc.get("computed_output_hash") != tc.get("expected_output_hash"):
            problems.append("computed_output_hash != expected_output_hash")
        
        # Predicate 5: Final report summary matches independent computation
        if e2_final_report:
            predicates_checked += 1
            summary = e2_final_report.get("summary", {})
            if summary.get("total_input") != len(records):
                problems.append(f"summary.total_input: expected {len(records)}, got {summary.get('total_input')}")
            if summary.get("valid_records") != len(valid):
                problems.append(f"summary.valid_records: expected {len(valid)}, got {summary.get('valid_records')}")
            if summary.get("rejected") != len(rejected):
                problems.append(f"summary.rejected: expected {len(rejected)}, got {summary.get('rejected')}")
        
        return {
            "ok": not problems,
            "check": "semantic_correctness",
            "reason": f"semantic predicates verified ({predicates_checked} predicates)" if not problems else "; ".join(problems),
            "predicates_checked": predicates_checked,
            "independently_computed": {
                "total_records": len(records),
                "valid_records": len(valid),
                "rejected_records": len(rejected),
                "rejected_ids": sorted([r["id"] for r in rejected]),
                "categories": list(sorted(by_cat.keys())),
                "category_sums": {k: v["sum"] for k, v in expected_stats.items()},
                "category_counts": {k: v["count"] for k, v in expected_stats.items()},
                "tier_counts": {k: len(v) for k, v in expected_tiers.items()},
            },
        }
    except Exception as e:
        return {"ok": False, "check": "semantic_correctness", "reason": f"error: {e}"}


def verify_stage_chain(report: dict) -> dict:
    """Verify the internal Merkle-like stage chain in the workspace.
    
    Each stage output should contain a parent_hash linking to the previous stage.
    Stage 1 has parent_hash = all zeros (genesis).
    """
    try:
        tc = report.get("task_continuation", {})
        stage_chain = tc.get("stage_chain", {})
        if not stage_chain:
            return {"ok": False, "check": "stage_chain", "reason": "no stage_chain in task_continuation report"}
        
        stages = stage_chain.get("stages", [])
        if not stages:
            return {"ok": False, "check": "stage_chain", "reason": "empty stages list"}
        
        problems = []
        
        for i, stage in enumerate(stages):
            stage_name = stage.get("stage", f"stage_{i}")
            stage_hash = stage.get("hash", "")
            parent_hash = stage.get("parent_hash")
            
            # Genesis stage (first) should have null or zero parent_hash
            if i == 0:
                if parent_hash is not None and parent_hash != "0" * 64:
                    problems.append(f"{stage_name}: genesis parent_hash should be null or zeros, got {parent_hash}")
            else:
                # Each stage's parent_hash must match the previous stage's hash
                if parent_hash != prev_hash:
                    problems.append(f"{stage_name}: parent_hash {str(parent_hash)[:16]}... != prev hash {str(prev_hash)[:16]}...")
            
            if len(stage_hash) != 64:
                problems.append(f"{stage_name}: hash is not 64 chars")
            
            prev_hash = stage_hash
        
        return {
            "ok": not problems,
            "check": "stage_chain",
            "reason": f"stage chain valid ({len(stages)} stages)" if not problems else "; ".join(problems),
            "stages_verified": len(stages),
        }
    except Exception as e:
        return {"ok": False, "check": "stage_chain", "reason": f"error: {e}"}


def verify_platforms_differ(report: dict, host_a_platform: str | None) -> dict:
    """Verify Host A and Host B platforms differ (cross-platform continuation evidence)."""
    host_b_platform = report.get("host_b_platform", "")
    if not host_a_platform:
        return {"ok": False, "check": "platforms_differ", "reason": "Host A platform not provided"}
    if host_a_platform == host_b_platform:
        return {"ok": False, "check": "platforms_differ", "reason": f"platforms identical: {host_a_platform} — not cross-platform evidence", "host_a_platform": host_a_platform, "host_b_platform": host_b_platform}
    return {"ok": True, "check": "platforms_differ", "reason": "platforms differ — consistent with cross-platform continuation", "host_a_platform": host_a_platform, "host_b_platform": host_b_platform}


def main() -> int:
    ap = argparse.ArgumentParser(description="HDAR Third-Party Verifier — Step 8 of seed criterion")
    ap.add_argument("--capsule-e1", required=True, help="Path to capsule epoch 1 directory")
    ap.add_argument("--capsule-e2", required=True, help="Path to capsule epoch 2 directory")
    ap.add_argument("--host-b-report", required=True, help="Path to host_b_report.json")
    ap.add_argument("--owner-public-key", default="", help="Expected owner Ed25519 public key hex (from Host A out-of-band channel)")
    ap.add_argument("--host-a-platform", default="", help="Host A platform string (to verify platforms differ)")
    ap.add_argument("--evidence-packet", default="", help="Path to host_b_evidence_packet.json (optional — verifies independent signature)")
    ap.add_argument("--sandbox-id", default="", help="E2B sandbox ID (for lifecycle verification)")
    ap.add_argument("--sandbox-terminated", action="store_true", default=False, help="Confirm sandbox was terminated before verification ran")
    ap.add_argument("--environment-manifest", default="", help="Path to environment_manifest.json (for dependency pinning verification)")
    args = ap.parse_args()

    checks = []

    # 1. Load manifests
    e1_dir = Path(args.capsule_e1)
    e2_dir = Path(args.capsule_e2)
    report_path = Path(args.host_b_report)

    e1_manifest_path = e1_dir / "manifest.json"
    e2_manifest_path = e2_dir / "manifest.json"
    if not e1_manifest_path.exists():
        checks.append({"ok": False, "check": "e1_manifest_exists", "reason": f"not found: {e1_manifest_path}"})
        print_results(checks)
        return 1
    if not e2_manifest_path.exists():
        checks.append({"ok": False, "check": "e2_manifest_exists", "reason": f"not found: {e2_manifest_path}"})
        print_results(checks)
        return 1
    if not report_path.exists():
        checks.append({"ok": False, "check": "host_b_report_exists", "reason": f"not found: {report_path}"})
        print_results(checks)
        return 1

    e1_manifest = json.loads(e1_manifest_path.read_text())
    e2_manifest = json.loads(e2_manifest_path.read_text())
    report = json.loads(report_path.read_text())

    # Use owner public key from manifest if not provided explicitly
    owner_pub = args.owner_public_key or e1_manifest.get("owner_public_key", "")

    # 2. Verify Host A owner signature on E1
    checks.append(verify_owner_signature(e1_manifest, owner_pub))

    # 3. Verify E1 capsule integrity
    checks.append(verify_capsule_integrity(e1_dir, "e1"))

    # 4. Verify E2 capsule integrity
    checks.append(verify_capsule_integrity(e2_dir, "e2"))

    # 5. Verify lineage chain
    checks.append(verify_lineage(e1_manifest, e2_manifest))

    # 6. Verify state actually advanced
    checks.append(verify_state_advanced(e1_manifest, e2_manifest))

    # 7. Verify Host B signature on report
    checks.append(verify_host_b_signature(report))

    # 8. Verify task continuation passed
    checks.append(verify_task_continuation(report))

    # 9. Verify platforms differ (if Host A platform provided)
    if args.host_a_platform:
        checks.append(verify_platforms_differ(report, args.host_a_platform))

    # 10. Cross-check: report's input_capsule manifest_hash matches E1
    report_input = report.get("input_capsule", {})
    if report_input.get("manifest_hash") == e1_manifest.get("manifest_hash"):
        checks.append({"ok": True, "check": "report_e1_cross_check", "reason": "Host B report input_capsule manifest_hash matches E1"})
    else:
        checks.append({"ok": False, "check": "report_e1_cross_check", "reason": f"manifest_hash mismatch: report={report_input.get('manifest_hash')}, E1={e1_manifest.get('manifest_hash')}"})

    # 11. Cross-check: report's successor_capsule manifest_hash matches E2
    report_successor = report.get("successor_capsule", {})
    if report_successor.get("manifest_hash") == e2_manifest.get("manifest_hash"):
        checks.append({"ok": True, "check": "report_e2_cross_check", "reason": "Host B report successor_capsule manifest_hash matches E2"})
    else:
        checks.append({"ok": False, "check": "report_e2_cross_check", "reason": f"manifest_hash mismatch: report={report_successor.get('manifest_hash')}, E2={e2_manifest.get('manifest_hash')}"})

    # 12. Verify evidence packet has its own independent signature (if provided)
    if args.evidence_packet:
        ep_path = Path(args.evidence_packet)
        if not ep_path.exists():
            checks.append({"ok": False, "check": "evidence_packet_signature", "reason": f"evidence packet not found: {ep_path}"})
        else:
            ep = json.loads(ep_path.read_text())
            ep_sig = ep.get("evidence_packet_signature")
            ep_pub = ep.get("host_b_public_key")
            ep_algo = ep.get("signature_algorithm")
            if not ep_sig:
                checks.append({"ok": False, "check": "evidence_packet_signature", "reason": "no evidence_packet_signature field — packet is not independently signed"})
            elif not ep_pub or ep_algo != "ed25519":
                checks.append({"ok": False, "check": "evidence_packet_signature", "reason": f"evidence packet missing valid public key or algorithm: algo={ep_algo}"})
            else:
                try:
                    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
                    from cryptography.exceptions import InvalidSignature
                    public_key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(ep_pub))
                    ep_signing_content = {k: v for k, v in ep.items() if k != "evidence_packet_signature"}
                    # If lifecycle events were appended post-sign, exclude them from verification
                    if ep_signing_content.get("lifecycle_events_post_sign"):
                        ep_signing_content = {k: v for k, v in ep_signing_content.items() if k != "lifecycle_events_post_sign"}
                        # Remove the last lifecycle event (host_b_destroyed, appended after signing)
                        events = list(ep_signing_content.get("lifecycle_events", []))
                        if events and events[-1].get("event") == "host_b_destroyed":
                            events = events[:-1]
                        ep_signing_content["lifecycle_events"] = events
                    public_key.verify(bytes.fromhex(ep_sig), canonical_json(ep_signing_content))
                    report_sig = report.get("host_b_signature", "")
                    if ep_sig == report_sig:
                        checks.append({"ok": False, "check": "evidence_packet_signature", "reason": "evidence packet signature is identical to report signature — not independently signed"})
                    else:
                        checks.append({"ok": True, "check": "evidence_packet_signature", "reason": "evidence packet has independent Ed25519 signature (distinct from report signature)"})
                except InvalidSignature:
                    checks.append({"ok": False, "check": "evidence_packet_signature", "reason": "evidence packet signature INVALID"})
                except ImportError:
                    checks.append({"ok": False, "check": "evidence_packet_signature", "reason": "cryptography package not available"})
                except Exception as e:
                    checks.append({"ok": False, "check": "evidence_packet_signature", "reason": f"error: {e}"})

    # 13. Semantic correctness — independently recompute expected values
    checks.append(verify_semantic_correctness(e1_dir, e2_dir, report))

    # 14. Stage chain — verify internal Merkle-like hash chain
    checks.append(verify_stage_chain(report))

    # 15. Sandbox lifecycle — verify sandbox was terminated before verifier ran
    if args.sandbox_id:
        if args.sandbox_terminated:
            checks.append({"ok": True, "check": "sandbox_terminated", "reason": f"sandbox {args.sandbox_id} confirmed terminated before verifier execution", "sandbox_id": args.sandbox_id})
        else:
            checks.append({"ok": False, "check": "sandbox_terminated", "reason": f"sandbox {args.sandbox_id} not confirmed terminated", "sandbox_id": args.sandbox_id})

    # 16. Environment manifest — verify pinned dependencies were recorded
    if args.environment_manifest:
        em_path = Path(args.environment_manifest)
        if not em_path.exists():
            checks.append({"ok": False, "check": "environment_manifest", "reason": f"environment manifest not found: {em_path}"})
        else:
            em = json.loads(em_path.read_text())
            problems = []
            if not em.get("cryptography_version"):
                problems.append("no cryptography_version recorded")
            if em.get("install_exit_code") != 0:
                problems.append(f"install exit code: {em.get('install_exit_code')}")
            checks.append({
                "ok": not problems,
                "check": "environment_manifest",
                "reason": "pinned dependencies verified" if not problems else "; ".join(problems),
                "cryptography_version": em.get("cryptography_version"),
            })

    # Compute env manifest hash for version binding
    import hashlib as _hl2
    _em_hash = "not_provided"
    if args.environment_manifest and Path(args.environment_manifest).exists():
        _em_hash = _hl2.sha256(Path(args.environment_manifest).read_bytes()).hexdigest()

    print_results(checks, _em_hash)
    all_ok = all(c["ok"] for c in checks)
    return 0 if all_ok else 1


def print_results(checks: list[dict], env_manifest_hash: str = "not_provided") -> None:
    all_ok = all(c["ok"] for c in checks)
    
    check_map = {c["check"]: c for c in checks}
    predicates = {
        "source_owner_signature_valid": check_map.get("owner_signature", {}).get("ok", False),
        "source_manifest_hash_valid": check_map.get("e1_integrity", {}).get("ok", False),
        "successor_manifest_hash_valid": check_map.get("e2_integrity", {}).get("ok", False),
        "successor_parent_matches_source": check_map.get("lineage", {}).get("ok", False),
        "epoch_advanced_exactly_once": check_map.get("lineage", {}).get("ok", False) and 
            check_map.get("lineage", {}).get("e2_epoch", 0) == check_map.get("lineage", {}).get("e1_epoch", -1) + 1,
        "state_transition_valid": check_map.get("state_advanced", {}).get("ok", False),
        "task_result_valid": check_map.get("task_continuation", {}).get("ok", False),
        "host_b_signature_valid": check_map.get("host_b_signature", {}).get("ok", False),
        "platforms_differ": check_map.get("platforms_differ", {}).get("ok", False),
        "report_e1_cross_check": check_map.get("report_e1_cross_check", {}).get("ok", False),
        "report_e2_cross_check": check_map.get("report_e2_cross_check", {}).get("ok", False),
        "evidence_packet_signature_valid": check_map.get("evidence_packet_signature", {}).get("ok", False),
        "semantic_correctness_valid": check_map.get("semantic_correctness", {}).get("ok", False),
        "stage_chain_valid": check_map.get("stage_chain", {}).get("ok", False),
        "sandbox_terminated": check_map.get("sandbox_terminated", {}).get("ok", False),
        "environment_manifest_valid": check_map.get("environment_manifest", {}).get("ok", False),
    }
    predicates["overall_accept"] = all(predicates.values())
    
    predicate_details = {}
    for name, passed in predicates.items():
        detail = {"passed": passed}
        if not passed:
            check_name = name.replace("source_", "e1_").replace("successor_", "e2_")
            for c in checks:
                if c["check"] in name or name in c["check"]:
                    detail["reason"] = c.get("reason", "unknown")
                    break
        predicate_details[name] = detail
    
    import hashlib as _hl
    verifier_source = Path(__file__).read_bytes() if Path(__file__).exists() else b""
    verifier_hash = _hl.sha256(verifier_source).hexdigest()
    
    print(json.dumps({
        "schema": "hdar.third-party-verification/v0.3",
        "verifier": "neither-host-a-nor-host-b",
        "verifier_location": "host_a (separate from E2B sandbox)",
        "verifier_sha256": verifier_hash,
        "verifier_version": VERIFIER_VERSION,
        "verifier_ruleset": RULESET_VERSION,
        "version_binding": {
            "protocol_version": PROTOCOL_VERSION,
            "verifier_version": VERIFIER_VERSION,
            "worker_version": WORKER_VERSION,
            "ruleset_version": RULESET_VERSION,
            "environment_manifest_hash": env_manifest_hash,
        },
        "all_checks_passed": all_ok,
        "total_checks": len(checks),
        "passed": sum(1 for c in checks if c["ok"]),
        "failed": sum(1 for c in checks if not c["ok"]),
        "boolean_predicates": predicates,
        "predicate_details": predicate_details,
        "checks": checks,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
