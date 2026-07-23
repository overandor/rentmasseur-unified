#!/usr/bin/env python3
"""Extract all conversation history from Windsurf/Devin acp-events NDJSON files."""

import json
import os
import glob
import sqlite3
from datetime import datetime
from collections import defaultdict

DATA_SOURCES = [
    {
        "name": "Devin",
        "events_dir": os.path.expanduser("~/Library/Application Support/Devin/User/acp-events"),
        "state_db": os.path.expanduser("~/Library/Application Support/Devin/User/globalStorage/state.vscdb"),
    },
    {
        "name": "Windsurf",
        "events_dir": os.path.expanduser("~/Library/Application Support/Windsurf/User/acp-events"),
        "state_db": os.path.expanduser("~/Library/Application Support/Windsurf/User/globalStorage/state.vscdb"),
    },
]
ARCHIVE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))

def load_session_metadata(state_db, source_name=""):
    """Load session metadata from state.vscdb."""
    meta = {}
    try:
        conn = sqlite3.connect(state_db)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM ItemTable WHERE key = 'windsurf.acp.metadataCache'")
        row = cur.fetchone()
        if row:
            raw = row[1]
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            data = json.loads(raw)
            for session in data.get("sessions", []):
                sid = session.get("sessionId", "")
                title = session.get("title", "Untitled")
                created = session.get("_meta", {}).get("cognition.ai/createdAt", "")
                updated = session.get("updatedAt", "")
                repos = [r.get("name", "") for r in session.get("_meta", {}).get("cognition.ai/sessionRepos", [])]
                prs = session.get("_meta", {}).get("cognition.ai/sessionPRs", [])
                meta[sid] = {
                    "title": title,
                    "created": created,
                    "updated": updated,
                    "repos": repos,
                    "prs": prs,
                    "source": source_name,
                }
        conn.close()
    except Exception as e:
        print(f"Error loading metadata ({source_name}): {e}")
    return meta

def load_event_log_index(state_db, source_name=""):
    """Load event log index for UUID -> session mapping."""
    index = {}
    try:
        conn = sqlite3.connect(state_db)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM ItemTable WHERE key = 'windsurf.acp.eventLog.index'")
        row = cur.fetchone()
        if row:
            raw = row[1]
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            data = json.loads(raw)
            for sid, info in data.items():
                uuid = info.get("uuid", "")
                index[uuid] = {
                    "sessionId": sid,
                    "eventCount": info.get("eventCount", 0),
                    "lastUpdated": info.get("lastUpdated", 0),
                    "source": source_name,
                }
        conn.close()
    except Exception as e:
        print(f"Error loading event index ({source_name}): {e}")
    return index

def parse_ndjson(filepath):
    """Parse an NDJSON file and extract events."""
    events = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    events.append(obj)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        print(f"Error reading {filepath}: {e}")
    return events

def extract_event_info(obj):
    """Extract type, timestamp, and content from an event object."""
    notif = obj.get("notification", {})
    meta = notif.get("_meta", {})
    event_type = meta.get("cognition.ai/eventType", "")
    timestamp = meta.get("cognition.ai/timestamp", "")
    session_update = notif.get("sessionUpdate", "")
    
    info = {
        "event_type": event_type,
        "timestamp": timestamp,
        "session_update": session_update,
        "text": "",
        "command": "",
        "exit_code": "",
        "title": notif.get("title", ""),
        "raw_output": notif.get("rawOutput", ""),
        "sender": meta.get("cognition.ai/sender", {}).get("name", ""),
    }
    
    # Extract text content
    content = notif.get("content", {})
    if isinstance(content, dict):
        info["text"] = content.get("text", "")
    elif isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                c = item.get("content", {})
                if isinstance(c, dict):
                    parts.append(c.get("text", ""))
        info["text"] = " ".join(parts).strip()
    
    # Extract command
    info["command"] = meta.get("cognition.ai/command", "")
    info["exit_code"] = meta.get("cognition.ai/exitCode", "")
    
    return info

def categorize_event(info):
    """Categorize an event as user_prompt, ai_response, or terminal_command."""
    et = info["event_type"]
    su = info["session_update"]
    
    # User messages
    if et == "initial_user_message" or (et == "user_message" and info["text"]):
        return "user_prompt"
    
    # AI responses
    if et in ("devin_message", "agent_message_chunk") and info["text"]:
        return "ai_response"
    
    # AI thoughts (also capture as ai_response)
    if et in ("devin_thoughts", "one_line_thoughts", "agent_thought_chunk") and info["text"]:
        return "ai_thought"
    
    # Terminal commands
    if et == "shell_process_started" and info["command"]:
        return "terminal_command"
    
    # Terminal output
    if et == "shell_process_completed":
        return "terminal_output"
    
    # PR created
    if et == "pr_created" and info["text"]:
        return "ai_response"
    
    # Git push
    if et == "git_push" and info["title"]:
        return "terminal_command"
    
    return None

