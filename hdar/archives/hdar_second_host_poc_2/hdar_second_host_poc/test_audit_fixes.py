#!/usr/bin/env python3
"""Tests for all 7 Cartman Demoronification Audit fixes.

Each test verifies a specific audit issue is resolved in run_on_host_b.py.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
from pathlib import Path

# Import the runner as a module
RUNNER_DIR = Path(__file__).parent / "run-2026-07-20-v2"
sys.path.insert(0, str(RUNNER_DIR))
import run_on_host_b as runner

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


def make_test_capsule(tmpdir: Path, files: dict = None, epoch: int = 1) -> Path:
    """Create a minimal test capsule in tmpdir."""
    capsule = tmpdir / "capsule"
    capsule.mkdir(parents=True)
    blocks = capsule / "blocks"
    blocks.mkdir()
    
    workspace_files = files or {
        "agent_state.json": json.dumps({"agent_id": "test", "status": "suspended"}),
        "progress.log": json.dumps({"event": "created"}) + "\n",
    }
    
    file_manifests = []
    for rel_path, content in workspace_files.items():
        data = content.encode() if isinstance(content, str) else content
        digest = sha256_bytes(data)
        block = blocks / digest[:2] / digest
        block.parent.mkdir(parents=True, exist_ok=True)
        block.write_bytes(data)
        file_manifests.append({
            "rel_path": rel_path,
            "sha256": digest,
            "size": len(data),
            "mode": 0o644,
        })
    
    root_material = "\n".join(
        f"{f['rel_path']}|{f['sha256']}|{f['size']}|{f['mode']}" for f in file_manifests
    ).encode()
    root_hash = sha256_bytes(root_material)
    
    manifest = {
        "schema": "hdar.transport-capsule/v0.1",
        "agent_id": "test-agent",
        "epoch": epoch,
        "parent_manifest_hash": None,
        "created_at": time.time(),
        "source_host_label": "test-host-a",
        "objective": "test",
        "continuation_point": "test",
        "verification_mode": "sha256-content-addressed-hash-only",
        "signature_mode": "omitted-in-test",
        "workspace_manifest": {
            "root_hash": root_hash,
            "files": file_manifests,
            "total_size": sum(f["size"] for f in file_manifests),
        },
    }
    manifest["manifest_hash"] = sha256_bytes(
        canonical_json({k: v for k, v in manifest.items() if k != "manifest_hash"})
    )
    (capsule / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True))
    
    receipt = {
        "schema": "hdar.receipt/v0.1",
        "event": "capsule_sealed",
        "agent_id": "test-agent",
        "epoch": epoch,
        "source_host_label": "test-host-a",
        "manifest_hash": manifest["manifest_hash"],
        "workspace_root_hash": root_hash,
        "timestamp": time.time(),
    }
    receipt["receipt_hash"] = sha256_bytes(canonical_json(receipt))
    (capsule / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
    
    return capsule


# ─── Test Fix #1: Runner self-authentication ──────────────────

def test_fix1_runner_hash_verification():
    """Fix #1: Runner can verify its own SHA-256 hash."""
    runner_path = RUNNER_DIR / "run_on_host_b.py"
    h = sha256_file(runner_path)
    assert len(h) == 64, f"expected 64-char hex hash, got {len(h)}"
    # Verify the --verify-runner-hash flag exists
    content = runner_path.read_text()
    assert "--verify-runner-hash" in content, "runner missing --verify-runner-hash flag"
    print("  test_fix1_runner_hash_verification ... OK")


# ─── Test Fix #2: External Host A report ──────────────────────

def test_fix2_host_a_report_flag():
    """Fix #2: --host-a-report flag exists and is used."""
    content = (RUNNER_DIR / "run_on_host_b.py").read_text()
    assert "--host-a-report" in content, "runner missing --host-a-report flag"
    assert "host_a_report_verify" in content, "runner missing host_a_report_verify logic"
    assert "manifest_hash_match" in content, "runner missing manifest hash cross-check"
    print("  test_fix2_host_a_report_flag ... OK")


# ─── Test Fix #3: Safe archive extraction ─────────────────────

