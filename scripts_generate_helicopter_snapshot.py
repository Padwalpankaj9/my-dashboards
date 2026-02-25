#!/usr/bin/env python3
"""Generate a visibility-only snapshot of this Mac for helicopter dashboard."""

import json
import os
import platform
import shlex
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
OUT_FILE = DATA_DIR / "snapshot.json"
HISTORY_FILE = DATA_DIR / "history.json"

# These are the main zones to keep visible at a glance.
KEY_PATHS = [
    ("Claude App Support", "/Users/apple/Library/Application Support/Claude"),
    ("Playwright Cache", "/Users/apple/Library/Caches/ms-playwright"),
    ("Claude Home", "/Users/apple/.claude"),
    ("npm Global", "/Users/apple/.npm-global"),
    ("Gmail Homes", "/Users/apple/.gmail-homes"),
    ("Gemini Home", "/Users/apple/.gemini"),
    ("Local Share", "/Users/apple/.local"),
    ("Codex Home", "/Users/apple/.codex"),
    ("Documents", "/Users/apple/Documents"),
    ("Software Development", "/Users/apple/Documents/Software_Development"),
    ("gmail-mcp", "/Users/apple/Documents/gmail-mcp"),
    ("Documents .appium", "/Users/apple/Documents/.appium"),
    ("Documents .playwright-mcp", "/Users/apple/Documents/.playwright-mcp"),
    ("nanobanana-output", "/Users/apple/Documents/nanobanana-output"),
]

CLI_COMMANDS = [
    "codex",
    "claude",
    "gemini",
    "imsg",
    "uv",
    "node",
    "npm",
    "npx",
    "python3",
    "pip3",
    "d2",
    "mmdc",
    "appium",
    "vercel",
    "shopify",
]

# These sections explain where fragmentation exists.
FRAGMENTATION_HINTS = [
    "Claude roots: ~/.claude + ~/Documents/.claude + project-level .claude folders",
    "Playwright roots: ~/.playwright-mcp + ~/Documents/.playwright-mcp + project-level copies",
    "MCP roots: ~/.claude/mcp-servers + ~/mcp-servers + ~/Documents/gmail-mcp",
    "Workspace roots: ~/Documents/Software_Development plus standalone repos in ~",
]


def run(cmd: str) -> str:
    """Run shell command and return trimmed stdout."""
    try:
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except Exception:
        return ""


def bytes_to_human(n: int) -> str:
    """Convert bytes to readable size string."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return f"{n} B"


def du_bytes(path: str) -> int:
    """Use du for fast directory size calculation."""
    if not os.path.exists(path):
        return 0
    out = run(f"du -sk {shlex.quote(path)}")
    if not out:
        return 0
    try:
        kb = int(out.split()[0])
        return kb * 1024
    except Exception:
        return 0


def get_df_root() -> dict:
    """Capture root volume usage."""
    out = run("df -k /")
    lines = out.splitlines()
    if len(lines) < 2:
        return {}
    cols = lines[1].split()
    if len(cols) < 6:
        return {}
    size_k = int(cols[1])
    used_k = int(cols[2])
    avail_k = int(cols[3])
    cap = cols[4]
    return {
        "filesystem": cols[0],
        "size_bytes": size_k * 1024,
        "used_bytes": used_k * 1024,
        "avail_bytes": avail_k * 1024,
        "capacity": cap,
        "size_human": bytes_to_human(size_k * 1024),
        "used_human": bytes_to_human(used_k * 1024),
        "avail_human": bytes_to_human(avail_k * 1024),
    }


def list_top_children(path: str, limit: int = 12) -> list[dict]:
    """List biggest immediate children under a directory."""
    p = Path(path)
    if not p.exists() or not p.is_dir():
        return []

    # Use one `du` call for speed instead of one call per child.
    out = run(f"du -sk -d 1 {shlex.quote(path)}")
    if not out:
        return []

    items: list[dict] = []
    base = str(p)
    for line in out.splitlines():
        parts = line.strip().split("\t")
        if len(parts) != 2:
            continue
        try:
            kb = int(parts[0])
        except Exception:
            continue
        full = parts[1]
        if full == base:
            continue
        name = os.path.basename(full.rstrip("/"))
        size = kb * 1024
        items.append(
            {
                "name": name,
                "path": full,
                "size_bytes": size,
                "size_human": bytes_to_human(size),
            }
        )

    items.sort(key=lambda x: x["size_bytes"], reverse=True)
    return items[:limit]


def resolve_clis() -> list[dict]:
    """Resolve important CLIs to concrete executable paths."""
    result = []
    for cmd in CLI_COMMANDS:
        resolved = run(f"command -v {shlex.quote(cmd)}") or "not-found"
        result.append({"command": cmd, "resolved": resolved})
    return result


def build_snapshot() -> dict:
    """Build full dashboard JSON payload."""
    key_locations = []
    for label, path in KEY_PATHS:
        exists = os.path.exists(path)
        size = du_bytes(path) if exists else 0
        key_locations.append(
            {
                "label": label,
                "path": path,
                "exists": exists,
                "size_bytes": size,
                "size_human": bytes_to_human(size),
            }
        )

    key_locations.sort(key=lambda x: x["size_bytes"], reverse=True)

    path_entries = os.environ.get("PATH", "").split(":")

    snapshot = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "host": {
            "hostname": socket.gethostname(),
            "user": os.environ.get("USER", "unknown"),
            "platform": platform.platform(),
            "python": platform.python_version(),
        },
        "disk_root": get_df_root(),
        "key_locations": key_locations,
        "clis": resolve_clis(),
        "path_entries": path_entries,
        "fragmentation_hints": FRAGMENTATION_HINTS,
        "breakdowns": {
            "home": list_top_children("/Users/apple", limit=15),
            "library": list_top_children("/Users/apple/Library", limit=15),
            "claude_home": list_top_children("/Users/apple/.claude", limit=15),
            "claude_app_support": list_top_children(
                "/Users/apple/Library/Application Support/Claude", limit=15
            ),
            "npm_globals": list_top_children(
                "/Users/apple/.npm-global/lib/node_modules", limit=15
            ),
            "documents": list_top_children("/Users/apple/Documents", limit=15),
        },
    }
    return snapshot


def load_history() -> list[dict]:
    """Read existing history entries if present."""
    if not HISTORY_FILE.exists():
        return []
    try:
        raw = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        if isinstance(raw, list):
            return raw
    except Exception:
        return []
    return []


def update_history(snapshot: dict) -> list[dict]:
    """Append a compact trend point and keep only recent history."""
    key_locations = snapshot.get("key_locations", [])
    total_tracked = sum(int(x.get("size_bytes", 0)) for x in key_locations)
    largest = key_locations[0] if key_locations else {}

    entry = {
        "generated_at_utc": snapshot.get("generated_at_utc"),
        "total_tracked_bytes": total_tracked,
        "total_tracked_human": bytes_to_human(total_tracked),
        "largest_label": largest.get("label", ""),
        "largest_bytes": int(largest.get("size_bytes", 0) or 0),
        "largest_human": largest.get("size_human", "0 B"),
    }

    history = load_history()
    history.append(entry)
    # Keep last 120 points so the file stays fast for static hosting.
    history = history[-120:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history


def main() -> None:
    """Create data folder and write latest JSON snapshot."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    history = update_history(snapshot)
    snapshot["history"] = history[-30:]
    OUT_FILE.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    print(f"Wrote {HISTORY_FILE}")


if __name__ == "__main__":
    main()
