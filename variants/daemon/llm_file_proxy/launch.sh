#!/bin/bash
# launch.sh — Start LLM File Proxy + Cloudflare Quick Tunnel, copy URL to clipboard
# Usage: launch.sh /path/to/file
# Outputs the public URL and copies it to clipboard

set -euo pipefail

FILE_PATH="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${2:-8765}"

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
    echo "ERROR: Provide a valid file path" >&2
    echo "Usage: $0 /path/to/file [port]" >&2
    exit 1
fi

# Start the proxy server in background
echo "Starting LLM File Proxy for: $(basename "$FILE_PATH")" >&2
python3 "$SCRIPT_DIR/llm_proxy.py" "$FILE_PATH" --port "$PORT" &
PROXY_PID=$!

# Wait for server to be ready
for i in $(seq 1 10); do
    if curl -s "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
        break
    fi
    sleep 0.5
done

if ! curl -s "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
    echo "ERROR: Proxy server failed to start" >&2
    kill $PROXY_PID 2>/dev/null || true
    exit 1
fi

echo "Proxy server running on http://127.0.0.1:$PORT" >&2

# Start Cloudflare Quick Tunnel (no account needed, free, instant)
echo "Starting Cloudflare Quick Tunnel..." >&2
cloudflared tunnel --url "http://127.0.0.1:$PORT" 2>&1 | while IFS= read -r line; do
    # Cloudflare prints the tunnel URL in a line like:
    # "Your quick Tunnel has been created! Visit it at: https://xxx.trycloudflare.com"
    if echo "$line" | grep -q "trycloudflare.com"; then
        TUNNEL_URL=$(echo "$line" | grep -oE 'https://[a-zA-Z0-9-]+\.trycloudflare\.com')
        if [ -n "$TUNNEL_URL" ]; then
            echo "$TUNNEL_URL" | pbcopy
            echo ""
            echo "========================================" >&2
            echo "  LLM URL copied to clipboard!" >&2
            echo "  URL: $TUNNEL_URL" >&2
            echo "========================================" >&2
            echo ""
            echo "$TUNNEL_URL"
            # Show macOS notification
            osascript -e "display notification \"URL copied to clipboard: $TUNNEL_URL\" with title \"LLM File Proxy\" sound name \"Glass\"" 2>/dev/null || true
        fi
    fi
    # Keep tunnel running
done

# Cleanup if tunnel exits
kill $PROXY_PID 2>/dev/null || true
