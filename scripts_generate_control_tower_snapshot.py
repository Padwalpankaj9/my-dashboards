#!/usr/bin/env python3
"""Generate control-tower visibility snapshot for AI agent ecosystem."""

import json
import os
import re
import shlex
import socket
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
OUT_FILE = DATA_DIR / "control-tower.json"
HISTORY_FILE = DATA_DIR / "control-tower-history.json"

USER_HOME = Path("/Users/apple")
SCAN_ROOTS = [
    Path("/Users/apple/Documents/Software_Development"),
    Path("/Users/apple/Documents"),
    Path("/Users/apple/mcp-servers"),
    Path("/Users/apple/granola-ai-mcp-server"),
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

CONFIG_MARKERS = [".claude", ".codex", ".gemini", ".playwright-mcp", ".appium"]
CONFIG_FILES = ["AGENTS.md", "CLAUDE.md", "settings.local.json", "settings.json"]

MCP_CANDIDATES = [
    Path("/Users/apple/.claude/mcp-servers"),
    Path("/Users/apple/mcp-servers"),
    Path("/Users/apple/Documents/gmail-mcp"),
    Path("/Users/apple/granola-ai-mcp-server"),
    Path("/Users/apple/.playwright-mcp"),
    Path("/Users/apple/Documents/.playwright-mcp"),
]


def run(cmd: str) -> str:
    """Run shell command and return stdout."""
    try:
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL)
        return out.strip()
    except Exception:
        return ""


def bytes_to_human(n: int) -> str:
    """Convert bytes to readable text."""
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(n)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{n} B"


def du_bytes(path: Path) -> int:
    """Get folder size quickly via du."""
    if not path.exists():
        return 0
    out = run(f"du -sk {shlex.quote(str(path))}")
    if not out:
        return 0
    try:
        return int(out.split()[0]) * 1024
    except Exception:
        return 0


def read_text(path: Path) -> str:
    """Read UTF-8 text safely."""
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def resolve_cli_manager(resolved: str) -> str:
    """Infer CLI manager from path prefix."""
    if resolved == "not-found":
        return "missing"
    if resolved.startswith("/opt/homebrew"):
        return "homebrew"
    if resolved.startswith("/Users/apple/.npm-global"):
        return "npm-global"
    if resolved.startswith("/Users/apple/.local/bin"):
        target = run(f"readlink {shlex.quote(resolved)}")
        if "/Users/apple/.local/share/uv/tools/" in target:
            return "uv-tool"
        return "local-bin"
    if resolved.startswith("/usr/bin") or resolved.startswith("/bin"):
        return "system"
    return "other"


def collect_clis() -> list[dict]:
    """Collect CLI command locations."""
    items = []
    for cmd in CLI_COMMANDS:
        resolved = run(f"command -v {shlex.quote(cmd)}") or "not-found"
        items.append(
            {
                "command": cmd,
                "resolved": resolved,
                "manager": resolve_cli_manager(resolved),
            }
        )
    return items


def find_git_repos() -> list[Path]:
    """Find git repos in key roots."""
    repos: set[str] = set()
    for root in SCAN_ROOTS:
        if not root.exists():
            continue
        cmd = (
            f"find {shlex.quote(str(root))} "
            "-type d \\( -name node_modules -o -name .venv -o -name venv -o -name .git \\) "
            "-prune -print"
        )
        out = run(cmd)
        for line in out.splitlines():
            p = Path(line)
            if p.name == ".git":
                repos.add(str(p.parent))
    return sorted(Path(x) for x in repos)


def repo_info(repo: Path) -> dict:
    """Collect git status for one repo."""
    branch = run(f"git -C {shlex.quote(str(repo))} branch --show-current") or "detached"
    porcelain = run(f"git -C {shlex.quote(str(repo))} status --porcelain")
    dirty = bool(porcelain)
    last_ts = run(f"git -C {shlex.quote(str(repo))} log -1 --format=%ct")
    days_since = None
    if last_ts.isdigit():
        now = int(datetime.now(timezone.utc).timestamp())
        days_since = int((now - int(last_ts)) / 86400)
    status = "active"
    if days_since is not None and days_since > 45:
        status = "stale"
    return {
        "name": repo.name,
        "path": str(repo),
        "branch": branch,
        "dirty": dirty,
        "days_since_commit": days_since,
        "status": status,
    }


def collect_projects() -> dict:
    """Collect active and stale project repos."""
    repos = [repo_info(r) for r in find_git_repos()]
    repos.sort(key=lambda x: (x["status"], x.get("days_since_commit") or 99999))
    active = [r for r in repos if r["status"] == "active"]
    stale = [r for r in repos if r["status"] == "stale"]
    dirty = [r for r in repos if r["dirty"]]
    return {
        "total": len(repos),
        "active_count": len(active),
        "stale_count": len(stale),
        "dirty_count": len(dirty),
        "repos": repos,
    }


def load_claude_config_text() -> str:
    """Load local Claude config text for reference detection."""
    paths = [
        USER_HOME / ".claude/settings.json",
        USER_HOME / ".claude/settings.local.json",
        USER_HOME / "Documents/.claude/settings.local.json",
    ]
    return "\n".join(read_text(p) for p in paths if p.exists())