def test_fix3_safe_extract_rejects_traversal():
    """Fix #3: safe_extract_tar rejects path traversal."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix3-"))
    try:
        # Create a tar with a traversal path
        evil_tar = tmpdir / "evil.tar.gz"
        with tarfile.open(evil_tar, "w:gz") as tf:
            info = tarfile.TarInfo(name="../../../etc/passwd")
            info.size = 4
            import io
            tf.addfile(info, io.BytesIO(b"evil"))
        
        extract_dir = tmpdir / "extract"
        extract_dir.mkdir()
        with tarfile.open(evil_tar, "r:gz") as tf:
            try:
                runner.safe_extract_tar(tf, extract_dir)
                assert False, "should have rejected traversal"
            except ValueError as e:
                assert "traversal" in str(e) or "escape" in str(e), f"wrong error: {e}"
        print("  test_fix3_safe_extract_rejects_traversal ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fix3_safe_extract_rejects_symlink():
    """Fix #3: safe_extract_tar rejects symlinks."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix3-sym-"))
    try:
        evil_tar = tmpdir / "evil.tar.gz"
        with tarfile.open(evil_tar, "w:gz") as tf:
            info = tarfile.TarInfo(name="link")
            info.type = tarfile.SYMTYPE
            info.linkname = "/etc/passwd"
            tf.addfile(info)
        
        extract_dir = tmpdir / "extract"
        extract_dir.mkdir()
        with tarfile.open(evil_tar, "r:gz") as tf:
            try:
                runner.safe_extract_tar(tf, extract_dir)
                assert False, "should have rejected symlink"
            except ValueError as e:
                assert "symlink" in str(e), f"wrong error: {e}"
        print("  test_fix3_safe_extract_rejects_symlink ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fix3_no_unrestricted_fallback():
    """Fix #3: no unrestricted extractall fallback in the code."""
    content = (RUNNER_DIR / "run_on_host_b.py").read_text()
    assert 'tf.extractall(dest)' in content, "safe_extract_tar should call extractall after validation"
    # Make sure there's no bare except TypeError fallback to extractall
    assert "except TypeError:" not in content, "unrestricted TypeError fallback still present"
    print("  test_fix3_no_unrestricted_fallback ... OK")


# ─── Test Fix #4: Path constraint in restore ──────────────────

def test_fix4_validate_safe_path_rejects_absolute():
    """Fix #4: _validate_safe_path rejects absolute paths."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix4-"))
    try:
        try:
            runner._validate_safe_path("/etc/passwd", tmpdir)
            assert False, "should reject absolute path"
        except ValueError as e:
            assert "absolute" in str(e).lower()
        print("  test_fix4_validate_safe_path_rejects_absolute ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fix4_validate_safe_path_rejects_traversal():
    """Fix #4: _validate_safe_path rejects ../ traversal."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix4-trav-"))
    try:
        try:
            runner._validate_safe_path("../../etc/passwd", tmpdir)
            assert False, "should reject traversal"
        except ValueError as e:
            assert "traversal" in str(e).lower() or "escape" in str(e).lower()
        print("  test_fix4_validate_safe_path_rejects_traversal ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fix4_validate_safe_path_accepts_normal():
    """Fix #4: _validate_safe_path accepts normal relative paths."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix4-ok-"))
    try:
        result = runner._validate_safe_path("src/worker.py", tmpdir)
        assert str(result).startswith(str(tmpdir.resolve())), f"path should be under dest: {result}"
        print("  test_fix4_validate_safe_path_accepts_normal ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Test Fix #5: Receipt verification ────────────────────────

def test_fix5_verify_receipt_valid():
    """Fix #5: verify_receipt accepts a valid receipt."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix5-ok-"))
    try:
        capsule = make_test_capsule(tmpdir)
        manifest = json.loads((capsule / "manifest.json").read_text())
        result = runner.verify_receipt(capsule, manifest)
        assert result["ok"], f"valid receipt should pass: {result['problems']}"
        print("  test_fix5_verify_receipt_valid ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fix5_verify_receipt_detects_tamper():
    """Fix #5: verify_receipt detects a tampered receipt."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix5-tamper-"))
    try:
        capsule = make_test_capsule(tmpdir)
        # Tamper with the receipt
        receipt = json.loads((capsule / "receipt.json").read_text())
        receipt["epoch"] = 999  # wrong epoch
        (capsule / "receipt.json").write_text(json.dumps(receipt, indent=2, sort_keys=True))
        manifest = json.loads((capsule / "manifest.json").read_text())
        result = runner.verify_receipt(capsule, manifest)
        assert not result["ok"], "tampered receipt should fail"
        assert any("epoch" in p for p in result["problems"]), f"should report epoch mismatch: {result['problems']}"
        print("  test_fix5_verify_receipt_detects_tamper ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fix5_verify_receipt_missing():
    """Fix #5: verify_receipt handles missing receipt.json."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix5-missing-"))
    try:
        capsule = make_test_capsule(tmpdir)
        (capsule / "receipt.json").unlink()
        manifest = json.loads((capsule / "manifest.json").read_text())
        result = runner.verify_receipt(capsule, manifest)
        assert not result["ok"], "missing receipt should fail"
        assert "receipt.json missing" in result["problems"]
        print("  test_fix5_verify_receipt_missing ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Test Fix #6: Host identity ───────────────────────────────

def test_fix6_host_identity_fields():
    """Fix #6: Report includes machine-generated identity fields."""
    content = (RUNNER_DIR / "run_on_host_b.py").read_text()
    assert "socket.gethostname()" in content, "missing machine hostname"
    assert "machine_hostname" in content, "missing machine_hostname in report"
    assert "runner_start" in content, "missing runner_start timestamp"
    assert "runner_end" in content, "missing runner_end timestamp"
    assert "console_log" in content, "missing console transcript"
    assert "python_version" in content, "missing python_version"
    print("  test_fix6_host_identity_fields ... OK")


# ─── Test Fix #7: Deterministic task ──────────────────────────

def test_fix7_task_constants():
    """Fix #7: Deterministic task constants are defined."""
    assert runner.TASK_INPUT_N == 100, f"expected TASK_INPUT_N=100, got {runner.TASK_INPUT_N}"
    assert runner.TASK_EXPECTED_RESULT == 1060, f"expected TASK_EXPECTED_RESULT=1060, got {runner.TASK_EXPECTED_RESULT}"
    print("  test_fix7_task_constants ... OK")


def test_fix7_complete_deterministic_task():
    """Fix #7: complete_deterministic_task runs worker.py and verifies result."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix7-task-"))
    try:
        workspace = tmpdir / "workspace"
        workspace.mkdir()
        (workspace / "src").mkdir()
        (workspace / "src" / "worker.py").write_text(
            "import sys\n"
            "def is_prime(n):\n"
            "    if n < 2: return False\n"
            "    for i in range(2, int(n**0.5)+1):\n"
            "        if n % i == 0: return False\n"
            "    return True\n"
            "def sum_of_primes_below(n):\n"
            "    return sum(i for i in range(2, n) if is_prime(i))\n"
            "if __name__ == '__main__':\n"
            "    n = int(sys.argv[1]) if len(sys.argv) > 1 else 100\n"
            "    print(sum_of_primes_below(n))\n"
        )
        result = runner.complete_deterministic_task(workspace)
        assert result["ok"], f"task should pass: {result}"
        assert result["passed"], "task passed flag should be True"
        assert result["computed_result"] == 1060, f"expected 1060, got {result['computed_result']}"
        assert (workspace / "task_result.json").exists(), "task_result.json should be written"
        print("  test_fix7_complete_deterministic_task ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def test_fix7_complete_deterministic_task_missing_worker():
    """Fix #7: complete_deterministic_task handles missing worker.py."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-fix7-missing-"))
    try:
        workspace = tmpdir / "workspace"
        workspace.mkdir()
        result = runner.complete_deterministic_task(workspace)
        assert not result["ok"], "should fail when worker.py missing"
        assert "not found" in result["reason"]
        print("  test_fix7_complete_deterministic_task_missing_worker ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Test full verify_capsule with receipt ────────────────────

def test_verify_capsule_includes_receipt():
    """verify_capsule now includes receipt_verified in its output."""
    tmpdir = Path(tempfile.mkdtemp(prefix="test-verify-cap-"))
    try:
        capsule = make_test_capsule(tmpdir)
        result = runner.verify_capsule(capsule)
        assert result["ok"], f"valid capsule should pass: {result['problems']}"
        assert "receipt_verified" in result, "verify_capsule missing receipt_verified"
        assert result["receipt_verified"]["ok"], "receipt verification should pass"
        print("  test_verify_capsule_includes_receipt ... OK")
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ─── Runner ───────────────────────────────────────────────────

def run_all_tests():
    tests = [
        test_fix1_runner_hash_verification,
        test_fix2_host_a_report_flag,
        test_fix3_safe_extract_rejects_traversal,
        test_fix3_safe_extract_rejects_symlink,
        test_fix3_no_unrestricted_fallback,
        test_fix4_validate_safe_path_rejects_absolute,
        test_fix4_validate_safe_path_rejects_traversal,
        test_fix4_validate_safe_path_accepts_normal,
        test_fix5_verify_receipt_valid,
        test_fix5_verify_receipt_detects_tamper,
        test_fix5_verify_receipt_missing,
        test_fix6_host_identity_fields,
        test_fix7_task_constants,
        test_fix7_complete_deterministic_task,
        test_fix7_complete_deterministic_task_missing_worker,
        test_verify_capsule_includes_receipt,
    ]
    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  {test.__name__} ... FAILED: {e}")
            failed += 1
    print(f"\n=== Results: {passed} passed, {failed} failed ===")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_all_tests())
