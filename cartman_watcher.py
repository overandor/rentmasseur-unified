#!/usr/bin/env python3
"""
Cartman Watcher — macOS daemon that watches Windsurf chats, sends AI responses
to God Cartman for direction, and speaks the directive using macOS `say`.

Runs as a launchd service. Watches for new AI responses in Windsurf's SQLite
state databases, sends them to http://127.0.0.1:5151/direct, and speaks the
result using the macOS `say` command with a Cartman-like voice.

Also writes directives to a file that Cascade can read for text-based directions.
"""

import os
import sys
import time
import json
import sqlite3
import subprocess
import hashlib
import re
import signal
from pathlib import Path
from datetime import datetime

import urllib.request

# ─── Config ─────────────────────────────────────────────────────────

CARTMAN_API = "http://127.0.0.1:5151"
WINDSURF_BASE = os.path.expanduser("~/Library/Application Support/Windsurf")
WORKSPACE_STORAGE = os.path.join(WINDSURF_BASE, "User", "workspaceStorage")
GLOBAL_DB = os.path.join(WINDSURF_BASE, "User", "globalStorage", "state.vscdb")

DIRECTIVE_FILE = os.path.expanduser(
    "~/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/cartman_directive.txt"
)
LOG_FILE = os.path.expanduser(
    "~/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/cartman_watcher.log"
)
SEEN_FILE = os.path.expanduser(
    "~/Downloads/MEMBRA::SURFACE=BUILD@LIVE/02_AI_Agents/rentmasseur-extension/.cartman_seen_hashes.json"
)

POLL_INTERVAL = 3  # seconds
SPEAK_ENABLED = True
WRITE_DIRECTIVE = True

# ─── Logging ────────────────────────────────────────────────────────

def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ─── Seen tracking ──────────────────────────────────────────────────

def load_seen():
    try:
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    except Exception:
        return set()

def save_seen(seen):
    try:
        with open(SEEN_FILE, "w") as f:
            json.dump(list(seen)[-500:], f)  # Keep last 500
    except Exception:
        pass

# ─── Windsurf DB scanning ───────────────────────────────────────────

def get_workspace_dbs():
    """Find all workspace state.vscdb files."""
    dbs = []
    if os.path.isdir(WORKSPACE_STORAGE):
        for entry in os.listdir(WORKSPACE_STORAGE):
            ws_dir = os.path.join(WORKSPACE_STORAGE, entry)
            db_path = os.path.join(ws_dir, "state.vscdb")
            if os.path.exists(db_path):
                ws_json = os.path.join(ws_dir, "workspace.json")
                folder = ""
                try:
                    with open(ws_json) as f:
                        data = json.load(f)
                        folder = data.get("folder", "")
                except Exception:
                    pass
                dbs.append({"path": db_path, "folder": folder})
    if os.path.exists(GLOBAL_DB):
        dbs.append({"path": GLOBAL_DB, "folder": "global"})
    return dbs

def extract_chat_text(db_path):
    """Extract chat/cascade text from a Windsurf state.vscdb."""
    texts = []
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM ItemTable")
        for key, value in cursor.fetchall():
            if not isinstance(value, (str, bytes)):
                continue
            key_lower = key.lower() if isinstance(key, str) else ""
            if not any(w in key_lower for w in ["chat", "cascade", "conversation", "message", "aichat"]):
                continue
            try:
                if isinstance(value, bytes):
                    value = value.decode("utf-8", errors="replace")
                # Try to parse as JSON and extract text content
                data = json.loads(value)
                extracted = extract_text_from_json(data)
                if extracted:
                    texts.append({"key": key, "text": extracted})
            except (json.JSONDecodeError, TypeError):
                # Not JSON, treat as raw text if long enough
                if isinstance(value, str) and len(value) > 50:
                    texts.append({"key": key, "text": value})
        conn.close()
    except Exception as e:
        log(f"DB read error {db_path}: {e}")
    return texts

def extract_text_from_json(data, depth=0):
    """Recursively extract text content from JSON structures."""
    if depth > 10:
        return ""
    parts = []
    if isinstance(data, dict):
        for k, v in data.items():
            if k in ("text", "content", "message", "response", "body", "prompt", "answer"):
                if isinstance(v, str) and len(v) > 20:
                    parts.append(v)
            else:
                parts.append(extract_text_from_json(v, depth + 1))
    elif isinstance(data, list):
        for item in data:
            parts.append(extract_text_from_json(item, depth + 1))
    elif isinstance(data, str) and len(data) > 50:
        parts.append(data)
    return "\n".join(p for p in parts if p)

# ─── Cartman API ────────────────────────────────────────────────────