def collect_mcps(config_text: str) -> dict:
    """Collect MCP roots and infer active/broken/unused state."""
    entries: list[dict] = []

    # Add directory children where each child is an MCP server candidate.
    for path in MCP_CANDIDATES:
        if path.is_dir() and path.name in {"mcp-servers"}:
            for child in sorted(path.iterdir()):
                if child.is_dir():
                    entries.append({"name": child.name, "path": str(child)})
        elif path.exists():
            entries.append({"name": path.name, "path": str(path)})

    # Add config-referenced MCP path strings to catch missing entries.
    referenced_paths = set(re.findall(r"/Users/apple[^\"'\s,]+", config_text))
    for rp in sorted(referenced_paths):
        if "mcp" in rp.lower() and not any(e["path"] == rp for e in entries):
            entries.append({"name": Path(rp).name, "path": rp})

    dedup = {(e["name"], e["path"]): e for e in entries}
    items = list(dedup.values())

    for item in items:
        p = Path(item["path"])
        exists = p.exists()
        size_bytes = du_bytes(p) if exists else 0
        referenced = (
            item["name"].lower() in config_text.lower() or item["path"] in config_text
        )

        if referenced and not exists:
            status = "broken"
        elif referenced and exists:
            status = "active"
        elif exists:
            status = "unused"
        else:
            status = "broken"

        item.update(
            {
                "exists": exists,
                "referenced": referenced,
                "status": status,
                "size_bytes": size_bytes,
                "size_human": bytes_to_human(size_bytes),
            }
        )

    items.sort(key=lambda x: (x["status"], x["name"]))
    return {
        "total": len(items),
        "active": sum(1 for x in items if x["status"] == "active"),
        "broken": sum(1 for x in items if x["status"] == "broken"),
        "unused": sum(1 for x in items if x["status"] == "unused"),
        "items": items,
    }


def collect_configs() -> dict:
    """Collect config marker locations and duplication counts."""
    base = Path("/Users/apple")
    markers: list[dict] = []

    find_cmd = (
        r"find /Users/apple -maxdepth 4 "
        r"\( -path '/Users/apple/Library' -o -path '/Users/apple/.cache' -o -path '/Users/apple/.Trash' \) -prune -o "
        r"\( -name '.claude' -o -name '.codex' -o -name '.gemini' -o -name '.playwright-mcp' -o -name '.appium' "
        r"-o -name 'AGENTS.md' -o -name 'CLAUDE.md' -o -name 'settings.local.json' -o -name 'settings.json' \) -print"
    )

    out = run(find_cmd)
    for line in out.splitlines():
        p = Path(line)
        marker_type = p.name
        markers.append(
            {
                "type": marker_type,
                "path": str(p),
                "is_dir": p.is_dir(),
            }
        )

    counts: dict[str, int] = {}
    for m in markers:
        counts[m["type"]] = counts.get(m["type"], 0) + 1

    duplicate_types = {k: v for k, v in counts.items() if v > 1}
    return {
        "total_markers": len(markers),
        "duplicate_types": duplicate_types,
        "markers": sorted(markers, key=lambda x: (x["type"], x["path"])),
    }


def collect_automations() -> dict:
    """Collect cron and launch agent visibility."""
    crontab_text = run("crontab -l")
    cron_lines = [
        line.strip()
        for line in crontab_text.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]

    launch_agents = []
    la_dir = USER_HOME / "Library/LaunchAgents"
    if la_dir.exists():
        for f in sorted(la_dir.glob("*.plist")):
            name = f.name
            content = read_text(f)
            if any(k in (name + content).lower() for k in ["claude", "codex", "gemini", "mcp", "playwright", "agent"]):
                launch_agents.append({"name": name, "path": str(f)})

    status = "healthy"
    if not cron_lines and not launch_agents:
        status = "missing"

    return {
        "status": status,
        "cron_jobs": cron_lines,
        "launch_agents": launch_agents,
    }


def collect_secrets_hygiene() -> dict:
    """Collect secrets hygiene without exposing secret values."""
    secrets_env = USER_HOME / ".config/shell/secrets.env"
    exists = secrets_env.exists()
    export_vars = []
    if exists:
        for line in read_text(secrets_env).splitlines():
            line = line.strip()
            if line.startswith("export ") and "=" in line:
                key = line.split("=", 1)[0].replace("export", "").strip()
                export_vars.append(key)

    env_find = run(
        r"find /Users/apple/Documents /Users/apple -maxdepth 3 "
        r"\( -path '/Users/apple/Library' -o -path '/Users/apple/.cache' -o -path '/Users/apple/.npm-global' \) -prune -o "
        r"\( -name '.env' -o -name '.env.*' \) -type f -print"
    )
    env_files = sorted(set(env_find.splitlines())) if env_find else []

    risky_keys = set()
    key_pattern = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*.+$")
    sensitive_hint = re.compile(r"(KEY|TOKEN|SECRET|PASSWORD)", re.IGNORECASE)
    for ef in env_files:
        text = read_text(Path(ef))
        for line in text.splitlines():
            if line.strip().startswith("#"):
                continue
            m = key_pattern.match(line)
            if not m:
                continue
            key = m.group(1)
            if sensitive_hint.search(key):
                risky_keys.add(key)

    return {
        "secrets_env_exists": exists,
        "secrets_env_path": str(secrets_env),
        "managed_vars_count": len(export_vars),
        "managed_vars": sorted(export_vars),
        "env_files_count": len(env_files),
        "env_files": env_files,
        "sensitive_keys_found": sorted(risky_keys),
    }


