import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


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


def list_mcp_servers(target_client: str = "all") -> Dict[str, Dict[str, Any]]:
    """
    Scans and reads configured MCP servers from all detected AI clients.
    Returns: { client_name: { "path": Path, "servers": { server_name: config } } }
    """
    clients: Dict[str, Dict[str, Any]] = {}

    # 1. Claude Desktop
    if target_client in ("all", "claude"):
        claude_path = get_claude_config_path()
        if claude_path.exists():
            try:
                with open(claude_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                servers = data.get("mcpServers", {})
                if isinstance(servers, dict) and servers:
                    clients["Claude Desktop"] = {"path": claude_path, "servers": servers}
            except Exception:
                pass

    # 2. Cursor IDE
    if target_client in ("all", "cursor"):
        for cursor_path in get_cursor_config_paths():
            if cursor_path.exists():
                try:
                    with open(cursor_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    servers = data.get("mcpServers", {})
                    if isinstance(servers, dict) and servers:
                        loc = (
                            "Cursor IDE (Local)"
                            if cursor_path.parent == Path.cwd() / ".cursor"
                            else "Cursor IDE (Global)"
                        )
                        clients[loc] = {"path": cursor_path, "servers": servers}
                except Exception:
                    continue

    # 3. Windsurf
    if target_client in ("all", "windsurf"):
        windsurf_path = get_windsurf_config_path()
        if windsurf_path.exists():
            try:
                with open(windsurf_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                servers = data.get("mcpServers", {})
                if isinstance(servers, dict) and servers:
                    clients["Windsurf"] = {"path": windsurf_path, "servers": servers}
            except Exception:
                pass

    return clients


def remove_mcp_config(
    server_name: str,
    target_client: str = "all",
) -> List[Tuple[str, Path, bool]]:
    """
    Removes server_name from detected AI clients.
    Creates timestamped .bak backups before editing.
    Returns list of (client_name, path, success).
    """
    results: List[Tuple[str, Path, bool]] = []

    # 1. Claude Desktop
    if target_client in ("all", "claude"):
        claude_path = get_claude_config_path()
        if claude_path.exists():
            try:
                with open(claude_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "mcpServers" in data and server_name in data["mcpServers"]:
                    shutil.copy2(claude_path, str(claude_path) + ".bak")
                    del data["mcpServers"][server_name]
                    with open(claude_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    results.append(("Claude Desktop", claude_path, True))
            except Exception:
                results.append(("Claude Desktop", claude_path, False))

    # 2. Cursor IDE
    if target_client in ("all", "cursor"):
        for cursor_path in get_cursor_config_paths():
            if cursor_path.exists():
                try:
                    with open(cursor_path, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    if "mcpServers" in data and server_name in data["mcpServers"]:
                        shutil.copy2(cursor_path, str(cursor_path) + ".bak")
                        del data["mcpServers"][server_name]
                        with open(cursor_path, "w", encoding="utf-8") as f:
                            json.dump(data, f, indent=2)
                        results.append(("Cursor IDE", cursor_path, True))
                except Exception:
                    continue

    # 3. Windsurf
    if target_client in ("all", "windsurf"):
        windsurf_path = get_windsurf_config_path()
        if windsurf_path.exists():
            try:
                with open(windsurf_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if "mcpServers" in data and server_name in data["mcpServers"]:
                    shutil.copy2(windsurf_path, str(windsurf_path) + ".bak")
                    del data["mcpServers"][server_name]
                    with open(windsurf_path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
                    results.append(("Windsurf", windsurf_path, True))
            except Exception:
                pass

    return results


class LintIssue:
    def __init__(self, severity: str, server: str, message: str, suggestion: str = ""):
        self.severity = severity  # "ERROR", "WARN", "INFO"
        self.server = server
        self.message = message
        self.suggestion = suggestion


class ClientLintReport:
    def __init__(self, client_name: str, path: Path):
        self.client_name = client_name
        self.path = path
        self.exists = False
        self.valid_json = True
        self.syntax_error: Optional[str] = None
        self.server_count = 0
        self.issues: List[LintIssue] = []
        self.fixed = False


def _lint_single_file(client_name: str, path: Path, auto_fix: bool = False) -> ClientLintReport:
    import re
    import shutil

    report = ClientLintReport(client_name, path)
    if not path.exists():
        report.exists = False
        return report

    report.exists = True
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    
    # 1. Test standard JSON parsing
    data = None
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as err:
        report.valid_json = False
        report.syntax_error = f"{err.msg} at line {err.lineno}, col {err.colno}"
        
        # Check for common syntax culprits: trailing commas and comments
        has_trailing_commas = bool(re.search(r",\s*([}\]])", raw_text))
        has_comments = bool(re.search(r"(//.*|/\*.*?\*/)", raw_text, re.DOTALL))
        
        if has_trailing_commas or has_comments:
            clean_candidate = re.sub(r"//.*", "", raw_text)
            clean_candidate = re.sub(r"/\*.*?\*/", "", clean_candidate, flags=re.DOTALL)
            clean_candidate = re.sub(r",\s*([}\]])", r"\1", clean_candidate)
            
            try:
                fixed_data = json.loads(clean_candidate)
                if auto_fix:
                    shutil.copy2(path, str(path) + ".bak")
                    path.write_text(json.dumps(fixed_data, indent=2), encoding="utf-8")
                    report.fixed = True
                    report.valid_json = True
                    data = fixed_data
                    report.issues.append(
                        LintIssue(
                            "INFO",
                            "FILE",
                            "Auto-fixed JSON formatting errors (removed trailing commas/comments). Backup created at .bak",
                            "No action needed",
                        )
                    )
                else:
                    report.issues.append(
                        LintIssue(
                            "ERROR",
                            "FILE",
                            f"JSON syntax error ({report.syntax_error}). Found trailing commas or comments which break Cursor/Claude.",
                            "Run 'aihub lint --fix' to automatically clean and repair this config.",
                        )
                    )
            except Exception:
                pass

        if not report.fixed:
            report.issues.append(
                LintIssue(
                    "ERROR",
                    "FILE",
                    f"Syntax error: {report.syntax_error}",
                    "Fix manual syntax error in your editor.",
                )
            )
            return report

    if not isinstance(data, dict):
        report.issues.append(
            LintIssue(
                "ERROR",
                "ROOT",
                f"Config root must be a JSON object ({...}), found {type(data).__name__}.",
                "Wrap your servers inside { \"mcpServers\": { ... } }",
            )
        )
        return report

    # 2. Check mcpServers key
    servers = data.get("mcpServers") or data.get("mcp_servers")
    if servers is None:
        report.issues.append(
            LintIssue(
                "WARN",
                "ROOT",
                "Missing \"mcpServers\" object in configuration.",
                "Define your tools under the \"mcpServers\" key.",
            )
        )
        return report

    if not isinstance(servers, dict):
        report.issues.append(
            LintIssue(
                "ERROR",
                "ROOT",
                f"\"mcpServers\" must be a key-value dictionary, got {type(servers).__name__}.",
                "Change \"mcpServers\" to an object with server names as keys.",
            )
        )
        return report

    report.server_count = len(servers)

    # 3. Per-Server Validation
    for name, srv in servers.items():
        if not isinstance(srv, dict):
            report.issues.append(
                LintIssue("ERROR", name, f"Server config must be an object, got {type(srv).__name__}.")
            )
            continue

        cmd = srv.get("command")
        if not cmd or not isinstance(cmd, str) or not cmd.strip():
            report.issues.append(
                LintIssue(
                    "ERROR",
                    name,
                    "Missing required \"command\" attribute.",
                    "Specify execution binary (e.g., \"npx\", \"python\", \"uvx\", \"docker\").",
                )
            )
        else:
            # Check binary availability in PATH
            clean_cmd = cmd.strip()
            binary_name = Path(clean_cmd).name
            if not shutil.which(clean_cmd) and not shutil.which(binary_name):
                # Only warn for common binaries where PATH failure breaks client silently
                if binary_name in ("npx", "node", "uvx", "python", "python3", "docker", "uv"):
                    report.issues.append(
                        LintIssue(
                            "WARN",
                            name,
                            f"Binary \"{clean_cmd}\" was not found in your current system PATH.",
                            f"Verify that {binary_name} is installed and accessible from terminal shells.",
                        )
                    )

        # Check args
        args = srv.get("args")
        if args is not None:
            if not isinstance(args, list):
                report.issues.append(
                    LintIssue("ERROR", name, f"\"args\" must be an array of strings, got {type(args).__name__}.")
                )
            else:
                for idx, arg in enumerate(args):
                    arg_str = str(arg)
                    # Detect broken relative paths (e.g. ./server.js or src/index.ts)
                    if (arg_str.startswith("./") or arg_str.startswith(".\\")) and not Path(arg_str).exists():
                        report.issues.append(
                            LintIssue(
                                "WARN",
                                name,
                                f"Arg [{idx}] \"{arg_str}\" is a relative path that does not exist in the current directory.",
                                "Cursor and Claude Desktop launch servers from their own root directory. Use an absolute path or Path.resolve().",
                            )
                        )

        # Check env placeholders
        env = srv.get("env")
        if env is not None:
            if not isinstance(env, dict):
                report.issues.append(
                    LintIssue("ERROR", name, f"\"env\" must be a key-value object of strings, got {type(env).__name__}.")
                )
            else:
                for env_k, env_v in env.items():
                    val = str(env_v).strip()
                    if not val:
                        report.issues.append(
                            LintIssue(
                                "WARN",
                                name,
                                f"Environment variable \"{env_k}\" is empty.",
                                f"Provide a valid value for {env_k}.",
                            )
                        )
                    elif (
                        "<" in val
                        or "YOUR_" in val.upper()
                        or "KEY_HERE" in val.upper()
                        or val.startswith("sk-ant-api...")
                        or val.startswith("sk-proj-...")
                    ):
                        report.issues.append(
                            LintIssue(
                                "ERROR",
                                name,
                                f"Environment variable \"{env_k}\" contains unconfigured placeholder: \"{val}\"",
                                f"Replace placeholder with your actual {env_k} credentials.",
                            )
                        )

    return report


def lint_mcp_configs(
    target_client: str = "all",
    custom_file: Optional[Path] = None,
    auto_fix: bool = False,
) -> List[ClientLintReport]:
    """
    Scans, lints, and optionally auto-fixes MCP configurations across all detected AI environments.
    """
    reports: List[ClientLintReport] = []

    if custom_file:
        reports.append(_lint_single_file("Custom Config", custom_file, auto_fix=auto_fix))
        return reports

    if target_client in ("all", "claude"):
        reports.append(_lint_single_file("Claude Desktop", get_claude_config_path(), auto_fix=auto_fix))

    if target_client in ("all", "cursor"):
        for p in get_cursor_config_paths():
            scope = "Workspace" if str(p).startswith(str(Path.cwd())) else "Global User"
            reports.append(_lint_single_file(f"Cursor ({scope})", p, auto_fix=auto_fix))

    if target_client in ("all", "windsurf"):
        reports.append(_lint_single_file("Windsurf", get_windsurf_config_path(), auto_fix=auto_fix))

    if target_client in ("all", "zed"):
        reports.append(_lint_single_file("Zed", get_zed_config_path(), auto_fix=auto_fix))

    return reports
