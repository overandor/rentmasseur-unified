#!/usr/bin/env python3
"""Emit an evidence manifest bound to source, binary, tools, and test artifacts.

Signing is explicit: pass an Ed25519 PEM private key with --private-key. The
script never creates or stores signing keys implicitly.
"""
import argparse, hashlib, json, pathlib, subprocess, platform, datetime

def run(*args):
    try: return subprocess.check_output(args, text=True, stderr=subprocess.STDOUT).strip()
    except Exception as exc: return f"unavailable: {exc}"

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""): h.update(block)
    return h.hexdigest()

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="pipeline_output/evidence/manifest.json")
    p.add_argument("--binary", default="native/hdar_native")
    p.add_argument("--private-key", help="Ed25519 PEM key used to sign the manifest")
    p.add_argument("artifacts", nargs="*")
    a = p.parse_args()
    root = pathlib.Path(run("git", "rev-parse", "--show-toplevel"))
    tracked = subprocess.check_output(["git", "ls-files", "-z"], cwd=root).split(b"\0")
    source_hash = hashlib.sha256()
    files = []
    for raw in sorted(x for x in tracked if x):
        rel = raw.decode(); path = root / rel
        if path.is_file() and not rel.startswith(("pipeline_output/", "sandbox/")):
            digest = sha(path); files.append({"path": rel, "sha256": digest})
            source_hash.update(rel.encode() + b"\0" + digest.encode() + b"\0")
    data = {"schema": "hdar.evidence.v1", "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "git_commit": run("git", "rev-parse", "HEAD"), "git_status": run("git", "status", "--porcelain"),
            "source_tree_sha256": source_hash.hexdigest(), "compiler": run("clang++", "--version"),
            "host": {"platform": platform.platform(), "machine": platform.machine()},
            "container_cli": run("container", "--version"), "files": files}
    for item in [a.binary, *a.artifacts]:
        path = root / item
        if path.is_file(): data.setdefault("artifacts", []).append({"path": item, "sha256": sha(path)})
    out = root / a.output; out.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(data, sort_keys=True, indent=2).encode() + b"\n"
    out.write_bytes(payload)
    if a.private_key:
        sig = out.with_suffix(out.suffix + ".sig")
        subprocess.run(["openssl", "pkeyutl", "-sign", "-inkey", a.private_key, "-rawin", "-in", str(out), "-out", str(sig)], check=True)
        print(f"manifest={out}\nsignature={sig}")
    else: print(f"manifest={out}\nUNSIGNED: provide --private-key for evidence-grade signing")

if __name__ == "__main__": main()
