# MirrorLease transport contract

Every adapter is a parser and delivery mechanism only. Authorization lives in
`mirrorlease_protocol.engine.MirrorLeaseEngine`.

| Door | Wire form | Authentication | Owner control |
|---|---|---|---|
| Finder right-click | selected file URLs into the native helper | physical owner action + Keychain device key | first use asks before creating the key |
| Local CLI | `python -m mirrorlease_protocol.local_cli` commands | local owner key + private lease record | normal requests ask through macOS approval dialog |
| Guarded HTTPS | JSON over TLS 1.2+ | signed invitation for knock; disposable lease token for requests | every disclosure asks locally |
| GPT Action | `mirrorlease_openapi.yaml` over the guarded endpoint | bearer lease token | same local prompt |
| MCP | Streamable HTTP JSON-RPC at `/mcp` | bearer lease token | same local prompt |
| Disposable email | private RFC 822 inbox/outbox spool | signed invitation or disposable token in JSON payload | same local prompt |

The common request envelope is `mirrorlease/v1` and contains a request id,
transport label, agent label, conversation label, nonce, operation, and public
file id. Conversation labels are audit metadata, never authority.

Every outcome appends a signed, hash-linked receipt to:

`~/Library/Application Support/MirrorLease/audit.jsonl`

Private lease records and original local paths remain in:

`~/Library/Application Support/MirrorLease/leases/`

Local smoke commands:

```sh
python -m mirrorlease_protocol.local_cli create ./sample.txt --clipboard
python -m mirrorlease_protocol.local_cli serve --host 127.0.0.1 --port 9443
```

The CLI path stores software keys under
`~/Library/Application Support/MirrorLease/keys/` with private file
permissions. The native Finder helper uses the macOS Keychain path described in
its Swift implementation.

The original file itself remains where the owner saved it. The website, GPT
Action, MCP server, and email spool do not become a second file cabinet.

The production gateway refuses to start without an explicit TLS certificate
and key. MirrorLease does not generate or install those credentials silently.
