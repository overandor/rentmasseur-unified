"""One authority path shared by Finder, HTTPS, MCP, GPT Actions, and email.

Adapters may parse different wire formats, but they are not allowed to make
authorization decisions. Every inbound message becomes the same canonical
knock/request and every outcome becomes a hash-linked, device-signed receipt.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from crypto import PublicKey


ALLOWED_OPERATIONS = {"read", "summarize", "verify_hash"}
LIVE_STATES = {"open", "waiting", "used"}
FINAL_STATES = {"expired", "revoked", "destroyed"}


class ProtocolError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.status = status

    def to_dict(self) -> dict:
        return {"ok": False, "error": self.code, "message": str(self)}


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def digest(value: Any) -> str:
    raw = value if isinstance(value, bytes) else canonical(value)
    return hashlib.sha256(raw).hexdigest()


def parse_invitation(text: str) -> dict:
    prefix = "mirrorlease:v1:"
    if not isinstance(text, str) or not text.startswith(prefix):
        raise ProtocolError("invalid_invitation", "Expected a mirrorlease:v1 invitation.")
    encoded = text[len(prefix):]
    try:
        raw = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
        payload = json.loads(raw)
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise ProtocolError("invalid_invitation", "The invitation payload is malformed.") from exc
    required = {
        "invitation_id", "mailbox_id", "token", "challenge", "grants",
        "created_at", "expires_at", "issuer_public_key", "issuer_fingerprint",
        "lease_signature",
    }
    if not required.issubset(payload):
        raise ProtocolError("invalid_invitation", "The invitation is missing signed fields.")
    return payload


def signed_lease_claims(invitation: dict) -> dict:
    return {
        "invitation_id": invitation["invitation_id"],
        "mailbox_id": invitation["mailbox_id"],
        "token_hash": hashlib.sha256(invitation["token"].encode()).hexdigest(),
        "task_description": invitation.get("task", ""),
        "recipient_id": invitation.get("recipient_id", ""),
        "conversation_label": invitation.get("conversation_label", ""),
        "challenge": invitation["challenge"],
        "grants": invitation["grants"],
        "created_at": invitation["created_at"],
        "expires_at": invitation["expires_at"],
        "issuer_fingerprint": invitation["issuer_fingerprint"],
    }


class CommandSigner:
    """Signs canonical receipts without extracting the Keychain private key."""

    def __init__(self, helper: str):
        self.helper = helper

    def __call__(self, data: bytes) -> dict:
        run = subprocess.run(
            [self.helper, "--sign-stdin"], input=data, capture_output=True, check=False
        )
        if run.returncode != 0:
            raise ProtocolError("signing_failed", "The local device could not sign the receipt.", 500)
        return json.loads(run.stdout)


class CommandApprover:
    """Uses the native owner dialog; it receives public labels, never file bytes."""

    def __init__(self, helper: str):
        self.helper = helper

    def __call__(self, request: dict) -> bool:
        run = subprocess.run(
            [self.helper, "--approve-stdin"], input=canonical(request), capture_output=True, check=False
        )
        if run.returncode != 0:
            return False
        try:
            return bool(json.loads(run.stdout).get("approved"))
        except (ValueError, TypeError, json.JSONDecodeError):
            return False


class MirrorLeaseEngine:
    def __init__(
        self,
        root: Optional[Path] = None,
        signer: Optional[Callable[[bytes], dict]] = None,
        approver: Optional[Callable[[dict], bool]] = None,
        clock: Callable[[], float] = time.time,
    ):
        self.root = Path(root or (Path.home() / "Library/Application Support/MirrorLease"))
        self.leases = self.root / "leases"
        self.audit = self.root / "audit.jsonl"
        helper = str(self.root / "bin/mirrorlease-share")
        self.signer = signer or CommandSigner(helper)
        self.approver = approver or CommandApprover(helper)
        self.clock = clock

    def _lease_path(self, invitation_id: str) -> Path:
        if not invitation_id or any(c not in "0123456789abcdef" for c in invitation_id.lower()):
            raise ProtocolError("invalid_invitation_id", "Invitation id is not valid.")
        return self.leases / f"{invitation_id}.json"

    def _load(self, invitation_id: str) -> dict:
        path = self._lease_path(invitation_id)
        try:
            record = json.loads(path.read_text())
        except FileNotFoundError as exc:
            raise ProtocolError("unknown_lease", "This lease is not present on this laptop.", 404) from exc
        except json.JSONDecodeError as exc:
            raise ProtocolError("corrupt_lease", "The private lease record is invalid.", 500) from exc
        now = self.clock()
        if record.get("state") in LIVE_STATES and now >= float(record["expires_at"]):
            record["state"] = "expired"
            record["expired_at"] = now
            self._save(record)
            self._receipt("lifecycle", record, {"event": "expired"}, granted=False)
        return record

    def _save(self, record: dict) -> None:
        self.leases.mkdir(parents=True, exist_ok=True, mode=0o700)
        path = self._lease_path(record["invitation_id"])
        fd, name = tempfile.mkstemp(dir=str(self.leases), prefix=".lease-", text=True)
        try:
            with os.fdopen(fd, "w") as out:
                json.dump(record, out, sort_keys=True, separators=(",", ":"))
            os.chmod(name, 0o600)
            os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def _verify(self, invitation: dict, record: dict) -> None:
        claims = signed_lease_claims(invitation)
        try:
            valid = PublicKey.from_hex(invitation["issuer_public_key"]).verify_bytes(
                canonical(claims), invitation["lease_signature"]
            )
        except (ValueError, TypeError):
            valid = False
        if not valid:
            raise ProtocolError("invalid_signature", "The device lease signature is invalid.", 403)
        comparisons = {
            "mailbox_id": invitation["mailbox_id"],
            "token_hash": claims["token_hash"],
            "challenge": invitation["challenge"],
            "grants": invitation["grants"],
            "issuer_public_key": invitation["issuer_public_key"],
            "lease_signature": invitation["lease_signature"],
        }
        if any(record.get(k) != v for k, v in comparisons.items()):
            raise ProtocolError("lease_mismatch", "The public invitation does not match the private lease.", 403)
        if record.get("state") in FINAL_STATES:
            raise ProtocolError(record["state"], f"The lease is {record['state']}.", 410)

    def _normalize(self, message: dict, transport: str, kind: str) -> dict:
        if transport not in {"finder", "https", "gpt_action", "mcp", "email"}:
            raise ProtocolError("unknown_transport", "Transport is not registered.")
        normalized = {
            "protocol": "mirrorlease/v1",
            "kind": kind,
            "request_id": str(message.get("request_id") or uuid.uuid4()),
            "transport": transport,
            "agent_id": str(message.get("agent_id") or "unlabeled-agent")[:160],
            "conversation_label": str(message.get("conversation_label") or "")[:160],
            "nonce": str(message.get("nonce") or uuid.uuid4().hex)[:160],
            "received_at": self.clock(),
        }
        if kind == "request":
            normalized["invitation_id"] = str(message.get("invitation_id") or "")
            normalized["citizen_id"] = str(message.get("citizen_id") or "")
            normalized["operation"] = str(message.get("operation") or "")
        return normalized

    def _receipt(self, kind: str, record: dict, event: dict, granted: bool) -> dict:
        previous = "0" * 64
        if self.audit.exists():
            try:
                previous = json.loads(self.audit.read_text().splitlines()[-1])["receipt_hash"]
            except (IndexError, KeyError, json.JSONDecodeError):
                raise ProtocolError("audit_corrupt", "The audit chain cannot be extended safely.", 500)
        body = {
            "protocol": "mirrorlease/v1",
            "receipt_id": uuid.uuid4().hex,
            "kind": kind,
            "invitation_id": record["invitation_id"],
            "mailbox_id": record["mailbox_id"],
            "lease_state": record["state"],
            "granted": granted,
            "event": event,
            "timestamp": self.clock(),
            "origin_request_hash": digest({
                "invitation_id": record["invitation_id"],
                "challenge": record["challenge"],
                "grants": record["grants"],
            }),
            "previous_receipt_hash": previous,
        }
        body["receipt_hash"] = digest(body)
        signature = self.signer(canonical(body))
        body.update({
            "host_signature": signature["signature"],
            "issuer_public_key": signature["issuer_public_key"],
            "issuer_fingerprint": signature["issuer_fingerprint"],
        })
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.audit.open("a") as out:
            out.write(json.dumps(body, sort_keys=True, separators=(",", ":")) + "\n")
        os.chmod(self.audit, 0o600)
        return body

    def knock(self, message: dict, transport: str) -> dict:
        invitation = parse_invitation(message.get("invitation", ""))
        record = self._load(invitation["invitation_id"])
        self._verify(invitation, record)
        knock = self._normalize(message, transport, "knock")
        receipt = self._receipt("knock", record, knock, granted=True)
        files = [{k: f[k] for k in ("citizen_id", "content_hash", "size")}
                 for f in record.get("private_files", [])]
        return {
            "ok": True,
            "protocol": "mirrorlease/v1",
            "lease": {
                "invitation_id": record["invitation_id"],
                "mailbox_id": record["mailbox_id"],
                "state": record["state"],
                "expires_at": record["expires_at"],
                "grants": record["grants"],
            },
            "files": files,
            "receipt": receipt,
        }

    def request(self, message: dict, transport: str) -> dict:
        request = self._normalize(message, transport, "request")
        record = self._load(request["invitation_id"])
        token = str(message.get("token") or "")
        if not token or not secrets_equal(record["token_hash"], hashlib.sha256(token.encode()).hexdigest()):
            raise ProtocolError("unauthorized", "The lease capability is missing or invalid.", 401)
        operation = request["operation"]
        citizen_id = request["citizen_id"]
        if operation not in ALLOWED_OPERATIONS or operation not in record.get("grants", {}).get(citizen_id, []):
            receipt = self._receipt("request", record, request, granted=False)
            raise ProtocolError("not_permitted", f"{operation!r} is outside this signed lease.", 403)
        private_file = next((f for f in record.get("private_files", []) if f["citizen_id"] == citizen_id), None)
        if private_file is None:
            raise ProtocolError("unknown_file", "The file is not enrolled in this lease.", 404)
        if not self.approver(request):
            receipt = self._receipt("request", record, {**request, "decision": "denied"}, granted=False)
            return {"ok": False, "error": "owner_denied", "lease_state": record["state"], "receipt": receipt}

        path = Path(private_file["local_path"])
        current_hash = file_hash(path)
        if current_hash != private_file["content_hash"]:
            receipt = self._receipt("request", record, {**request, "decision": "file_changed"}, granted=False)
            return {"ok": False, "error": "file_changed", "lease_state": record["state"], "receipt": receipt}
        result: Dict[str, Any] = {"citizen_id": citizen_id, "content_hash": current_hash}
        if operation == "read":
            result["data"] = path.read_text(errors="replace")
        elif operation == "summarize":
            text = path.read_text(errors="replace")
            result["summary"] = " ".join(text.split())[:500]
        else:
            result["verified"] = True
        record["state"] = "used"
        record.setdefault("used_at", self.clock())
        self._save(record)
        receipt = self._receipt("request", record, {**request, "result_hash": digest(result)}, granted=True)
        return {"ok": True, "lease_state": record["state"], "result": result, "receipt": receipt}

    def transition(self, invitation_id: str, state: str) -> dict:
        if state not in {"revoked", "destroyed"}:
            raise ProtocolError("invalid_transition", "Only revoke or destroy is owner initiated.")
        record = self._load(invitation_id)
        record["state"] = state
        record[f"{state}_at"] = self.clock()
        if state == "destroyed":
            record["token_hash"] = ""
            record["grants"] = {}
            record["private_files"] = []
        self._save(record)
        return {"ok": True, "state": state, "receipt": self._receipt("lifecycle", record, {"event": state}, False)}


def secrets_equal(left: str, right: str) -> bool:
    import hmac
    return hmac.compare_digest(str(left), str(right))


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()
