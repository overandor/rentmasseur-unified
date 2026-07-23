---
title: Jorki
emoji: ⚡
colorFrom: blue
colorTo: purple
sdk: docker
app_port: 7860
pinned: false
---

# Jorki — The Operating System for AI File Access

**Files don't move. Context does.**

Jorki turns any local file into a live AI-readable session URL. Instead of uploading gigabytes into every chat, create one secure session and let AI tools query exactly what they need.

## How it works

1. Select a file (Finder right-click → Jorki → Copy AI URL)
2. Local C++ engine indexes any file (1GB+) in <3 seconds
3. Compact SQLite index (KB) is uploaded to this Space
4. AI queries the index via SQL, search, chunk retrieval, or MCP
5. The original file never leaves your machine
6. Revoke access at any time

## API

- `POST /upload` — Upload .idx index (auth required)
- `GET /meta/{id}` — File metadata
- `GET /summary/{id}` — Structure + samples
- `GET /chunk/{id}/{idx}` — Chunk content
- `GET /chunks/{id}` — List all chunks
- `GET /search/{id}?q=` — Full-text search
- `POST /query/sql/{id}` — SQL query
- `POST /query/nosql/{id}` — NoSQL query
- `GET /stats/{id}` — Query statistics
- `DELETE /revoke/{id}` — Revoke session (auth required)
- `GET /mcp` — MCP manifest
- `POST /mcp/query` — MCP unified query
- `GET /health` — Health check

## Persistent Storage

To survive Space restarts, enable persistent storage in HF Space settings:
1. Go to Space Settings → Persistent Storage
2. Attach a small (20GB) persistent volume
3. It mounts at `/data` — Jorki auto-detects and uses it

Without persistent storage, sessions are lost on restart. The `/health` endpoint shows storage status.
