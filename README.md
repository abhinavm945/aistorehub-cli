# AIStoreHub CLI (`aistorehub` / `aihub`)

[![PyPI Version](https://img.shields.io/pypi/v/aistorehub.svg)](https://pypi.org/project/aistorehub/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python: 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)

The official command-line interface for **[AIStoreHub](https://aistorehub.in)** — the open registry and marketplace for autonomous AI systems, model instructions, agent workflows, and Model Context Protocol (MCP) servers.

---

## ⚡ Quick Install

```bash
pip install aistorehub
```

> **Tip:** Both `aistorehub` and `aihub` commands are installed. You can also invoke the CLI directly anywhere with `python -m aihub` or `python -m aistorehub`!

---

## 🚀 Key Features

* **1-Click MCP Auto-Configuration**: Automatically injects MCP server configs into **Claude Desktop**, **Cursor IDE**, and **Windsurf** with automatic timestamped `.bak` safety backups.
* **Instant Artifact Pull**: Download prompts, schemas, instructions, and test datasets straight into your current directory with verified distribution telemetry.
* **Interactive Terminal Search**: Query AI systems, agents, and verified benchmarks without leaving your terminal.
* **Provenance & Metadata Inspection**: View upstream repository sources, licensing, and maintainer verification status before pulling.
* **10-Second Manifest Inspector**: Inspect local folders to auto-detect system prompts, tool schemas, and capabilities before publishing.
* **Team & Organization RBAC**: Switch between personal workspaces and enterprise multi-tenant organizations seamlessly.

---

## 📖 Command Reference

### 1. Authenticate (1-Click Browser Login & CI)
```bash
# 1-Click browser authorization with OAuth PKCE (RFC 7636 / RFC 8252):
aihub login

# CI/CD & Automation: Pipe token via standard input (avoids shell history & ps exposure):
echo $AISTOREHUB_TOKEN | aihub login --token-stdin

# Interactive terminal login with hidden prompt:
aihub login --interactive

# Inspect current authenticated user:
aihub whoami

# Log out and purge stored credentials:
aihub logout
```

> **🔒 Credential Storage at Rest**: The CLI automatically secures your Personal Access Token in your operating system's native credential vault (**Windows Credential Manager**, **macOS Keychain**, or **Linux Secret Service**) via `keyring`. In headless Linux / container environments without an active secret service daemon, credentials fall back to a dedicated `~/.aistorehub/credentials.json` file locked with restrictive POSIX permissions (`0o600`, owner-only read/write). Plaintext tokens are never written to general configuration files.

### 2. Search Systems & Agents
```bash
# Search by keyword, problem, or capability:
aihub search "sql optimizer"
aihub search "mcp-server-postgres"
```

### 3. Inspect System Metadata & Provenance
```bash
# Check version, license, upstream repo, and quickstart instructions:
aihub info mcp-server-postgres
```

### 4. Pull System Instructions & Code
```bash
# Pull into current directory:
aihub pull community/mcp-server-postgres

# Pull into a custom destination folder:
aihub pull community/mcp-server-postgres --dest ./my-tools
```

### 5. 1-Click MCP Server Installation
```bash
# Auto-configure into Claude Desktop and Cursor simultaneously:
aihub mcp community/mcp-server-postgres

# Or target a specific client:
aihub mcp community/mcp-server-postgres --client claude
aihub mcp community/mcp-server-postgres --client cursor
aihub mcp community/mcp-server-postgres --client windsurf
```

### 6. Inspect Local Folders for Publishing
```bash
# Auto-detect manifests, tools, prompts, and view filtered files:
aihub inspect ./my-agent-folder
```

### 7. Package & Publish with `.aihubignore` & `.gitignore`
```bash
# Package, quarantine scan, and publish an AI system:
aihub publish ./my-agent-folder --type agent
```

#### 🛡️ Smart File Exclusion & Security Rules
When inspecting or packaging a system (`aihub inspect` / `aihub publish`), the CLI automatically filters out sensitive credentials, temporary environments, and bulky build outputs before creating the release bundle:
1. **`.aihubignore` (Highest Priority)**: Define custom patterns specifically for your AIStoreHub release. Rules here override `.gitignore` and default rules (supports standard globbing, directory slashes `dir/`, and `!negation`).
2. **`.gitignore` (Standard Fallback)**: Standard git repository exclusions are respected automatically.
3. **Default Safety Exclusions**: Always filters `.env*`, `.venv/`, `node_modules/`, `__pycache__/`, `.git/`, `credentials.json`, `*.pem`, `*.key`, `id_rsa*`, etc.
4. **Guaranteed Whitelist Protection**: Critical metadata and documentation files are **never ignored** (`.env.example`, `manifest.json`, `aistorehub.json`, `README.md`).

---

## ⚙️ Environment Variables

You can optionally configure authentication, custom endpoints, and telemetry via environment variables:

* `AISTOREHUB_TOKEN` or `AIHUB_TOKEN`: Personal Access Token (PAT).
* `AISTOREHUB_API_URL` or `AIHUB_API_URL`: Custom API endpoint (default: `https://aistorehub-be.onrender.com/api/v1`).
* `DO_NOT_TRACK=1`, `AISTOREHUB_TELEMETRY_DISABLED=1`, or `AISTOREHUB_TELEMETRY=0`: Disables anonymous CLI usage telemetry.

---

## 🔒 Telemetry & Privacy (Transparent, Pseudonymous & Opt-outable)

AIStoreHub CLI records minimal, client-reported activity events (`pull_succeeded` and `mcp_configured`) to help community open-source maintainers evaluate discovery and distribution interest for their AI systems.

* **What the CLI sends**: Event name, target system ID, and CLI client version.
* **What is NEVER collected**: Passwords, Personal Access Tokens (PATs), shell commands, arguments, local file paths, directory contents, or private code.
* **Server-side Network Metadata & Retention**:
  * On ingestion, the backend derives a one-way 32-character SHA-256 hash of the incoming IP address (`ip_hash`) solely to enforce sliding-window duplicate suppression (120-second debounce) and protect against metric inflation.
  * Raw client IP addresses are discarded in-memory and are never written to application database tables or persistent application records. (Standard ephemeral cloud infrastructure ingress logs on hosting providers like Render remain subject to infrastructure provider retention policies).
  * Because deterministic cryptographic hashes are technically classified as pseudonymous identifiers (potentially linkable in fixed-IP environments), we provide full user-controlled opt-outs.
* **Complete Opt-Out Controls (Supported in Code)**:
  * **Per-Command Flag**: Pass `--no-telemetry` on any command (`aihub pull <target> --no-telemetry` or `aihub mcp <target> --no-telemetry`).
  * **Persistent Config**: Run `aihub telemetry disable` (persists `telemetry: false` in `~/.aistorehub/config.json`). Re-enable anytime with `aihub telemetry enable`.
  * **Environment Variables**: Export `DO_NOT_TRACK=1`, `AISTOREHUB_TELEMETRY_DISABLED=1`, or `AISTOREHUB_TELEMETRY=0` in your shell profile.
  * **Inspect Status**: Run `aihub telemetry status` anytime to see whether telemetry is currently active or disabled.
  * **Opt-Out Scope**: When telemetry is disabled via any of the above mechanisms, the CLI client suppresses all event reporting logic—zero network calls are dispatched to telemetry endpoints.

---

## 📚 Resources & Documentation

* **Marketplace & Catalog**: [https://aistorehub.in](https://aistorehub.in)
* **CLI Reference**: [https://aistorehub.in/cli](https://aistorehub.in/cli)
* **Full Documentation**: [https://aistorehub.in/docs](https://aistorehub.in/docs)

---

## 📄 License

MIT © [AIStoreHub Team](https://aistorehub.in)
