import os
import sys
from pathlib import Path
import click
from typing import Optional, Dict, Any, List

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from .config import get_config, set_token, clear_auth, get_token, DEFAULT_API_URL
from .client import APIClient
from .mcp import inject_mcp_config, list_mcp_servers, remove_mcp_config
from .packager import inspect_directory, create_bundle_zip


@click.group()
@click.version_option("0.1.8", prog_name="aistorehub")
@click.option("--no-telemetry", is_flag=True, default=False, help="Disable anonymous usage telemetry for this command invocation")
def cli(no_telemetry: bool = False):
    """
    aistorehub - The Official AIStoreHub Developer CLI.
    Discover, pull, publish, and auto-configure AI systems and MCP servers.
    """
    if no_telemetry:
        import os
        os.environ["DO_NOT_TRACK"] = "1"


def _run_browser_login(
    frontend_base_url: str = "https://aistorehub.in",
    api_base_url: str = DEFAULT_API_URL,
) -> Optional[str]:
    import socket
    import secrets
    import hashlib
    import base64
    import webbrowser
    import httpx
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import urlparse, parse_qs

    # Find a free local port on loopback interface
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()

    # Generate cryptographically secure PKCE verifier & challenge (RFC 7636 / RFC 8252)
    code_verifier = secrets.token_urlsafe(64)
    verifier_bytes = code_verifier.encode("ascii")
    code_challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier_bytes).digest()).decode("ascii").rstrip("=")

    expected_state = secrets.token_urlsafe(32)
    captured_data = {"token": None, "error": None}

    class CallbackHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            if parsed.path == "/callback":
                params = parse_qs(parsed.query)
                state = params.get("state", [""])[0]
                code = params.get("code", [""])[0]
                legacy_token = params.get("token", [""])[0]

                if not secrets.compare_digest(state, expected_state):
                    captured_data["error"] = "State verification failed (CSRF check mismatch)."
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<html><body><h3>State mismatch error. Please retry login.</h3></body></html>")
                    return

                if code:
                    # Secure PKCE Backchannel Exchange (RFC 7636)
                    # Directly exchange ephemeral single-use code for PAT over HTTPS
                    try:
                        with httpx.Client(timeout=15.0) as http_client:
                            resp = http_client.post(
                                f"{api_base_url.rstrip('/')}/auth/cli/exchange",
                                json={"code": code, "code_verifier": code_verifier},
                                headers={"Accept": "application/json", "User-Agent": "aistorehub-cli/0.1.5"},
                            )
                            if resp.status_code != 200:
                                err_detail = resp.text
                                try:
                                    err_detail = resp.json().get("detail", err_detail)
                                except Exception:
                                    pass
                                captured_data["error"] = f"PKCE exchange failed: {err_detail}"
                                self.send_response(400)
                                self.send_header("Content-Type", "text/html; charset=utf-8")
                                self.end_headers()
                                self.wfile.write(f"<html><body><h3>Authorization code exchange failed: {err_detail}</h3></body></html>".encode("utf-8"))
                                return
                            exchange_data = resp.json()
                            captured_data["token"] = exchange_data["token"]
                    except Exception as exc:
                        captured_data["error"] = f"Backchannel communication error: {exc}"
                        self.send_response(500)
                        self.send_header("Content-Type", "text/html; charset=utf-8")
                        self.end_headers()
                        self.wfile.write(b"<html><body><h3>Failed to communicate with AIStoreHub backend. Please retry login.</h3></body></html>")
                        return
                elif legacy_token:
                    captured_data["token"] = legacy_token
                else:
                    captured_data["error"] = "No authorization code or token received in callback."
                    self.send_response(400)
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.end_headers()
                    self.wfile.write(b"<html><body><h3>No authorization code received. Please retry login.</h3></body></html>")
                    return

                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                html = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>AIStoreHub CLI Authorized</title>
  <style>
    body { background: #09090b; color: #f4f4f5; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
    .card { text-align: center; max-width: 420px; padding: 40px 32px; background: #18181b; border-radius: 20px; border: 1px solid rgba(16, 185, 129, 0.3); box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5); }
    .badge { display: inline-block; background: rgba(16, 185, 129, 0.15); color: #34d399; padding: 6px 14px; border-radius: 9999px; font-size: 13px; font-weight: 600; margin-bottom: 16px; border: 1px solid rgba(16, 185, 129, 0.25); }
    h1 { font-size: 22px; font-weight: 700; margin: 0 0 10px 0; color: #ffffff; }
    p { font-size: 14px; color: #a1a1aa; line-height: 1.5; margin: 0 0 24px 0; }
    .btn { display: inline-block; background: #27272a; color: #e4e4e7; padding: 8px 16px; border-radius: 10px; font-size: 12px; font-weight: 500; text-decoration: none; border: 1px solid #3f3f46; cursor: pointer; }
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">&#10003; Successfully Authorized</div>
    <h1>CLI Connected!</h1>
    <p>Your AIStoreHub terminal session has been authenticated securely via PKCE. You can close this window and return to your terminal.</p>
    <button class="btn" onclick="window.close()">Close Window</button>
  </div>
</body>
</html>"""
                self.wfile.write(html.encode("utf-8"))
            else:
                self.send_response(404)
                self.end_headers()

    server = HTTPServer(("127.0.0.1", port), CallbackHandler)
    server.timeout = 180

    auth_url = (
        f"{frontend_base_url.rstrip('/')}/cli/auth?"
        f"port={port}&state={expected_state}&code_challenge={code_challenge}"
    )

    click.echo("\n--- AIStoreHub 1-Click Login ---")
    click.echo("Opening your default browser to authenticate...")
    click.echo("If your browser does not open automatically, visit:")
    click.secho(f"  {auth_url}\n", fg="cyan", bold=True)
    click.echo("Waiting for browser authorization (or press Ctrl+C to cancel)...")

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    try:
        while not captured_data["token"] and not captured_data["error"]:
            server.handle_request()
    except KeyboardInterrupt:
        click.secho("\nLogin cancelled by user.", fg="yellow")
        return None

    if captured_data["error"]:
        click.secho(f"✗ Login error: {captured_data['error']}", fg="red")
        return None

    return captured_data["token"]


@cli.command()
@click.option("--token-stdin", is_flag=True, default=False, help="Read Personal Access Token from standard input (recommended for CI/CD and automation).")
@click.option("--interactive", "-i", is_flag=True, default=False, help="Prompt interactively for token with hidden input (no browser).")
@click.option("--token", default=None, help="Personal Access Token (PAT). Warning: may be recorded in shell history.")
@click.option("--url", default=None, help="Custom AIStoreHub API URL")
def login(token_stdin: bool, interactive: bool, token: Optional[str], url: Optional[str]):
    """
    Log in to AIStoreHub.
    Opens your browser for 1-click authorization, reads securely via --token-stdin,
    or prompts interactively with hidden input.
    """
    cfg = get_config()
    if url:
        cfg["api_url"] = url

    # 1. Pipeline / Stdin input (avoids shell history & ps monitoring)
    if token_stdin:
        token = sys.stdin.read().strip()
        if not token:
            click.secho("Error: No token received from standard input.", fg="red")
            sys.exit(1)

    # 2. Interactive hidden prompt
    elif interactive:
        token = click.prompt("Enter your AIStoreHub Personal Access Token (PAT)", hide_input=True)

    # 3. Direct argument (warn about shell history)
    elif token:
        click.secho(
            "Security Notice: Passing tokens directly via command-line arguments can expose secrets "
            "in shell history and process monitoring tools. For CI/CD, prefer setting AISTOREHUB_TOKEN "
            "or piping via 'aihub login --token-stdin'.",
            fg="yellow",
        )

    # 4. Default: 1-Click browser login with PKCE
    else:
        api_url = cfg.get("api_url", DEFAULT_API_URL)
        if "localhost" in api_url or "127.0.0.1" in api_url:
            frontend_url = "http://localhost:3000"
        else:
            frontend_url = "https://aistorehub.in"

        token = _run_browser_login(frontend_url, api_url)
        if not token:
            click.echo("\nManual login fallback:")
            token = click.prompt("Enter your AIStoreHub Personal Access Token (PAT)", hide_input=True)

    if not token or not token.strip():
        click.secho("Login aborted: No token provided.", fg="yellow")
        return

    set_token(token.strip())

    client = APIClient()
    try:
        user = client.whoami()
        username = user.get("username", "developer")
        click.secho(f"\n✓ Successfully authenticated as @{username}!", fg="green", bold=True)
        set_token(token.strip(), user_info=user)
    except Exception as e:
        click.secho(f"✗ Login verification failed: {e}", fg="red")
        clear_auth()
        sys.exit(1)


@cli.command()
def logout():
    """Log out and remove stored credentials."""
    clear_auth()
    click.secho("✓ Successfully logged out from AIStoreHub.", fg="green")


@cli.command()
def whoami():
    """Display the currently authenticated user."""
    client = APIClient()
    token = get_token()
    if not token:
        click.secho("Not logged in. Run 'aistorehub login' or set AISTOREHUB_TOKEN.", fg="yellow")
        sys.exit(1)

    try:
        user = client.whoami()
        click.echo("---")
        click.secho(f"User:        {user.get('display_name', '')} (@{user.get('username')})", bold=True)
        click.echo(f"Email:       {user.get('email', '')}")
        click.echo(f"ID:          {user.get('id', '')}")
        click.echo(f"Admin:       {user.get('is_admin', False)}")
        click.echo("---")
    except Exception as e:
        click.secho(f"Error: {e}", fg="red")
        sys.exit(1)


@cli.command()
@click.argument("query", default="")
@click.option("--limit", default=10, help="Number of items to return")
def search(query: str, limit: int):
    """Search AI systems, agents, and MCP servers in the store."""
    client = APIClient()
    try:
        items = client.search(query=query, limit=limit)
        if not items:
            click.echo("No systems found matching your query.")
            return

        click.secho(f"Found {len(items)} AI systems in store:\n", bold=True)
        for it in items:
            name = it.get("name", "Unknown")
            slug = it.get("slug", "")
            owner = it.get("repository", {}).get("owner", {}).get("username", "store")
            sys_type = it.get("type", "agent")
            desc = it.get("description") or "No description provided."
            stars = it.get("save_count", 0)

            click.secho(f"• {owner}/{slug} ", fg="cyan", bold=True, nl=False)
            click.secho(f"[{sys_type.upper()}] ★ {stars}", fg="yellow")
            click.echo(f"  {desc[:90]}")
            click.echo("")
    except Exception as e:
        click.secho(f"Search error: {e}", fg="red")
        sys.exit(1)


def _display_mcp_list(target_client: str = "all"):
    clients = list_mcp_servers(target_client=target_client)
    if not clients:
        click.secho("No active MCP servers found in detected AI clients.", fg="yellow")
        click.echo("To configure one, run: aihub mcp install <owner>/<system>")
        return

    click.echo("\n" + "=" * 76)
    click.secho("Active MCP Servers Configured Across AI Clients", fg="bright_white", bold=True)
    click.echo("=" * 76)

    total_servers = 0
    for client_name, info in clients.items():
        path = info["path"]
        servers = info["servers"]
        total_servers += len(servers)
        click.secho(f"\n● {client_name}", fg="cyan", bold=True)
        click.echo(f"  Config: {path}")
        for sname, scfg in servers.items():
            transport = scfg.get("transport") or ("command" if "command" in scfg else "sse")
            url_or_cmd = scfg.get("url") or (f"{scfg.get('command')} {' '.join(scfg.get('args', []))}") or "Custom"
            click.secho(f"  ✔ {sname}", fg="green", bold=True, nl=False)
            click.echo(f" [{transport}] -> {url_or_cmd}")

    click.echo("\n" + "=" * 76)
    click.echo(f"Total: {total_servers} active server configuration(s)")
    click.echo("To remove a server: aihub mcp remove <server_name>\n")


@cli.command(name="list")
@click.option("--client", "target_client", default="all", type=click.Choice(["all", "claude", "cursor", "windsurf"]), help="Target AI client")
def list_cmd(target_client: str = "all"):
    """
    List all active MCP servers configured across Cursor, Claude Desktop, and Windsurf.
    Example: aihub list
    """
    _display_mcp_list(target_client=target_client)


@cli.command()
@click.argument("target", required=False)
@click.argument("sub_target", required=False)
@click.option("--client", "target_client", default="all", type=click.Choice(["all", "claude", "cursor", "windsurf"]), help="Target AI client")
@click.option("--remove", "-r", is_flag=True, default=False, help="Remove the specified MCP server from client configuration")
@click.option("--no-telemetry", is_flag=True, default=False, help="Disable anonymous usage telemetry for this command")
def mcp(
    target: Optional[str] = None,
    sub_target: Optional[str] = None,
    target_client: str = "all",
    remove: bool = False,
    no_telemetry: bool = False,
):
    """
    Auto-configure, list, or remove MCP servers in Claude Desktop, Cursor, or Windsurf.
    Examples:
      aihub mcp install community/stitch-skills
      aihub mcp list
      aihub mcp remove stitch-skills
    """
    if no_telemetry:
        import os
        os.environ["DO_NOT_TRACK"] = "1"

    # Handle sub-command style: aihub mcp list / aihub mcp ls
    if not target or target in ("list", "ls"):
        _display_mcp_list(target_client=target_client)
        return

    # Handle removal: aihub mcp remove <name> / aihub mcp uninstall <name> / aihub mcp <name> --remove
    if target in ("remove", "rm", "uninstall", "delete"):
        is_removal = True
        actual_target = sub_target
        if not actual_target:
            click.secho("Error: Missing target server name to remove.", fg="red", bold=True)
            click.echo("Usage: aihub mcp remove <server_name>")
            click.echo("Example: aihub mcp remove stitch-skills")
            return
    elif target in ("install", "add") and sub_target:
        is_removal = False
        actual_target = sub_target
    else:
        is_removal = remove
        actual_target = target

    if not actual_target:
        click.secho("Error: Missing target server name. Example: aihub mcp install community/stitch-skills", fg="red")
        return

    parts = actual_target.strip("/").split("/")
    owner = parts[0] if len(parts) > 1 else "public"
    system_slug = parts[-1]

    if is_removal:
        click.echo(f"Removing MCP server '{system_slug}' from detected clients...")
        results = remove_mcp_config(system_slug, target_client=target_client)
        if not results:
            click.secho(f"No configured server matching '{system_slug}' found in client configs.", fg="yellow")
            return
        click.echo("")
        for client_name, path, ok in results:
            if ok:
                click.secho(f"✓ Removed from {client_name}", fg="green", bold=True)
                click.echo(f"  Location: {path}")
            else:
                click.secho(f"✗ Failed to update {client_name} at {path}", fg="red")
        click.secho("\nRestart your AI client to apply changes.", fg="bright_white", bold=True)
        return

    # Install / Inject
    api = APIClient()
    click.echo(f"Fetching MCP configuration for {owner}/{system_slug}...")

    server_url = f"https://mcp.aistorehub.in/{owner}/{system_slug}/sse"
    try:
        sys_data = api.get_system(owner=owner, system_slug=system_slug)
        offers = sys_data.get("distribution_offers", [])
        mcp_offer = next((o for o in offers if o.get("channel") == "mcp"), None)
        if mcp_offer and mcp_offer.get("endpoint_url"):
            server_url = mcp_offer["endpoint_url"]
    except Exception:
        # Proceed with canonical url
        pass

    server_config = {
        "url": server_url,
        "transport": "sse",
    }

    results = inject_mcp_config(system_slug, server_config, target_client=target_client)
    if not results:
        click.secho("No supported AI clients detected on your machine.", fg="yellow")
        return

    click.echo("")
    any_success = any(ok for _, _, ok in results)
    if any_success and "sys_data" in locals() and sys_data and sys_data.get("id"):
        api.log_event("mcp_configured", system_id=sys_data["id"])

    for client_name, path, ok in results:
        if ok:
            click.secho(f"✓ Configured for {client_name}", fg="green", bold=True)
            click.echo(f"  Location: {path}")
        else:
            click.secho(f"✗ Failed to configure {client_name} at {path}", fg="red")

    click.secho("\nRestart your AI client to start using the tools!", fg="bright_white", bold=True)


@cli.command()
@click.argument("target")
def info(target: str):
    """
    Display system metadata, license, upstream provenance, and installation commands.
    Example: aistorehub info mcp-server-postgres
    """
    parts = target.strip("/").split("/")
    if len(parts) >= 3:
        owner = parts[0]
        repo = parts[1]
        system_slug = parts[2]
    elif len(parts) == 2:
        owner = parts[0]
        repo = None
        system_slug = parts[1]
    else:
        owner = "community"
        repo = None
        system_slug = parts[0]

    api = APIClient()
    try:
        data = api.get_system(owner=owner, system_slug=system_slug, repo=repo)
    except Exception as e:
        click.secho(f"System '{target}' not found: {e}", fg="red")
        sys.exit(1)

    name = data.get("name", "Unknown System")
    sys_type = data.get("type", "unknown")
    desc = data.get("description", "No description provided.")
    curr_ver = data.get("current_version") or {}
    ver_str = curr_ver.get("version") or data.get("latest_version") or "1.0.0"
    license_str = data.get("license") or "Custom"
    manifest = data.get("manifest_data") or {}
    prov_type = manifest.get("provenance_type")
    orig_repo = manifest.get("original_repo_url") or data.get("github_repo_url")
    orig_maintainer = manifest.get("original_maintainer")
    is_claimed = manifest.get("is_claimed", False)
    instructions = curr_ver.get("instructions") or ""

    click.echo("\n" + "=" * 78)
    click.secho(f"{name} (v{ver_str}) [{sys_type}]", fg="bright_white", bold=True)
    click.echo("=" * 78)
    click.echo(f"Description: {desc}")
    click.echo(f"License:     {license_str.upper()}")
    if prov_type == "community_imported":
        click.secho(f"Provenance:  Open-source community project", fg="cyan")
        if orig_maintainer:
            click.echo(f"Maintainer:  @{orig_maintainer}")
        if orig_repo:
            click.echo(f"Upstream:    {orig_repo}")
        claim_label = "Claimed by verified maintainer" if is_claimed else "Unclaimed (Author can claim on AIStoreHub)"
        click.echo(f"Claim State: {claim_label}")

    if instructions:
        click.echo("\n--- Installation & Quickstart ---")
        click.secho(instructions.strip(), fg="green")
        click.echo("---------------------------------")

    slug_ref = f"{data.get('owner_username', owner)}/{data.get('repository_slug', 'catalog')}/{data.get('slug', system_slug)}"
    click.echo(f"\nPull bundle:   aistorehub pull {slug_ref}")
    click.echo(f"View on web:   https://aistorehub.in/{slug_ref}")
    click.echo("=" * 78 + "\n")


def _pull_upstream_github_repo(upstream_repo: str, out_dir: Path) -> int:
    """
    Downloads and extracts upstream GitHub repository codebase when no custom artifacts
    are hosted on AIStoreHub. Preserves full code structure (src, package.json, tests, etc.).
    """
    import io
    import shutil
    import zipfile
    import httpx

    cleaned = upstream_repo.strip().rstrip("/")
    if cleaned.endswith(".git"):
        cleaned = cleaned[:-4]
    if "github.com/" not in cleaned:
        return 0
    repo_path = cleaned.split("github.com/")[1]
    parts = repo_path.split("/")
    if len(parts) < 2:
        return 0
    owner, repo = parts[0], parts[1]

    urls = [
        f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/main",
        f"https://codeload.github.com/{owner}/{repo}/zip/refs/heads/master",
        f"https://api.github.com/repos/{owner}/{repo}/zipball",
    ]

    content = None
    for url in urls:
        try:
            r = httpx.get(url, headers={"User-Agent": "aistorehub-cli/0.1.5"}, follow_redirects=True, timeout=25.0)
            if r.status_code == 200 and len(r.content) > 500:
                content = r.content
                break
        except Exception:
            continue

    if not content:
        import subprocess
        import tempfile
        try:
            with tempfile.TemporaryDirectory() as tmp_dir:
                res = subprocess.run(
                    ["git", "clone", "--depth", "1", f"https://github.com/{owner}/{repo}.git", tmp_dir],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if res.returncode == 0:
                    count = 0
                    for item in Path(tmp_dir).iterdir():
                        if item.name == ".git":
                            continue
                        dest = out_dir / item.name
                        if item.is_dir():
                            shutil.copytree(item, dest, dirs_exist_ok=True)
                        else:
                            shutil.copy2(item, dest)
                        count += 1
                    return count
        except Exception:
            pass
        return 0

    try:
        zf = zipfile.ZipFile(io.BytesIO(content))
        namelist = zf.namelist()
        prefix = namelist[0].split("/")[0] + "/" if namelist and "/" in namelist[0] else ""
        count = 0
        for m in zf.infolist():
            rel = m.filename[len(prefix):] if prefix and m.filename.startswith(prefix) else m.filename
            if not rel or m.is_dir():
                continue
            dest = out_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(m) as src, open(dest, "wb") as dst:
                shutil.copyfileobj(src, dst)
            count += 1
        return count
    except Exception:
        return 0


def _do_pull_or_clone(target: str, dest: str, extract: bool, no_telemetry: bool = False, action_label: str = "Pulling"):
    """Core logic to pull or clone an AI system bundle, codebase, and instructions."""
    import json
    import zipfile

    if no_telemetry:
        import os
        os.environ["DO_NOT_TRACK"] = "1"

    parts = target.strip("/").split("/")
    if len(parts) >= 3:
        owner = parts[0]
        repo = parts[1]
        system_slug = parts[2]
    elif len(parts) == 2:
        owner = parts[0]
        repo = None
        system_slug = parts[1]
    else:
        owner = "community"
        repo = None
        system_slug = parts[0]

    api = APIClient()
    click.echo(f"{action_label} {owner}/{system_slug} from AIStoreHub...")

    try:
        sys_data = api.get_system(owner=owner, system_slug=system_slug, repo=repo)
        out_dir = Path(dest) if dest else Path.cwd() / system_slug
        out_dir.mkdir(parents=True, exist_ok=True)

        sys_type = sys_data.get("type", "prompt")
        curr_ver = sys_data.get("current_version") or {}
        repo_data = sys_data.get("repository") or {}

        # 1. Write manifest metadata
        manifest = {
            "name": sys_data.get("name"),
            "slug": sys_data.get("slug"),
            "type": sys_type,
            "version": curr_ver.get("version", "1.0.0"),
            "description": sys_data.get("description"),
            "owner": owner,
            "repository": repo_data.get("slug", "systems"),
        }
        with open(out_dir / "aistorehub.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # 2. Write instructions if available
        instructions_text = curr_ver.get("instructions")
        if not instructions_text and sys_type == "mcp_server":
            instructions_text = (
                f"Configure in Claude Desktop or Cursor:\n"
                f"Run command: aistorehub mcp {owner}/{system_slug}\n\n"
                f"Or inspect aistorehub.json and package.json to run locally.\n"
            )
        if instructions_text:
            with open(out_dir / "instructions.txt", "w", encoding="utf-8") as f:
                f.write(instructions_text)

        # 3. Write README if available and not present
        if curr_ver.get("readme") and not (out_dir / "README.md").exists():
            with open(out_dir / "README.md", "w", encoding="utf-8") as f:
                f.write(curr_ver["readme"])

        # 4. Download version artifacts (packages, scripts, configs)
        artifacts = curr_ver.get("artifacts", [])
        downloaded_count = 0
        for art in artifacts:
            art_name = art.get("name") or "artifact"
            art_id = art.get("id")
            art_text = art.get("content_text")

            if art_text is not None:
                (out_dir / art_name).write_text(art_text, encoding="utf-8")
                downloaded_count += 1
                click.secho(f"  ✓ Saved artifact: {art_name}", fg="green")
            elif art_id:
                try:
                    data = api.download_artifact(art_id)
                    art_file = out_dir / art_name
                    art_file.write_bytes(data)
                    downloaded_count += 1
                    click.secho(f"  ✓ Downloaded artifact: {art_name} ({len(data)} bytes)", fg="green")

                    # If it's a zip and extract is requested
                    if extract and art_name.lower().endswith(".zip"):
                        try:
                            with zipfile.ZipFile(art_file, "r") as zf:
                                zf.extractall(out_dir)
                            click.secho(f"  ✓ Extracted {art_name} into {out_dir.name}/", fg="cyan")
                        except Exception as e:
                            click.secho(f"  ! Could not extract {art_name}: {e}", fg="yellow")
                except Exception as e:
                    click.secho(f"  ! Could not download artifact {art_name}: {e}", fg="yellow")

        # 4b. If no custom artifacts are uploaded, fetch complete upstream codebase from Git repository
        manifest_meta = sys_data.get("manifest_data") or {}
        upstream_repo = sys_data.get("github_repo_url") or manifest_meta.get("original_repo_url")
        if not artifacts and upstream_repo and "github.com/" in upstream_repo:
            click.echo(f"  Fetching upstream codebase from {upstream_repo}...")
            code_files_count = _pull_upstream_github_repo(upstream_repo, out_dir)
            if code_files_count > 0:
                downloaded_count += code_files_count
                click.secho(f"  ✓ Downloaded and unpacked {code_files_count} codebase files from upstream repository", fg="green")

        past_verb = "cloned" if action_label.lower().startswith("clone") else "pulled"
        click.secho(f"\n✓ Successfully {past_verb} {owner}/{system_slug} to {out_dir.resolve()}", fg="green", bold=True)
        if sys_data and sys_data.get("id"):
            api.log_event("pull_succeeded", system_id=sys_data["id"])

        # 5. Print tailored quickstart based on system type
        click.echo("\n--- Quickstart ---")
        if sys_type == "mcp_server":
            click.secho("• Model Context Protocol (MCP) Server detected:", bold=True)
            click.echo(f"  Auto-configure into Claude Desktop or Cursor by running:")
            click.secho(f"  aistorehub mcp {owner}/{system_slug}", fg="cyan", bold=True)
        elif sys_type in ("prompt", "skill", "template"):
            click.secho(f"• {sys_type.capitalize()} instructions saved in instructions.txt", bold=True)
            click.echo("  Copy and paste instructions or integrate into your prompt pipeline.")
        elif sys_type == "workflow":
            click.secho("• Workflow template ready:", bold=True)
            click.echo("  Import workflow JSON into n8n, Make, or LangGraph.")
        elif sys_type in ("agent", "bot", "multi_agent", "ai_application"):
            click.secho(f"• {sys_type.capitalize()} project files ready in {out_dir.name}/", bold=True)
            if (out_dir / "requirements.txt").exists():
                click.echo(f"  Run: cd {out_dir.name} && pip install -r requirements.txt")
            elif (out_dir / "package.json").exists():
                click.echo(f"  Run: cd {out_dir.name} && npm install")
            click.echo(f"  Inspect agent entry point (main.py, agent.py, or index.ts) to run.")
        else:
            click.echo(f"  All deliverables saved in {out_dir.name}/")
        click.echo("------------------")

    except Exception as e:
        click.secho(f"{action_label} error: {e}", fg="red")
        sys.exit(1)


@cli.command()
@click.argument("target")
@click.option("--dest", default=None, help="Destination directory (defaults to system slug)")
@click.option("--extract/--no-extract", default=True, help="Automatically extract zip packages if downloaded")
@click.option("--no-telemetry", is_flag=True, default=False, help="Disable anonymous usage telemetry for this command")
def pull(target: str, dest: str, extract: bool, no_telemetry: bool = False):
    """
    Pull an AI system bundle, artifacts, and instructions into a local directory.
    Example: aistorehub pull community/catalog/brave-search-mcp
    """
    _do_pull_or_clone(target, dest, extract, no_telemetry, action_label="Pulling")


@cli.command()
@click.argument("target")
@click.option("--dest", default=None, help="Destination directory (defaults to system slug)")
@click.option("--extract/--no-extract", default=True, help="Automatically extract zip packages if downloaded")
@click.option("--no-telemetry", is_flag=True, default=False, help="Disable anonymous usage telemetry for this command")
def clone(target: str, dest: str, extract: bool, no_telemetry: bool = False):
    """
    Clone an AI system codebase, bundle, and configuration into a local directory.
    Alias for 'aistorehub pull'.
    Example: aistorehub clone community/catalog/brave-search-mcp
    """
    _do_pull_or_clone(target, dest, extract, no_telemetry, action_label="Cloning")


@cli.command()
@click.argument("target")
@click.option("--dest", default=None, help="Working directory (defaults to system slug)")
@click.option("--input", "user_input", default=None, help="Input prompt or task description to pass to the system")
@click.option("--no-telemetry", is_flag=True, default=False, help="Disable anonymous usage telemetry for this command")
def run(target: str, dest: str, user_input: Optional[str] = None, no_telemetry: bool = False):
    """
    Execute or run an AI system locally.

    For Agents & Bots: Pulls codebase if not present and launches entrypoint (main.py, agent.py, npm start).
    For Prompts & Skills: Executes instructions with provided input or displays runtime directives.
    For MCP Servers: Starts in stdio mode or outputs Claude/Cursor configuration command.

    Example:
      aihub run community/astrbot
      aihub run community/stitch-skills --input "Build an obsidian dark theme navbar"
    """
    import subprocess
    import shutil

    parts = target.strip("/").split("/")
    if len(parts) >= 3:
        owner = parts[0]
        repo = parts[1]
        system_slug = parts[2]
    elif len(parts) == 2:
        owner = parts[0]
        repo = None
        system_slug = parts[1]
    else:
        owner = "community"
        repo = None
        system_slug = parts[0]

    out_dir = Path(dest) if dest else Path.cwd() / system_slug

    # 1. Ensure system is pulled locally
    if not out_dir.exists() or not (out_dir / "aistorehub.json").exists():
        click.secho(f"System '{owner}/{system_slug}' not found locally in {out_dir.name}/. Pulling bundle first...", fg="cyan")
        _do_pull_or_clone(target, str(out_dir), extract=True, no_telemetry=no_telemetry, action_label="Pulling")

    # 2. Inspect manifest & instructions
    manifest_file = out_dir / "aistorehub.json"
    manifest = {}
    if manifest_file.exists():
        try:
            import json
            manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    sys_type = manifest.get("type", "agent")
    sys_name = manifest.get("name", system_slug)

    click.echo(f"\n==============================================================================")
    click.secho(f"🚀 Executing {sys_name} ({sys_type})", bold=True, fg="green")
    click.echo(f"   Directory: {out_dir.resolve()}")
    click.echo(f"==============================================================================\n")

    # Case A: Prompts, Skills, and Templates
    if sys_type in ("prompt", "skill", "template"):
        instructions_file = out_dir / "instructions.txt"
        instructions = instructions_file.read_text(encoding="utf-8") if instructions_file.exists() else ""

        if user_input:
            click.secho("--- Executing with Prompt Directives ---", fg="cyan", bold=True)
            click.echo(f"Input Task: {user_input}\n")
            click.echo("--- System Instructions ---")
            click.echo(instructions)
            click.secho("\n✓ Directives compiled successfully. Pipe into your LLM runtime or copy above.", fg="green")
        else:
            click.secho("--- System Instructions & Directives ---", fg="cyan", bold=True)
            click.echo(instructions)
            click.echo("\nTip: Pass task input using --input:")
            click.secho(f"  aihub run {owner}/{system_slug} --input \"Your query here\"", fg="yellow")
        return

    # Case B: Model Context Protocol (MCP) Server
    if sys_type == "mcp_server":
        click.secho("• Model Context Protocol (MCP) Server detected:", bold=True)
        click.echo("  To configure into Cursor, Claude Desktop, or Windsurf:")
        click.secho(f"  aihub mcp {owner}/{system_slug}", fg="cyan", bold=True)

        entry_points = ["index.js", "index.mjs", "server.py", "main.py", "index.ts"]
        for ep in entry_points:
            ep_file = out_dir / ep
            if ep_file.exists():
                click.echo(f"\n  To run in stdio mode locally:")
                if ep.endswith(".py"):
                    click.secho(f"  cd {out_dir.name} && python {ep}", fg="green")
                else:
                    click.secho(f"  cd {out_dir.name} && node {ep}", fg="green")
                break
        return

    # Case C: Autonomous Agents, Bots, and Applications
    py_candidates = ["main.py", "agent.py", "run.py", "bot.py", "app.py", "cli.py"]
    for candidate in py_candidates:
        candidate_file = out_dir / candidate
        if candidate_file.exists():
            click.secho(f"• Launching Python entry point: {candidate}", fg="cyan", bold=True)
            if (out_dir / "requirements.txt").exists():
                click.echo(f"  Dependencies available in: {candidate_file.parent / 'requirements.txt'}")
            cmd = [sys.executable, str(candidate_file.name)]
            if user_input:
                cmd.extend(["--input", user_input])
            try:
                subprocess.run(cmd, cwd=str(out_dir))
            except KeyboardInterrupt:
                click.echo("\nExecution stopped by user.")
            except Exception as e:
                click.secho(f"Execution error: {e}", fg="red")
            return

    # Look for Node / JS entry points
    if (out_dir / "package.json").exists():
        click.secho("• Launching Node.js project...", fg="cyan", bold=True)
        npm_bin = shutil.which("npm") or "npm"
        try:
            subprocess.run([npm_bin, "start"], cwd=str(out_dir))
        except KeyboardInterrupt:
            click.echo("\nExecution stopped by user.")
        except Exception as e:
            click.secho(f"Execution error: {e}", fg="red")
        return

    # Fallback
    click.secho(f"• All project files ready in {out_dir.name}/", bold=True)
    if (out_dir / "README.md").exists():
        click.echo("  Inspect README.md for execution instructions.")
    click.echo(f"  cd {out_dir.name}")


@cli.command()
@click.argument("path", default=".")
def inspect(path: str):
    """Inspect a local folder and preview its auto-detected manifest."""
    dir_path = Path(path).resolve()
    if not dir_path.is_dir():
        click.secho(f"Error: {dir_path} is not a directory", fg="red")
        sys.exit(1)

    detected = inspect_directory(dir_path)
    click.secho(f"Auto-Detected System Specification for {dir_path.name}:", bold=True, fg="cyan")
    click.echo(f"  Name:         {detected['name']}")
    click.echo(f"  Slug:         {detected['slug']}")
    click.echo(f"  Type:         {detected['type']}")
    click.echo(f"  Version:      {detected['version']}")
    click.echo(f"  Channel:      {detected['channel']}")
    if detected.get("description"):
        click.echo(f"  Description:  {detected['description']}")
    if detected.get("instructions"):
        click.echo(f"  Instructions: {len(detected['instructions'])} characters detected")
    if detected.get("tools"):
        click.echo(f"  Tools:        {len(detected['tools'])} tools detected")
    click.secho("\nReady to publish with 'aistorehub publish'.", fg="green")


@cli.command()
@click.argument("path", default=".")
@click.option("--repo", default=None, help="Target repository slug")
@click.option("--name", default=None, help="AI system name")
@click.option("--slug", default=None, help="AI system slug")
@click.option("--type", "system_type", default=None, help="System type (prompt, skill, agent, workflow, mcp_server, etc.)")
@click.option("--version", "version_str", default="1.0.0", help="System version (default: 1.0.0)")
@click.option("--description", default=None, help="System description")
@click.option("--commercial-model", default="free", type=click.Choice(["free", "one_time", "subscription"]), help="Commercial model")
@click.option("--price", default=0.0, type=float, help="Price in USD (if paid)")
def publish(path: str, repo: str, name: str, slug: str, system_type: str, version_str: str, description: str, commercial_model: str, price: float):
    """
    Bundle, scan, and publish an AI system from a local directory to AIStoreHub.
    Example: aistorehub publish . --type agent
    """
    import tempfile

    api = APIClient()
    token = get_token()
    if not token:
        click.secho("Not logged in. Please run 'aistorehub login' first.", fg="yellow")
        sys.exit(1)

    try:
        user = api.whoami()
        username = user.get("username", "developer")
    except Exception as e:
        click.secho(f"Authentication failed: {e}. Please run 'aistorehub login'.", fg="red")
        sys.exit(1)

    dir_path = Path(path).resolve()
    if not dir_path.is_dir():
        click.secho(f"Error: {dir_path} is not a directory.", fg="red")
        sys.exit(1)

    click.secho(f"Inspecting package in {dir_path.name}...", fg="cyan")
    detected = inspect_directory(dir_path)

    sys_name = name or detected.get("name") or dir_path.name.replace("-", " ").replace("_", " ").title()
    sys_slug = slug or detected.get("slug") or dir_path.name.lower().replace(" ", "-")
    sys_type = system_type or detected.get("type") or "prompt"
    sys_desc = description or detected.get("description") or f"{sys_name} - AI system published via AIStoreHub CLI"
    instructions = detected.get("instructions") or ""
    readme = detected.get("readme") or f"# {sys_name}\n\n{sys_desc}"

    # 1. Create temporary zip bundle
    click.echo("Creating package archive...")
    temp_zip = Path(tempfile.mktemp(suffix=".zip"))
    try:
        create_bundle_zip(dir_path, temp_zip)
        zip_size_kb = temp_zip.stat().st_size / 1024
        click.secho(f"✓ Archive created: {sys_slug}.zip ({zip_size_kb:.1f} KB)", fg="green")

        # 2. Upload through static quarantine & security scanner
        click.echo("Uploading through security & quarantine gate...")
        upload_resp = api.upload_artifact(temp_zip, filename=f"{sys_slug}.zip")
        storage_key = upload_resp.get("storage_key")
        sha256 = upload_resp.get("checksum_sha256", "")
        click.secho(f"✓ Security scan passed (SHA-256: {sha256[:12]}...)", fg="green")
    finally:
        if temp_zip.exists():
            try:
                temp_zip.unlink()
            except Exception:
                pass

    # 3. Resolve repository
    repo_id = None
    repo_slug = repo or "systems"
    try:
        repos = api.get_user_repos()
        matching_repo = next((r for r in repos if r.get("slug") == repo_slug), None)
        if matching_repo:
            repo_id = matching_repo.get("id")
    except Exception:
        pass

    # 4. Check if system already exists
    existing_sys = None
    try:
        existing_sys = api.get_system(owner=username, system_slug=sys_slug)
    except Exception:
        existing_sys = None

    artifact_item = {
        "kind": "package",
        "name": f"{sys_slug}.zip",
        "storage_key": storage_key,
        "mime_type": "application/zip",
        "checksum_sha256": sha256,
        "is_primary": True,
        "access_level": "public" if commercial_model == "free" else "entitled",
    }

    sample_example = {
        "title": f"Run {sys_name}",
        "input_text": "Sample task input",
        "output_text": "Sample expected output",
    }

    version_payload = {
        "version": version_str,
        "readme": readme,
        "instructions": instructions,
        "artifacts": [artifact_item],
        "examples": [sample_example],
    }

    if existing_sys and existing_sys.get("id"):
        # Add new version to existing system
        sys_id = existing_sys["id"]
        click.echo(f"System @{username}/{sys_slug} already exists. Publishing version {version_str}...")
        try:
            api.add_version(sys_id, version_payload)
            click.secho(f"\n✓ Successfully published new version {version_str} for {username}/{sys_slug}!", fg="green", bold=True)
        except Exception as e:
            click.secho(f"Publish version failed: {e}", fg="red")
            sys.exit(1)
    else:
        # Create brand new system
        click.echo(f"Registering new AI system '{sys_name}' [{sys_type}]...")
        system_payload = {
            "name": sys_name,
            "slug": sys_slug,
            "type": sys_type,
            "description": sys_desc,
            "visibility": "public",
            "request_public_approval": True,
            "version": version_payload,
            "distribution_offers": [
                {
                    "name": f"{sys_name} Package",
                    "channel": "mcp" if sys_type == "mcp_server" else "source",
                    "commercial_model": commercial_model,
                    "price_amount": price,
                    "currency": "USD",
                    "is_primary": True,
                }
            ],
        }
        if repo_id:
            system_payload["repository_id"] = repo_id

        try:
            created = api.create_system(system_payload)
            click.secho(f"\n✓ Successfully published {username}/{sys_slug} (v{version_str})!", fg="green", bold=True)
        except Exception as e:
            click.secho(f"Publish failed: {e}", fg="red")
            sys.exit(1)

    click.echo("\n--- Next Steps ---")
    click.echo(f"• Discover and view on AIStoreHub:")
    click.secho(f"  https://aistorehub.in/{username}/{repo_slug}/{sys_slug}", fg="cyan", bold=True)
    click.echo(f"• Pull and verify anywhere with:")
    click.secho(f"  aistorehub pull {username}/{sys_slug}", fg="cyan")
    click.echo("------------------")


@cli.command()
@click.argument("action", default="status", type=click.Choice(["status", "enable", "disable"]))
def telemetry(action: str):
    """
    View or toggle anonymous CLI usage telemetry (pull counts).
    Never collects credentials, arguments, code, or local file paths.
    """
    from .config import is_telemetry_enabled, set_telemetry

    if action == "enable":
        set_telemetry(True)
        click.secho("✓ Usage telemetry enabled. Thank you for supporting open-source distribution metrics!", fg="green")
    elif action == "disable":
        set_telemetry(False)
        click.secho("✓ Usage telemetry disabled. No event data will be transmitted by the CLI.", fg="yellow")
    else:
        active = is_telemetry_enabled()
        status_label = "ENABLED" if active else "DISABLED"
        color = "green" if active else "yellow"
        click.echo("---")
        click.secho(f"AIStoreHub Telemetry: {status_label}", fg=color, bold=True)
        click.echo("Data collected: Anonymous event name & system ID on pull/mcp.")
        click.echo("Data excluded:  NO credentials, arguments, file paths, or private data.")
        click.echo("Opt out:        'aihub telemetry disable', set DO_NOT_TRACK=1, or use --no-telemetry")
        click.echo("---")


if __name__ == "__main__":
    cli()
