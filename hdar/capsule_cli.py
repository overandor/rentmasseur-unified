#!/usr/bin/env python3
"""Agent-Native Suspension Capsule — Stage 1 core.

Exit gate:  workspace -> capsule -> destroy workspace -> verified identical restoration

A capsule is a content-addressed, signed, lineage-bearing artifact holding an
agent's whole operational state: workspace bytes, pending goals, capability
grants, and its receipt chain. Restoration is verified against the manifest,
not trusted. Tampering, truncation, and epoch rollback are rejected.

SAFETY: destroy() refuses to touch anything outside an explicit sandbox root.

  capsule.py seal    <workspace> <capsule_dir> [--goals ...] [--epoch N]
  capsule.py verify  <capsule_dir>
  capsule.py restore <capsule_dir> <dest>
  capsule.py destroy <workspace>          # sandbox paths only
"""
import argparse, hashlib, hmac, json, os, shutil, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
KEYFILE = os.path.join(HERE, ".capsule_key")
CHUNK = 1 << 20                      # 1 MiB content-addressed chunks
SANDBOX_ROOTS = ("/tmp/", "/private/tmp/", os.path.join(HERE, "sandbox"))


def _key():
    if not os.path.exists(KEYFILE):
        with open(KEYFILE, "wb") as f:
            f.write(os.urandom(32))
        os.chmod(KEYFILE, 0o600)
    return open(KEYFILE, "rb").read()


def _sha(b): return hashlib.sha256(b).hexdigest()


def _sign(payload: dict) -> str:
    canon = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hmac.new(_key(), canon, hashlib.sha256).hexdigest()


