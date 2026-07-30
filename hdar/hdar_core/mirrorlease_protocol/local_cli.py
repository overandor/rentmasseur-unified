#!/usr/bin/env python3
"""Local MirrorLease commands for the real right-click/clipboard workflow.

This module is intentionally small: Finder/Shortcuts can call `create`, agents
can call the guarded HTTP adapter, and all authorization still routes through
MirrorLeaseEngine.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

from crypto import HostKeyPair, OwnerKeyPair

from .engine import MirrorLeaseEngine, canonical
from .http_adapter import MirrorLeaseHandler
from http.server import ThreadingHTTPServer


APP_ROOT = Path.home() / "Library/Application Support/MirrorLease"
OWNER_KEY = APP_ROOT / "keys/owner-ed25519.pem"
HOST_KEY = APP_ROOT / "keys/host-ed25519.pem"


def app_root(path: str | None) -> Path:
    return Path(path).expanduser() if path else APP_ROOT


def ensure_owner_key(root: Path) -> OwnerKeyPair:
    key_path = root / "keys/owner-ed25519.pem"
    key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if key_path.exists():
        return OwnerKeyPair.load(str(key_path))
    key = OwnerKeyPair.generate()
    key.save(str(key_path))
    return key


def ensure_host_key(root: Path) -> HostKeyPair:
    key_path = root / "keys/host-ed25519.pem"
    key_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if key_path.exists():
        owner = OwnerKeyPair.load(str(key_path))
        return HostKeyPair(owner.private_key, owner.public_key, "mirrorlease-local-guardian")
    key = HostKeyPair.generate("mirrorlease-local-guardian")
    owner_compatible = OwnerKeyPair(key.private_key, key.public_key)
    owner_compatible.save(str(key_path))
    return key


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_private_record(root: Path, record: dict[str, Any]) -> None:
    leases = root / "leases"
    leases.mkdir(parents=True, exist_ok=True, mode=0o700)
    target = leases / f"{record['invitation_id']}.json"
    tmp = leases / f".{record['invitation_id']}.{uuid.uuid4().hex}.tmp"
    tmp.write_bytes(canonical(record))
    os.chmod(tmp, 0o600)
    os.replace(tmp, target)


def copy_clipboard(text: str) -> bool:
    try:
        subprocess.run(["/usr/bin/pbcopy"], input=text, text=True, check=True)
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        return False


def create_invitation(args: argparse.Namespace) -> dict[str, Any]:
    root = app_root(args.root)
    owner = ensure_owner_key(root)
    now = time.time()
    expires = now + args.hours * 3600
    invitation_id = uuid.uuid4().hex
    mailbox_id = f"mirror-{uuid.uuid4().hex[:12]}"
    token = uuid.uuid4().hex + uuid.uuid4().hex
    challenge = uuid.uuid4().hex
    grants: dict[str, list[str]] = {}
    files: list[dict[str, Any]] = []

    for raw in args.files:
        path = Path(raw).expanduser().resolve()
        if not path.is_file():
            raise SystemExit(f"not a regular file: {path}")
        content_hash = sha256_file(path)
        citizen_id = f"file-{content_hash[:16]}"
        grants[citizen_id] = sorted(set(args.grant))
        files.append({
            "citizen_id": citizen_id,
            "local_path": str(path),
            "content_hash": content_hash,
            "size": path.stat().st_size,
        })

    token_hash = hashlib.sha256(token.encode()).hexdigest()
    claims = {
        "invitation_id": invitation_id,
        "mailbox_id": mailbox_id,
        "token_hash": token_hash,
        "task_description": args.task,
        "recipient_id": args.recipient_id or "",
        "conversation_label": args.conversation_label or "",
        "challenge": challenge,
        "grants": grants,
        "created_at": now,
        "expires_at": expires,
        "issuer_fingerprint": owner.fingerprint,
    }
    signature = owner.sign_bytes(canonical(claims))
    public = {
        "invitation_id": invitation_id,
        "mailbox_id": mailbox_id,
        "token": token,
        "task": args.task,
        "recipient_id": args.recipient_id or "",
        "conversation_label": args.conversation_label or "",
        "challenge": challenge,
        "grants": grants,
        "created_at": now,
        "expires_at": expires,
        "issuer_public_key": owner.public_key_hex,
        "issuer_fingerprint": owner.fingerprint,
        "lease_signature": signature,
    }
    invitation = "mirrorlease:v1:" + base64.urlsafe_b64encode(canonical(public)).decode().rstrip("=")
    record = {
        "version": 1,
        "invitation_id": invitation_id,
        "mailbox_id": mailbox_id,
        "state": "waiting",
        "created_at": now,
        "expires_at": expires,
        "token_hash": token_hash,
        "challenge": challenge,
        "grants": grants,
        "issuer_public_key": owner.public_key_hex,
        "issuer_fingerprint": owner.fingerprint,
        "lease_signature": signature,
        "private_files": files,
    }
    write_private_record(root, record)
    if args.clipboard:
        copy_clipboard(invitation)
    return {
        "ok": True,
        "invitation": invitation,
        "invitation_id": invitation_id,
        "mailbox_id": mailbox_id,
        "expires_at": expires,
        "private_record": str(root / "leases" / f"{invitation_id}.json"),
        "file_count": len(files),
    }


def local_signer(root: Path):
    def sign(data: bytes) -> dict[str, str]:
        key = ensure_host_key(root)
        return {
            "signature": key.sign_bytes(data),
            "issuer_public_key": key.public_key_hex,
            "issuer_fingerprint": key.fingerprint,
        }
    return sign


def approval_dialog(request: dict[str, Any]) -> bool:
    text = (
        f"{request.get('agent_id', 'agent')} requests {request.get('operation', 'access')} "
        f"on {request.get('citizen_id', 'selected file')} via {request.get('transport', 'unknown')}."
    )
    script = (
        'display dialog '
        + json.dumps(text)
        + ' buttons {"Deny", "Allow once"} default button "Deny" with icon caution'
    )
    run = subprocess.run(["/usr/bin/osascript", "-e", script], capture_output=True, text=True)
    return run.returncode == 0 and "Allow once" in run.stdout


def engine_for(root: Path, yes: bool = False) -> MirrorLeaseEngine:
    approver = (lambda _request: True) if yes else approval_dialog
    return MirrorLeaseEngine(root=root, signer=local_signer(root), approver=approver)


def knock(args: argparse.Namespace) -> dict[str, Any]:
    return engine_for(app_root(args.root), yes=args.yes).knock({
        "invitation": args.invitation,
        "agent_id": args.agent_id,
        "conversation_label": args.conversation_label,
    }, args.transport)


def request(args: argparse.Namespace) -> dict[str, Any]:
    return engine_for(app_root(args.root), yes=args.yes).request({
        "invitation_id": args.invitation_id,
        "token": args.token,
        "citizen_id": args.citizen_id,
        "operation": args.operation,
        "agent_id": args.agent_id,
        "conversation_label": args.conversation_label,
    }, args.transport)


def serve(args: argparse.Namespace) -> None:
    root = app_root(args.root)
    server = ThreadingHTTPServer((args.host, args.port), MirrorLeaseHandler)
    server.engine = engine_for(root, yes=args.yes)  # type: ignore[attr-defined]
    print(f"MirrorLease gateway listening on http://{args.host}:{server.server_port}", flush=True)
    server.serve_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description="MirrorLease local guardian")
    parser.add_argument("--root", help="MirrorLease application-support root")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="Create a signed lease invitation for selected files")
    create.add_argument("files", nargs="+")
    create.add_argument("--hours", type=float, default=72)
    create.add_argument("--grant", action="append", choices=["read", "summarize", "verify_hash"], default=["read", "summarize", "verify_hash"])
    create.add_argument("--task", default="Review the selected local file through MirrorLease")
    create.add_argument("--recipient-id", default="")
    create.add_argument("--conversation-label", default="")
    create.add_argument("--clipboard", action="store_true")
    create.set_defaults(func=create_invitation)

    knock_p = sub.add_parser("knock", help="Present an invitation and receive public metadata")
    knock_p.add_argument("invitation")
    knock_p.add_argument("--transport", default="https")
    knock_p.add_argument("--agent-id", default="local-agent")
    knock_p.add_argument("--conversation-label", default="")
    knock_p.add_argument("--yes", action="store_true")
    knock_p.set_defaults(func=knock)

    request_p = sub.add_parser("request", help="Request an operation allowed by a lease")
    request_p.add_argument("invitation_id")
    request_p.add_argument("citizen_id")
    request_p.add_argument("operation", choices=["read", "summarize", "verify_hash"])
    request_p.add_argument("--token", required=True)
    request_p.add_argument("--transport", default="https")
    request_p.add_argument("--agent-id", default="local-agent")
    request_p.add_argument("--conversation-label", default="")
    request_p.add_argument("--yes", action="store_true")
    request_p.set_defaults(func=request)

    serve_p = sub.add_parser("serve", help="Start guarded local HTTP/MCP gateway")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=9443)
    serve_p.add_argument("--yes", action="store_true", help="testing only: bypass owner dialog")
    serve_p.set_defaults(func=serve)

    args = parser.parse_args()
    result = args.func(args)
    if result is not None:
        json.dump(result, sys.stdout, indent=2, sort_keys=True)
        print()


if __name__ == "__main__":
    main()
