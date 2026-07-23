# MirrorLease: The Laptop That Speaks for Itself

MirrorLease is a local-authority protocol for lending an AI agent one narrow,
temporary capability. The laptop remains the root of trust. A file fingerprint
identifies content; it is never a password. A public key verifies identity and
signatures; merely knowing it never grants access.

## Canonical rules

1. **One ticket, one ride.** A lease names the mailbox, intended recipient,
   exact file identities, allowed operations, random challenge, and expiration.
2. **The device signs the lease.** Its private signing key stays local. The
   invitation carries a disposable bearer token plus public verification data.
3. **Chat identity is only a label.** A conversation identifier may appear in
   receipts but is not ownership, authentication, or the root of trust.
4. **Paths stay private.** The agent sees virtual file identities and content
   hashes, never raw local paths or neighboring directory structure.
5. **No authority decay.** A lease has discrete states: `open`, `waiting`,
   `used`, `expired`, `revoked`, and `destroyed`. Authorized access remains
   exact until expiration or revocation, then stops atomically. Reduced modes,
   when needed, must be selected explicitly by the owner rather than triggered
   silently by time.
6. **Every operation is checked.** The gateway enforces the immutable grant
   snapshot embedded in the signed lease, not a mutable global permission.
7. **A response is not proof of understanding.** A receipt proves an exchange
   and can commit to a deterministic result. It does not prove consciousness,
   attention, wisdom, or comprehension.
8. **The palindrome is a trace.** Every receipt links backward, commits to the
   first request and completion rules, and supports a verified reverse view.
   Reversed text may be decorative but is not security.
9. **The chain is a witness, not storage.** Optional public timestamping may
   anchor fingerprints. Private files and private keys remain off-chain.
10. **Mailbox transport is replaceable.** Email, HTTPS, an approved GPT Action,
    or MCP may deliver the same signed protocol messages. Transport does not
    widen authority.

## Lifecycle

`open -> waiting -> used -> expired -> destroyed`

The owner may branch from any live state to `revoked`, then `destroyed`.
Expiration is a time boundary, not progressive corruption or partial access.
Destruction invalidates live invitations, sessions, and grants while retaining
non-secret receipt evidence.

## Current prototype boundary

The prototype implements local file identities, device-signed one-use
leases, recipient and operation binding, explicit lifecycle states, atomic TTL
expiry, session revocation, grant destruction, hash-linked signed receipts, and
forward/reverse request commitments. The installed native Finder Quick Action
hashes selected files locally, creates a 72-hour lease, stores private path
mappings under the user's Application Support directory, and copies only the
public invitation to the clipboard. First use requires explicit approval before
the Ed25519 device key is created in macOS Keychain.

It does **not** yet implement a hardened local daemon, encrypted transient
copies, remote MCP/Action transport, durable encrypted lease storage, secure
deletion guarantees, or public blockchain timestamping. See
`MIRRORLEASE_CLAIM_STATUS.json` for the machine-readable claim boundary.