def load_terminal_history(state_db, source_name=""):
    """Load local terminal history from state.vscdb."""
    local_term_lines = []
    try:
        conn = sqlite3.connect(state_db)
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM ItemTable WHERE key = 'terminal.history.entries.commands'")
        row = cur.fetchone()
        if row:
            raw = row[1]
            if isinstance(raw, bytes):
                raw = raw.decode('utf-8')
            data = json.loads(raw)
            for entry in data.get("entries", []):
                cmd = entry.get("key", "")
                shell_type = entry.get("value", {}).get("shellType", "unknown")
                if cmd:
                    local_term_lines.append({"command": cmd, "shellType": shell_type, "source": source_name})
        conn.close()
    except Exception as e:
        print(f"Error loading terminal history ({source_name}): {e}")
    return local_term_lines

def main():
    all_session_meta = {}
    all_event_index = {}
    all_events = []
    all_local_terms = []
    total_ndjson = 0

    for source in DATA_SOURCES:
        sname = source["name"]
        sdb = source["state_db"]
        edir = source["events_dir"]

        print(f"\n{'='*60}")
        print(f"Processing source: {sname}")
        print(f"{'='*60}")

        print("Loading session metadata...")
        session_meta = load_session_metadata(sdb, sname)
        print(f"  Found {len(session_meta)} sessions in metadata cache")
        all_session_meta.update(session_meta)

        print("Loading event log index...")
        event_index = load_event_log_index(sdb, sname)
        print(f"  Found {len(event_index)} UUID mappings")
        all_event_index.update(event_index)

        print(f"\nScanning NDJSON files in {edir}...")
        ndjson_files = sorted(glob.glob(os.path.join(edir, "*.ndjson")))
        print(f"  Found {len(ndjson_files)} event files")
        total_ndjson += len(ndjson_files)

        for filepath in ndjson_files:
            uuid = os.path.basename(filepath).replace(".ndjson", "")
            session_info = event_index.get(uuid, {})
            session_id = session_info.get("sessionId", f"unknown/{uuid}")
            meta = session_meta.get(session_id, {})
            title = meta.get("title", "Untitled")
            fsize = os.path.getsize(filepath)
            print(f"  Parsing {os.path.basename(filepath)} ({fsize//1024}KB)...")

            events = parse_ndjson(filepath)

            for event in events:
                info = extract_event_info(event)
                category = categorize_event(info)
                if category:
                    info["category"] = category
                    info["session_id"] = session_id
                    info["session_title"] = title
                    info["uuid"] = uuid
                    info["source_file"] = os.path.basename(filepath)
                    info["source_app"] = sname
                    all_events.append(info)

        print("Loading terminal history...")
        local_terms = load_terminal_history(sdb, sname)
        print(f"  Found {len(local_terms)} local terminal commands")
        all_local_terms.extend(local_terms)
    
    # Sort by timestamp
    all_events.sort(key=lambda x: x["timestamp"] or "")
    
    print(f"\nTotal categorized events: {len(all_events)}")
    
    # Count by category
    counts = defaultdict(int)
    for e in all_events:
        counts[e["category"]] += 1
    for cat, count in sorted(counts.items()):
        print(f"  {cat}: {count}")
    
    # Build three archive files
    idx_counter = 0
    
    terminal_lines = []
    ai_response_lines = []
    user_prompt_lines = []
    
    terminal_lines.append("# Terminal Commands Log — Full Historical Archive")
    terminal_lines.append("# Extracted from Devin + Windsurf acp-events NDJSON files")
    terminal_lines.append(f"# Generated: {datetime.now().isoformat()}")
    terminal_lines.append(f"# Total terminal events: {counts.get('terminal_command', 0) + counts.get('terminal_output', 0) + counts.get('terminal_command', 0)}")
    terminal_lines.append("")
    
    ai_response_lines.append("# AI Response Log — Full Historical Archive")
    ai_response_lines.append("# Extracted from Devin + Windsurf acp-events NDJSON files")
    ai_response_lines.append(f"# Generated: {datetime.now().isoformat()}")
    ai_response_lines.append(f"# Total AI response events: {counts.get('ai_response', 0) + counts.get('ai_thought', 0)}")
    ai_response_lines.append("")
    
    user_prompt_lines.append("# User Prompt Log — Full Historical Archive")
    user_prompt_lines.append("# Extracted from Devin + Windsurf acp-events NDJSON files")
    user_prompt_lines.append(f"# Generated: {datetime.now().isoformat()}")
    user_prompt_lines.append(f"# Total user prompt events: {counts.get('user_prompt', 0)}")
    user_prompt_lines.append("")
    
    term_idx = 0
    ai_idx = 0
    user_idx = 0
    
    for event in all_events:
        ts = event["timestamp"]
        cat = event["category"]
        sid = event["session_id"]
        title = event["session_title"]
        text = event["text"]
        cmd = event["command"]
        exit_code = event["exit_code"]
        raw_output = event["raw_output"]
        sender = event["sender"]
        
        source_app = event.get("source_app", "?")

        if cat == "terminal_command":
            term_idx += 1
            terminal_lines.append(f"--- ENTRY {term_idx} ---")
            terminal_lines.append(f"Timestamp: {ts}")
            terminal_lines.append(f"Source: {source_app}")
            terminal_lines.append(f"Session: {title} ({sid})")
            if cmd:
                terminal_lines.append(f"Command: {cmd}")
            if event["title"]:
                terminal_lines.append(f"Title: {event['title']}")
            terminal_lines.append("")
        
        elif cat == "terminal_output":
            term_idx += 1
            terminal_lines.append(f"--- ENTRY {term_idx} ---")
            terminal_lines.append(f"Timestamp: {ts}")
            terminal_lines.append(f"Source: {source_app}")
            terminal_lines.append(f"Session: {title} ({sid})")
            if exit_code:
                terminal_lines.append(f"Exit Code: {exit_code}")
            if raw_output:
                # Truncate very long outputs
                if len(raw_output) > 2000:
                    terminal_lines.append(f"Output (truncated):\n{raw_output[:2000]}\n... [truncated {len(raw_output)-2000} chars]")
                else:
                    terminal_lines.append(f"Output:\n{raw_output}")
            terminal_lines.append("")
        
        elif cat in ("ai_response", "ai_thought"):
            ai_idx += 1
            ai_response_lines.append(f"--- ENTRY {ai_idx} ---")
            ai_response_lines.append(f"Timestamp: {ts}")
            ai_response_lines.append(f"Source: {source_app}")
            ai_response_lines.append(f"Session: {title} ({sid})")
            label = "Thought" if cat == "ai_thought" else "Response"
            ai_response_lines.append(f"Type: {label}")
            if sender:
                ai_response_lines.append(f"Sender: {sender}")
            if text:
                # Truncate very long texts
                if len(text) > 3000:
                    ai_response_lines.append(f"Content (truncated):\n{text[:3000]}\n... [truncated {len(text)-3000} chars]")
                else:
                    ai_response_lines.append(f"Content:\n{text}")
            ai_response_lines.append("")
        
        elif cat == "user_prompt":
            user_idx += 1
            user_prompt_lines.append(f"--- ENTRY {user_idx} ---")
            user_prompt_lines.append(f"Timestamp: {ts}")
            user_prompt_lines.append(f"Source: {source_app}")
            user_prompt_lines.append(f"Session: {title} ({sid})")
            if sender:
                user_prompt_lines.append(f"Sender: {sender}")
            if text:
                user_prompt_lines.append(f"Prompt: {text}")
            user_prompt_lines.append("")
    
    # Append local terminal commands to terminal log, grouped by source
    if all_local_terms:
        terminal_lines.append("")
        terminal_lines.append("--- LOCAL TERMINAL HISTORY (from IDE) ---")
        terminal_lines.append(f"--- {len(all_local_terms)} commands total ---")
        terminal_lines.append("")
        by_source = defaultdict(list)
        for entry in all_local_terms:
            by_source[entry["source"]].append(entry)
        for sname, entries in by_source.items():
            terminal_lines.append(f"=== {sname} ({len(entries)} commands) ===")
            terminal_lines.append("")
            for i, entry in enumerate(entries, 1):
                terminal_lines.append(f"[{i}] ({entry['shellType']}) {entry['command']}")
            terminal_lines.append("")
    
    # Write files
    term_path = os.path.join(ARCHIVE_DIR, "01_terminal_log.md")
    ai_path = os.path.join(ARCHIVE_DIR, "02_ai_response_log.md")
    user_path = os.path.join(ARCHIVE_DIR, "03_user_prompt_log.md")
    
    with open(term_path, 'w') as f:
        f.write("\n".join(terminal_lines))
    print(f"\nWrote {term_path} ({term_idx} entries)")
    
    with open(ai_path, 'w') as f:
        f.write("\n".join(ai_response_lines))
    print(f"Wrote {ai_path} ({ai_idx} entries)")
    
    with open(user_path, 'w') as f:
        f.write("\n".join(user_prompt_lines))
    print(f"Wrote {user_path} ({user_idx} entries)")
    
    # Also write a combined index file
    index_path = os.path.join(ARCHIVE_DIR, "00_session_index.md")
    index_lines = [
        "# Session Index — Full Historical Archive",
        f"# Generated: {datetime.now().isoformat()}",
        f"# Total sessions: {len(session_meta)}",
        "",
    ]
    
    sorted_sessions = sorted(session_meta.items(), key=lambda x: x[1].get("created", ""))
    for sid, meta in sorted_sessions:
        index_lines.append(f"## {meta['title']}")
        index_lines.append(f"- Session ID: `{sid}`")
        index_lines.append(f"- Created: {meta['created']}")
        index_lines.append(f"- Updated: {meta['updated']}")
        if meta["repos"]:
            index_lines.append(f"- Repos: {', '.join(meta['repos'])}")
        if meta["prs"]:
            for pr in meta["prs"]:
                index_lines.append(f"  - PR: [{pr.get('title', '')}]({pr.get('url', '')}) — {pr.get('state', '')}")
        index_lines.append("")
    
    with open(index_path, 'w') as f:
        f.write("\n".join(index_lines))
    print(f"Wrote {index_path} ({len(sorted_sessions)} sessions)")
    
    print("\nDone!")

if __name__ == "__main__":
    main()