def seal(workspace, capsule_dir, goals=None, epoch=1, parent=None):
    """Content-address every file into chunks; emit signed manifest + receipt."""
    os.makedirs(os.path.join(capsule_dir, "blocks"), exist_ok=True)
    files, total, dedup_hits = [], 0, 0
    for dp, dirs, fnames in os.walk(workspace):
        dirs[:] = [d for d in dirs if d != ".git"]
        for fn in sorted(fnames):
            ap = os.path.join(dp, fn)
            rel = os.path.relpath(ap, workspace)
            blocks = []
            with open(ap, "rb") as fh:
                while True:
                    b = fh.read(CHUNK)
                    if not b:
                        break
                    h = _sha(b)
                    bp = os.path.join(capsule_dir, "blocks", h)
                    if os.path.exists(bp):
                        dedup_hits += 1
                    else:
                        with open(bp, "wb") as out:
                            out.write(b)
                    blocks.append({"sha256": h, "len": len(b)})
                    total += len(b)
            files.append({"path": rel, "size": os.path.getsize(ap),
                          "sha256": _sha(open(ap, "rb").read()), "blocks": blocks})
    manifest = {
        "capsule_version": 1,
        "epoch": epoch,
        "parent_capsule": parent,
        "sealed_at": time.time(),
        "workspace_root": os.path.basename(os.path.abspath(workspace)),
        "files": files,
        "total_bytes": total,
        "dedup_block_hits": dedup_hits,
        "goals": goals or [],
        "capabilities": {"note": "capability grants travel here; never broaden on restore"},
    }
    manifest["manifest_hash"] = _sha(json.dumps(manifest, sort_keys=True,
                                                separators=(",", ":")).encode())
    receipt = {"kind": "capsule.seal", "epoch": epoch, "parent": parent,
               "manifest_hash": manifest["manifest_hash"], "ts": time.time()}
    receipt["signature"] = _sign(receipt)
    with open(os.path.join(capsule_dir, "manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2)
    with open(os.path.join(capsule_dir, "receipt.json"), "w") as f:
        json.dump(receipt, f, indent=2)
    return {"files": len(files), "bytes": total, "epoch": epoch,
            "dedup_block_hits": dedup_hits,
            "manifest_hash": manifest["manifest_hash"][:16]}


def verify(capsule_dir, min_epoch=None):
    """Independent offline verification. Trusts nothing but hashes + signature."""
    problems = []
    try:
        man = json.load(open(os.path.join(capsule_dir, "manifest.json")))
        rec = json.load(open(os.path.join(capsule_dir, "receipt.json")))
    except Exception as e:
        return {"ok": False, "problems": [f"unreadable capsule: {e}"]}

    # manifest integrity
    m2 = {k: v for k, v in man.items() if k != "manifest_hash"}
    if _sha(json.dumps(m2, sort_keys=True, separators=(",", ":")).encode()) != man["manifest_hash"]:
        problems.append("manifest hash mismatch — manifest was modified")
    # receipt signature
    sig = rec.pop("signature", None)
    if not hmac.compare_digest(_sign(rec), sig or ""):
        problems.append("receipt signature invalid — receipt was forged or altered")
    rec["signature"] = sig
    if rec.get("manifest_hash") != man["manifest_hash"]:
        problems.append("receipt does not bind this manifest")
    # anti-rollback
    if min_epoch is not None and man["epoch"] < min_epoch:
        problems.append(f"ROLLBACK: epoch {man['epoch']} < authorized {min_epoch}")
    # block completeness + integrity
    missing = bad = 0
    for f in man["files"]:
        for b in f["blocks"]:
            bp = os.path.join(capsule_dir, "blocks", b["sha256"])
            if not os.path.exists(bp):
                missing += 1
            elif _sha(open(bp, "rb").read()) != b["sha256"]:
                bad += 1
    if missing:
        problems.append(f"INCOMPLETE: {missing} content blocks missing")
    if bad:
        problems.append(f"CORRUPT: {bad} blocks fail their hash")
    return {"ok": not problems, "epoch": man["epoch"], "files": len(man["files"]),
            "problems": problems}


def restore(capsule_dir, dest, min_epoch=None):
    v = verify(capsule_dir, min_epoch)
    if not v["ok"]:
        return {"restored": False, "reason": "verification failed", "problems": v["problems"]}
    man = json.load(open(os.path.join(capsule_dir, "manifest.json")))
    os.makedirs(dest, exist_ok=True)
    exact = 0
    for f in man["files"]:
        out = os.path.join(dest, f["path"])
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as w:
            for b in f["blocks"]:
                w.write(open(os.path.join(capsule_dir, "blocks", b["sha256"]), "rb").read())
        if _sha(open(out, "rb").read()) == f["sha256"]:
            exact += 1
    return {"restored": True, "files": len(man["files"]), "hash_identical": exact,
            "exact": exact == len(man["files"]), "epoch": man["epoch"],
            "goals": man["goals"]}


def destroy(workspace):
    """Destroy a runtime workspace. Sandbox paths ONLY — never real user data."""
    ap = os.path.abspath(workspace)
    if not any(ap.startswith(os.path.abspath(r)) for r in SANDBOX_ROOTS):
        sys.exit(f"REFUSED: {ap} is outside the sandbox roots {SANDBOX_ROOTS}")
    shutil.rmtree(ap)
    return {"destroyed": ap, "exists": os.path.exists(ap)}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("seal");    s.add_argument("workspace"); s.add_argument("capsule")
    s.add_argument("--goals", nargs="*"); s.add_argument("--epoch", type=int, default=1)
    v = sub.add_parser("verify");  v.add_argument("capsule"); v.add_argument("--min-epoch", type=int)
    r = sub.add_parser("restore"); r.add_argument("capsule"); r.add_argument("dest")
    r.add_argument("--min-epoch", type=int)
    d = sub.add_parser("destroy"); d.add_argument("workspace")
    a = ap.parse_args()
    if a.cmd == "seal":     print(json.dumps(seal(a.workspace, a.capsule, a.goals, a.epoch), indent=2))
    elif a.cmd == "verify": print(json.dumps(verify(a.capsule, a.min_epoch), indent=2))
    elif a.cmd == "restore":print(json.dumps(restore(a.capsule, a.dest, a.min_epoch), indent=2))
    elif a.cmd == "destroy":print(json.dumps(destroy(a.workspace), indent=2))