def send_to_cartman(response_text, context=""):
    """Send AI response to God Cartman /direct endpoint."""
    try:
        payload = json.dumps({"response": response_text, "context": context}).encode("utf-8")
        req = urllib.request.Request(
            f"{CARTMAN_API}/direct",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        log(f"Cartman API error: {e}")
        return None

# ─── macOS say ──────────────────────────────────────────────────────

def speak(text, voice="Alex", rate=180, pitch=None):
    """Speak text using macOS `say` command."""
    if not SPEAK_ENABLED:
        return
    # Clean text for speech
    clean = re.sub(r"[#*`@\[\](){}]", " ", text)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return

    cmd = ["say", "-v", voice, "-r", str(rate)]
    if pitch:
        cmd.extend(["-p", str(pitch)])
    cmd.append(clean[:500])  # Limit length

    try:
        subprocess.run(cmd, timeout=30, capture_output=True)
    except Exception as e:
        log(f"say error: {e}")

def write_directive(directive_data):
    """Write directive to file for Cascade to read."""
    if not WRITE_DIRECTIVE:
        return
    try:
        with open(DIRECTIVE_FILE, "w") as f:
            f.write(f"CARTMAN DIRECTIVE — {datetime.now().isoformat()}\n")
            f.write(f"Action: {directive_data.get('action', 'continue')}\n")
            f.write(f"Directive: {directive_data.get('directive', '')}\n")
            f.write(f"Cartman says: {directive_data.get('cartman_quote', '')}\n")
            incomplete = directive_data.get("incomplete_items", [])
            if incomplete:
                f.write("Incomplete items:\n")
                for item in incomplete:
                    f.write(f"  - {item}\n")
            f.write(f"Watching: {directive_data.get('watching', True)}\n")
    except Exception as e:
        log(f"Write directive error: {e}")

# ─── Main loop ──────────────────────────────────────────────────────

running = True

def signal_handler(sig, frame):
    global running
    running = False
    log("Shutting down...")

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)

def main():
    log("Cartman Watcher starting up...")
    log(f"Watching Windsurf DBs in: {WORKSPACE_STORAGE}")
    log(f"Cartman API: {CARTMAN_API}")
    log(f"Directive file: {DIRECTIVE_FILE}")

    seen = load_seen()
    log(f"Loaded {len(seen)} seen hashes")

    # Check if Cartman engine is running
    try:
        urllib.request.urlopen(f"{CARTMAN_API}/health", timeout=3)
        log("God Cartman engine is online.")
    except Exception:
        log("WARNING: God Cartman engine not responding. Will retry...")

    last_dbs = []
    cycle = 0

    while running:
        cycle += 1
        try:
            dbs = get_workspace_dbs()

            # Detect new/changed DBs
            if len(dbs) != len(last_dbs) or cycle == 1:
                log(f"Found {len(dbs)} workspace DBs")
                for db in dbs:
                    log(f"  - {db['folder']} -> {db['path']}")
                last_dbs = dbs

            for db in dbs:
                texts = extract_chat_text(db["path"])
                for entry in texts:
                    text = entry["text"]
                    if len(text) < 30:
                        continue

                    # Hash the text to detect new content
                    h = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
                    if h in seen:
                        continue

                    # New text detected!
                    seen.add(h)
                    save_seen(seen)

                    log(f"New chat content from {db['folder']} (key: {entry['key'][:50]}, hash: {h})")
                    log(f"  Text preview: {text[:200].replace(chr(10), ' ')}...")

                    # Send to God Cartman for direction
                    result = send_to_cartman(text, context=db["folder"])
                    if result:
                        directive = result.get("directive", "")
                        action = result.get("action", "continue")
                        quote = result.get("cartman_quote", "")
                        incomplete = result.get("incomplete_items", [])

                        log(f"  CARTMAN SAYS: {quote}")
                        log(f"  ACTION: {action}")
                        log(f"  DIRECTIVE: {directive}")

                        # Write directive file for Cascade
                        write_directive(result)

                        # Speak the directive using macOS say
                        speak(quote, voice="Alex", rate=190)
                        speak(directive, voice="Alex", rate=175)

                        # If there are incomplete items, speak them too
                        if incomplete:
                            speak(f"You still need to do: {' '.join(incomplete[:3])}", voice="Alex", rate=175)
                    else:
                        # Cartman engine down — use fallback
                        fallback = "Don't stop! Keep going! Respect my authoritah!"
                        write_directive({
                            "action": "continue",
                            "directive": fallback,
                            "cartman_quote": fallback,
                            "incomplete_items": [],
                            "watching": True,
                        })
                        speak(fallback, voice="Alex", rate=190)

        except Exception as e:
            log(f"Error in main loop: {e}")

        time.sleep(POLL_INTERVAL)

    log("Cartman Watcher stopped.")

if __name__ == "__main__":
    main()
