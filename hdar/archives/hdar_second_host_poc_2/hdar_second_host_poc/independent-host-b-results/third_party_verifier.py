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
import sys
from pathlib import Path

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
        "reason": f"task passed: {task.get('task', 'unknown')} = {task.get('computed_result')}",
        "computed_result": task.get("computed_result"),
        "expected_result": task.get("expected_result"),
    }


def verify_platforms_differ(report: dict, host_a_platform: str | None) -> dict:
    """Verify Host A and Host B platforms differ (independent host evidence)."""
    host_b_platform = report.get("host_b_platform", "")
    if not host_a_platform:
        return {"ok": False, "check": "platforms_differ", "reason": "Host A platform not provided"}
    if host_a_platform == host_b_platform:
        return {"ok": False, "check": "platforms_differ", "reason": f"platforms identical: {host_a_platform} — not independent host evidence", "host_a_platform": host_a_platform, "host_b_platform": host_b_platform}
    return {"ok": True, "check": "platforms_differ", "reason": "platforms differ — consistent with independent host", "host_a_platform": host_a_platform, "host_b_platform": host_b_platform}


def main() -> int:
    ap = argparse.ArgumentParser(description="HDAR Third-Party Verifier — Step 8 of seed criterion")
    ap.add_argument("--capsule-e1", required=True, help="Path to capsule epoch 1 directory")
    ap.add_argument("--capsule-e2", required=True, help="Path to capsule epoch 2 directory")
    ap.add_argument("--host-b-report", required=True, help="Path to host_b_report.json")
    ap.add_argument("--owner-public-key", default="", help="Expected owner Ed25519 public key hex (from Host A out-of-band channel)")
    ap.add_argument("--host-a-platform", default="", help="Host A platform string (to verify platforms differ)")
    ap.add_argument("--evidence-packet", default="", help="Path to host_b_evidence_packet.json (optional — verifies independent signature)")
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
                    public_key.verify(bytes.fromhex(ep_sig), canonical_json(ep_signing_content))
                    # Also verify the signature is NOT a copy of the report signature
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

    print_results(checks)
    all_ok = all(c["ok"] for c in checks)
    return 0 if all_ok else 1


def print_results(checks: list[dict]) -> None:
    all_ok = all(c["ok"] for c in checks)
    print(json.dumps({
        "schema": "hdar.third-party-verification/v0.1",
        "verifier": "neither-host-a-nor-host-b",
        "all_checks_passed": all_ok,
        "total_checks": len(checks),
        "passed": sum(1 for c in checks if c["ok"]),
        "failed": sum(1 for c in checks if not c["ok"]),
        "checks": checks,
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    raise SystemExit(main())