def score_containment(projects: dict, mcps: dict, configs: dict, automations: dict) -> dict:
    """Compute simple containment score for control confidence."""
    score = 100
    penalties = []

    if projects["stale_count"] > 0:
        p = min(20, projects["stale_count"] * 2)
        score -= p
        penalties.append({"reason": "stale_projects", "points": p})

    if projects["dirty_count"] > 0:
        p = min(15, projects["dirty_count"])
        score -= p
        penalties.append({"reason": "dirty_repos", "points": p})

    if mcps["broken"] > 0:
        p = min(25, mcps["broken"] * 5)
        score -= p
        penalties.append({"reason": "broken_mcps", "points": p})

    duplicate_count = sum(configs["duplicate_types"].values())
    if duplicate_count > 0:
        p = min(20, duplicate_count)
        score -= p
        penalties.append({"reason": "duplicate_configs", "points": p})

    if automations["status"] == "missing":
        score -= 10
        penalties.append({"reason": "no_automation_visibility", "points": 10})

    score = max(0, score)
    status = "good" if score >= 75 else "warning" if score >= 55 else "critical"
    return {"score": score, "status": status, "penalties": penalties}


def load_history() -> list[dict]:
    """Load previous history points."""
    if not HISTORY_FILE.exists():
        return []
    try:
        data = json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def write_history(point: dict) -> list[dict]:
    """Append a history point and keep rolling history."""
    history = load_history()
    history.append(point)
    history = history[-180:]
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")
    return history


def build_snapshot() -> dict:
    """Build control tower snapshot payload."""
    clis = collect_clis()
    projects = collect_projects()
    config_text = load_claude_config_text()
    mcps = collect_mcps(config_text)
    configs = collect_configs()
    automations = collect_automations()
    secrets = collect_secrets_hygiene()

    containment = score_containment(projects, mcps, configs, automations)

    system_map = {
        "nodes": [
            {"id": "agents", "label": "Agents", "status": "good", "count": 2},
            {"id": "skills", "label": "Skills", "status": "good", "count": 0},
            {"id": "mcps", "label": "MCPs", "status": "warning" if mcps["broken"] == 0 else "critical", "count": mcps["total"]},
            {"id": "clis", "label": "CLIs", "status": "good", "count": len(clis)},
            {"id": "configs", "label": "Configs", "status": "warning" if configs["duplicate_types"] else "good", "count": configs["total_markers"]},
            {"id": "automations", "label": "Automations", "status": "good" if automations["status"] == "healthy" else "warning", "count": len(automations["cron_jobs"])},
            {"id": "projects", "label": "Projects", "status": "warning" if projects["stale_count"] else "good", "count": projects["total"]},
            {"id": "secrets", "label": "Secrets", "status": "good" if secrets["secrets_env_exists"] else "critical", "count": secrets["managed_vars_count"]},
        ],
        "edges": [
            {"from": "agents", "to": "skills"},
            {"from": "agents", "to": "mcps"},
            {"from": "agents", "to": "clis"},
            {"from": "mcps", "to": "configs"},
            {"from": "clis", "to": "projects"},
            {"from": "automations", "to": "projects"},
            {"from": "secrets", "to": "mcps"},
        ],
    }

    now = datetime.now(timezone.utc).isoformat()
    summary = {
        "generated_at_utc": now,
        "host": f"{os.environ.get('USER','unknown')}@{socket.gethostname()}",
        "containment_score": containment["score"],
        "containment_status": containment["status"],
        "active_projects": projects["active_count"],
        "stale_projects": projects["stale_count"],
        "mcp_active": mcps["active"],
        "mcp_broken": mcps["broken"],
        "mcp_unused": mcps["unused"],
        "duplicate_config_types": len(configs["duplicate_types"]),
        "cron_jobs": len(automations["cron_jobs"]),
    }

    point = {
        "generated_at_utc": now,
        "containment_score": containment["score"],
        "active_projects": projects["active_count"],
        "stale_projects": projects["stale_count"],
        "mcp_broken": mcps["broken"],
    }
    history = write_history(point)

    snapshot = {
        "summary": summary,
        "system_map": system_map,
        "containment": containment,
        "projects": projects,
        "mcps": mcps,
        "clis": clis,
        "configs": configs,
        "automations": automations,
        "secrets": secrets,
        "history": history[-30:],
    }
    return snapshot


def main() -> None:
    """Generate control tower JSON snapshot."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    snapshot = build_snapshot()
    OUT_FILE.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"Wrote {OUT_FILE}")
    print(f"Wrote {HISTORY_FILE}")


if __name__ == "__main__":
    main()
