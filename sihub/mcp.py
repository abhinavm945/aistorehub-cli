import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


def get_claude_config_path() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "Claude" / "claude_desktop_config.json"
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
    else:
        return Path.home() / ".config" / "Claude" / "claude_desktop_config.json"


def get_cursor_config_paths() -> List[Path]:
    paths = []
    # Local workspace .cursor/mcp.json
    local_cursor = Path.cwd() / ".cursor" / "mcp.json"
    paths.append(local_cursor)

    # User global .cursor/mcp.json
    user_cursor = Path.home() / ".cursor" / "mcp.json"
    paths.append(user_cursor)
    return paths


def get_windsurf_config_path() -> Path:
    return Path.home() / ".codeium" / "windsurf" / "mcp_config.json"


def get_zed_config_path() -> Path:
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "Zed" / "settings.json"
    else:
        return Path.home() / ".config" / "zed" / "settings.json"


def inject_mcp_config(
    server_name: str,
    server_config: Dict[str, Any],
    target_client: str = "all",
) -> List[Tuple[str, Path, bool]]:
    """
    Injects or updates server_config in detected AI clients.
    Returns list of (client_name, path, success).
    """
    results = []

    # 1. Claude Desktop
    if target_client in ("all", "claude"):
        claude_path = get_claude_config_path()
        try:
            claude_path.parent.mkdir(parents=True, exist_ok=True)
            data: Dict[str, Any] = {"mcpServers": {}}
            if claude_path.exists():
                try:
                    with open(claude_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    shutil.copy2(claude_path, str(claude_path) + ".bak")
                except Exception:
                    data = {"mcpServers": {}}

            if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                data["mcpServers"] = {}

            data["mcpServers"][server_name] = server_config

            with open(claude_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            results.append(("Claude Desktop", claude_path, True))
        except Exception as e:
            results.append(("Claude Desktop", claude_path, False))

    # 2. Cursor IDE
    if target_client in ("all", "cursor"):
        for cursor_path in get_cursor_config_paths():
            try:
                cursor_path.parent.mkdir(parents=True, exist_ok=True)
                data = {"mcpServers": {}}
                if cursor_path.exists():
                    try:
                        with open(cursor_path, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        shutil.copy2(cursor_path, str(cursor_path) + ".bak")
                    except Exception:
                        data = {"mcpServers": {}}

                if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                    data["mcpServers"] = {}

                data["mcpServers"][server_name] = server_config

                with open(cursor_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)

                results.append(("Cursor IDE", cursor_path, True))
                break  # Updated primary cursor config
            except Exception:
                continue

    # 3. Windsurf
    if target_client in ("all", "windsurf"):
        windsurf_path = get_windsurf_config_path()
        try:
            windsurf_path.parent.mkdir(parents=True, exist_ok=True)
            data = {"mcpServers": {}}
            if windsurf_path.exists():
                try:
                    with open(windsurf_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    shutil.copy2(windsurf_path, str(windsurf_path) + ".bak")
                except Exception:
                    data = {"mcpServers": {}}

            if "mcpServers" not in data or not isinstance(data["mcpServers"], dict):
                data["mcpServers"] = {}

            data["mcpServers"][server_name] = server_config

            with open(windsurf_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            results.append(("Windsurf", windsurf_path, True))
        except Exception:
            pass

    return results
