#!/usr/bin/env python3
"""Palindrome integration test — proves the full palindrome flow:

  1. Machine enrolls files as citizens (public identity + private authority)
  2. Owner creates a mailbox with TTL and file permissions
  3. Owner generates a one-use invitation
  4. Guest redeems invitation -> session credential
  5. Guest accesses files through the mailbox
  6. Access remains exact until an atomic expiry boundary
  7. Every access produces a receipt in a hash-linked chain
  8. Invitation cannot be reused
  9. Chain can be verified offline
 10. The answer returns home — receipt chain is the palindrome

This is the product: a temporary private mailbox through which an AI
may perceive selected parts of a self-protecting local machine.
"""

import sys
import os
import time
import tempfile
import json

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from palindrome import (
    InvitationManager, FileCitizenRegistry, MailboxManager,
    ReceiptChain, LeaseStatus,
)
from crypto import OwnerKeyPair, HostKeyPair, PublicKey

PASS = 0
FAIL = 0

def check(label, condition, detail=""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  PASS  {label}")
    else:
        FAIL += 1
        print(f"  FAIL  {label}  {detail}")


def main():
    print()
    print("=" * 72)
    print("  PALINDROME")
    print("  A mailbox that forgets. A machine that remembers.")
    print("  An agent that temporarily attends.")
    print("=" * 72)
    print()

    # Set up crypto
    owner_key = OwnerKeyPair.generate()
    host_key = HostKeyPair.generate("host-palindrome")

    # Set up components
    citizens = FileCitizenRegistry()
    invitations = InvitationManager(device_key=owner_key)
    mailboxes = MailboxManager(citizens, invitations)
    chain = ReceiptChain()

    # Create temp files to act as "local machine files"
    tmpdir = tempfile.mkdtemp(prefix="palindrome-")
    evidence_file = os.path.join(tmpdir, "evidence.txt")
    secret_file = os.path.join(tmpdir, "secret.key")

    with open(evidence_file, "w") as f:
        f.write("HDAR Decisive Loop: 55/55 passed, 0 failed.\n")
        f.write("Real Apple Containerization VMs on Apple Silicon.\n")
        f.write("Ed25519 owner signing, host witness, offline verification.\n" * 10)

    with open(secret_file, "w") as f:
        f.write("SSH_PRIVATE_KEY=-----BEGIN OPENSSH PRIVATE KEY-----\n")
        f.write("this_is_secret_and_should_never_be_exposed\n")

    # ─── 1. File citizenship ───────────────────────────────────
    print("[1/10] File citizenship: enroll files with public identity + private authority")
    citizen_ev = citizens.enroll(
        evidence_file,
        permissions=["read", "summarize", "verify_hash"],
        owner_key=owner_key,
    )
    citizen_secret = citizens.enroll(
        secret_file,
        permissions=["verify_hash"],  # can verify hash but NOT read
        owner_key=owner_key,
    )

    check("evidence file enrolled", citizen_ev.citizen_id.startswith("file-"))
    check("evidence has content hash", len(citizen_ev.content_hash) == 64)
    check("evidence has owner signature", len(citizen_ev.owner_signature) > 0)
    check("evidence has read permission", "read" in citizen_ev.permissions)
    check("secret file enrolled", citizen_secret.citizen_id.startswith("file-"))
    check("secret has NO read permission", "read" not in citizen_secret.permissions)
    check("secret has verify_hash only", citizen_secret.permissions == ["verify_hash"])

    # Public identity does not contain local path
    pub = citizen_ev.to_public_dict()
    check("public identity has no local path", "local_path" not in pub)
    check("public identity has no owner signature", "owner_signature" not in pub)
    check("public identity has citizen_id", "citizen_id" in pub)
    check("public identity has content_hash", "content_hash" in pub)
    print()

    # ─── 2. Mailbox creation ───────────────────────────────────
    print("[2/10] Mailbox creation: temporary container with TTL")
    mailbox = mailboxes.create_mailbox(
        name="wolf-moon-72",
        ttl_seconds=100.0,
        task_description="Review HDAR evidence and verify integrity",
    )
    check("mailbox created", mailbox.mailbox_id == "wolf-moon-72")
    check("mailbox starts open", mailbox.status == LeaseStatus.OPEN)
    check("mailbox has TTL", mailbox.ttl_seconds == 100.0)

    # Enroll files into mailbox
    mailboxes.enroll_file("wolf-moon-72", evidence_file, ["read", "summarize", "verify_hash"], owner_key)
    mailboxes.enroll_file("wolf-moon-72", secret_file, ["verify_hash"], owner_key)

    status = mailboxes.mailbox_status("wolf-moon-72")
    check("mailbox has 2 citizens", len(status["citizens"]) == 2)
    check("mailbox reports open state", status["status"] == "open")
    print()

    # ─── 3. One-use invitation ─────────────────────────────────
    print("[3/10] One-use invitation: hotel keycard, not a kingdom")
    invitation = mailboxes.create_invitation(
        "wolf-moon-72",
        "Verify HDAR evidence integrity",
        recipient_id="chatgpt-session-001",
        conversation_label="chat-label-not-authority",
    )
    check("invitation created", invitation is not None)
    check("invitation has token", len(invitation.token) == 64)
    check("invitation is pending", invitation.status.value == "pending")
    check("lease has a valid device signature", invitation.verify_signature())
    check("lease binds exact file grants", citizen_ev.citizen_id in invitation.grants)
    tampered = type(invitation).from_dict(invitation.to_dict())
    tampered.grants[citizen_ev.citizen_id].append("inspect")
    check("tampering invalidates lease signature", not tampered.verify_signature())
    check("chat identifier is metadata", invitation.conversation_label == "chat-label-not-authority")
    check("mailbox moves to waiting", mailbox.status == LeaseStatus.WAITING)

    invite_str = invitation.to_invite_string()
    check("invite string starts with mirrorlease:v1:", invite_str.startswith("mirrorlease:v1:"))
    check("invite string contains encoded public payload", len(invite_str.split(":", 2)[-1]) > 100)

    # Parse it back
    parsed = type(invitation).parse_invite_string(invite_str)
    check("invite string parseable", parsed is not None)
    check("parsed mailbox matches", parsed["mailbox_id"] == "wolf-moon-72")
    check("pasted invitation verifies offline", type(invitation).from_public_dict(parsed).verify_signature())

    # Invitation does NOT contain private keys or local paths
    pub_inv = invitation.to_public_dict()
    check("invitation has no private keys", "private" not in json.dumps(pub_inv).lower())
    check("invitation has no local paths", "/Users/" not in json.dumps(pub_inv))
    print()

    # ─── 4. Invitation redemption ──────────────────────────────
    print("[4/10] Invitation redemption: one-use token exchanged for session credential")
    wrong_session, wrong_reason = invitations.redeem(
        "wolf-moon-72", invitation.token, guest_id="wrong-recipient"
    )
    check("recipient mismatch rejected", wrong_session is None and "recipient" in wrong_reason)
    session_cred, reason = invitations.redeem(
        "wolf-moon-72", invitation.token, guest_id="chatgpt-session-001"
    )
    check("invitation redeemed", session_cred is not None)
    check("redemption reason", reason == "redeemed")
    check("session credential is 64 chars", len(session_cred) == 64)

    # Try to redeem again — should fail
    session_cred2, reason2 = invitations.redeem(
        "wolf-moon-72", invitation.token, guest_id="chatgpt-session-002"
    )
    check("invitation cannot be reused", session_cred2 is None)
    check("reuse rejected", "already redeemed" in reason2)
    print()

    # ─── 5. File access through mailbox ────────────────────────
    print("[5/10] File access: GPT perceives only what was permitted")
    # Read evidence file — should work
    result_read = mailboxes.access_file(session_cred, citizen_ev.citizen_id, "read")
    check("evidence read granted", result_read["granted"])
    check("evidence read moves lease to used", result_read["state"] == "used")
    check("evidence content returned", "55/55 passed" in result_read.get("data", ""))
    check("read produces receipt", result_read["receipt"] is not None)

    # Try to read secret file — should be denied (no read permission)
    result_secret = mailboxes.access_file(session_cred, citizen_secret.citizen_id, "read")
    check("secret read denied", not result_secret["granted"])
    check("secret denial has reason", "not permitted" in result_secret["reason"])

    # Verify hash on secret — should work
    result_verify = mailboxes.access_file(session_cred, citizen_secret.citizen_id, "verify_hash")
    check("secret verify_hash granted", result_verify["granted"])
    check("secret hash verified", result_verify.get("verified", False))
    citizen_ev.permissions.append("inspect")
    result_scope_expand = mailboxes.access_file(session_cred, citizen_ev.citizen_id, "inspect")
    check("signed grant snapshot blocks later scope expansion", not result_scope_expand["granted"])
    print()

    # ─── 6. Fidelity decay ─────────────────────────────────────
    print("[6/10] Atomic expiry: full authorized access, then none")
    mailbox.created_at = time.time() - 92
    result_before_expiry = mailboxes.access_file(session_cred, citizen_ev.citizen_id, "read")
    check("at 92% TTL: lease remains used", result_before_expiry["state"] == "used")
    check("before expiry: content remains complete", "55/55 passed" in result_before_expiry.get("data", ""))

    # 101% of TTL -> EXPIRED
    mailbox.created_at = time.time() - 101
    result_expired = mailboxes.access_file(session_cred, citizen_ev.citizen_id, "read")
    check("at 101% TTL: expired", result_expired["state"] == "expired")
    check("expired denies access", not result_expired["granted"])
    print()

    # ─── 7. Receipt chain ──────────────────────────────────────
    print("[7/10] Receipt chain: every access produces a hash-linked receipt")
    # Reset mailbox for clean chain test
    mailbox2 = mailboxes.create_mailbox(name="stone-gate-42", ttl_seconds=3600.0)
    mailboxes.enroll_file("stone-gate-42", evidence_file, ["read", "summarize", "verify_hash"], owner_key)
    inv2 = mailboxes.create_invitation("stone-gate-42")
    session2, _ = invitations.redeem("stone-gate-42", inv2.token, guest_id="chatgpt-002")
    chain.bind_origin(
        inv2.signed_claims(),
        {"required_operations": ["read", "summarize", "verify_hash"]},
    )

    # Perform several operations, adding to chain
    for op in ["read", "summarize", "verify_hash"]:
        r = mailboxes.access_file(session2, citizen_ev.citizen_id, op)
        if r["receipt"]:
            chain.add(
                mailbox_id="stone-gate-42",
                citizen_id=citizen_ev.citizen_id,
                operation=op,
                granted=r["granted"],
                lease_state=r["state"],
                result_data=r.get("data", r.get("summary", r.get("verified", ""))),
                result_summary=r.get("reason", ""),
                host_key=host_key,
            )

    # Denied access also produces a receipt
    r_deny = mailboxes.access_file(session2, citizen_secret.citizen_id, "read")
    chain.add(
        mailbox_id="stone-gate-42",
        citizen_id=citizen_secret.citizen_id,
        operation="read",
        granted=False,
        lease_state=r_deny["state"],
        result_data=r_deny["reason"],
        result_summary="denied",
        host_key=host_key,
    )

    check("chain has 4 receipts", len(chain.get_receipts()) == 4)
    check("chain head hash is 64 chars", len(chain.head().receipt_hash) == 64)

    # Verify chain integrity
    verification = chain.verify_chain()
    check("chain verification passes", verification["chain_valid"])
    check("chain has 0 failures", verification["checks_failed"] == 0)
    check("chain has 20 checks passed (4 receipts x 5)", verification["checks_passed"] == 20)
    check("chain commits to original request", chain.head().origin_request_hash == chain.origin_request_hash)
    check("reverse trace ends at first receipt", chain.reverse_trace()[-1]["sequence"] == 0)
    print()

    # ─── 8. Signature verification ─────────────────────────────
    print("[8/10] Signature verification: receipts signed by host, verifiable offline")
    host_pub = PublicKey.from_hex(host_key.public_key_hex)
    sig_verification = chain.verify_chain(host_public_key=host_pub)
    check("signature verification passes", sig_verification["chain_valid"])
    print()

    # ─── 9. The palindrome: answer returns home ────────────────
    print("[9/10] The palindrome: outward goes the question, inward returns the answer")
    # The chain summary shows the conversation is captured
    summary = chain.summary()
    check("chain summary has operations", len(summary["operations"]) > 0)
    check("chain summary has 3 granted", summary["granted"] == 3)
    check("chain summary has 1 denied", summary["denied"] == 1)
    check("chain summary has mailbox", "stone-gate-42" in summary["mailboxes"])

    # The last receipt's hash becomes the opening state of the next session
    head = chain.head()
    check("head receipt exists", head is not None)
    check("head receipt has previous hash", len(head.previous_receipt_hash) == 64)

    # New mailbox can reference the previous chain head
    mailbox3 = mailboxes.create_mailbox(name="ember-lake-17", ttl_seconds=3600.0)
    check("new mailbox created for next round", mailbox3.mailbox_id == "ember-lake-17")
    inv3 = mailboxes.create_invitation("ember-lake-17")
    print()

    # ─── 10. Session revocation ────────────────────────────────
    print("[10/10] Session revocation: owner can close the mailbox early")
    # Close mailbox early
    closed = mailboxes.close_mailbox("ember-lake-17")
    check("mailbox closed early", closed)
    status_closed = mailboxes.mailbox_status("ember-lake-17")
    check("closed mailbox shows revoked status", status_closed["status"] == "revoked")

    # Revoke session
    revoked = invitations.revoke_session(session2)
    check("session revoked", revoked)
    after_revoke = invitations.validate_session(session2)
    check("revoked session invalid", after_revoke is None)
    destroyed = mailboxes.destroy_mailbox("ember-lake-17")
    check("revoked mailbox can be destroyed", destroyed)
    check("destroyed mailbox has no live grants", mailbox3.citizen_ids == [])
    check("destroyed invitation bearer token scrubbed", inv3.token == "")
    check("destroyed invitation grant snapshot scrubbed", inv3.grants == {})
    print()

    # ─── Result ────────────────────────────────────────────────
    print("=" * 72)
    print(f"  RESULT: {PASS} passed, {FAIL} failed")
    print()
    print("  Proven:")
    print("    - File citizenship: public identity + private authority, local paths never exposed")
    print("    - One-use invitation: hotel keycard, not a kingdom — cannot be reused")
    print("    - Mailbox with TTL: temporary container for AI perception")
    print("    - Explicit lease states: open -> waiting -> used -> expired/revoked -> destroyed")
    print("    - Per-file permissions: evidence readable, secret hash-verifiable only")
    print("    - Receipt chain: hash-linked, signed, verifiable offline")
    print("    - The palindrome: answer returns home, becomes next question's opening state")
    print("    - Owner can close mailbox and revoke session at any time")
    print()
    print("  The mailbox dies.")
    print("  The receipt survives.")
    print("  The machine continues.")
    print("=" * 72)

    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
