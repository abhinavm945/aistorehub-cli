import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import zipfile


def inspect_directory(dir_path: Path) -> Dict[str, Any]:
    """
    Auto-detects manifest properties, prompts, instructions, and tools from a directory.
    """
    detected: Dict[str, Any] = {
        "name": dir_path.name.replace("-", " ").replace("_", " ").title(),
        "slug": dir_path.name.lower().replace(" ", "-"),
        "description": "",
        "type": "prompt",
        "instructions": "",
        "version": "1.0.0",
        "tools": [],
        "variables": [],
        "channel": "source",
        "endpoint_url": None,
    }

    # 0. Check explicit aistorehub.json manifest
    manifest_file = dir_path / "aistorehub.json"
    if manifest_file.is_file():
        try:
            m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            for k in ("name", "slug", "description", "type", "version", "channel"):
                if k in m_data and m_data[k]:
                    detected[k] = m_data[k]
        except Exception:
            pass

    # 1. Check README.md
    readme_file = next((f for f in dir_path.iterdir() if f.is_file() and f.name.lower() in ("readme.md", "readme.txt")), None)
    if readme_file:
        try:
            content = readme_file.read_text(encoding="utf-8")
            detected["readme"] = content
            lines = [l.strip() for l in content.splitlines() if l.strip()]
            if lines:
                # First heading
                for l in lines:
                    if l.startswith("# "):
                        detected["name"] = l.lstrip("# ").strip()
                        break
                # First paragraph as description
                for l in lines:
                    if not l.startswith("#") and len(l) > 10:
                        detected["description"] = l[:240]
                        break
        except Exception:
            pass

    # 2. Check MCP Manifest: mcp.json / server.json
    mcp_file = next((f for f in dir_path.iterdir() if f.is_file() and f.name.lower() in ("mcp.json", "server.json")), None)
    if mcp_file:
        try:
            mcp_data = json.loads(mcp_file.read_text(encoding="utf-8"))
            detected["type"] = "mcp_server"
            detected["channel"] = "mcp"
            if "name" in mcp_data:
                detected["name"] = mcp_data["name"]
            if "description" in mcp_data:
                detected["description"] = mcp_data["description"]
            if "tools" in mcp_data and isinstance(mcp_data["tools"], list):
                detected["tools"] = mcp_data["tools"]
            if "endpoint" in mcp_data or "url" in mcp_data:
                detected["endpoint_url"] = mcp_data.get("endpoint") or mcp_data.get("url")
        except Exception:
            pass

    # 3. Check Workflow Manifest: workflow.json / n8n.json / flow.json
    workflow_file = next((f for f in dir_path.iterdir() if f.is_file() and f.name.lower() in ("workflow.json", "n8n.json", "flow.json")), None)
    if workflow_file:
        try:
            wf_data = json.loads(workflow_file.read_text(encoding="utf-8"))
            detected["type"] = "workflow"
            if "name" in wf_data and wf_data["name"]:
                detected["name"] = wf_data["name"]
        except Exception:
            pass

    # 4. Check Skill Manifest: skill.md / skill.yaml
    skill_file = next((f for f in dir_path.iterdir() if f.is_file() and f.name.lower() in ("skill.md", "skill.yaml")), None)
    if skill_file:
        detected["type"] = "skill"

    # 5. Check package.json
    pkg_file = dir_path / "package.json"
    if pkg_file.is_file():
        try:
            pkg_data = json.loads(pkg_file.read_text(encoding="utf-8"))
            if "name" in pkg_data:
                detected["name"] = pkg_data["name"].split("/")[-1].replace("-", " ").title()
                detected["slug"] = pkg_data["name"].split("/")[-1].lower()
            if "version" in pkg_data:
                detected["version"] = pkg_data["version"]
            if "description" in pkg_data:
                detected["description"] = pkg_data["description"]
        except Exception:
            pass

    # 6. Check prompt or instructions files
    for candidate in ("instructions.txt", "instructions.md", "system_prompt.txt", "prompt.txt", "agent.py", "main.py"):
        p_file = dir_path / candidate
        if p_file.is_file():
            try:
                text = p_file.read_text(encoding="utf-8")
                detected["instructions"] = text[:5000]
                if not detected["type"] or detected["type"] == "prompt":
                    detected["type"] = "agent" if candidate in ("agent.py", "main.py") else "prompt"
                break
            except Exception:
                pass

    return detected


from sihub.ignore_matcher import IgnoreMatcher


def create_bundle_zip(dir_path: Path, output_zip: Path) -> Path:
    """
    Creates a zip bundle of the directory excluding files specified in
    .aihubignore, .gitignore, and built-in AIStoreHub safety rules.
    """
    matcher = IgnoreMatcher(base_dir=dir_path)

    with zipfile.ZipFile(output_zip, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(dir_path):
            rel_root = Path(root).relative_to(dir_path).as_posix()
            # Filter subdirectories in-place
            dirs[:] = [
                d
                for d in dirs
                if not matcher.is_ignored(f"{rel_root}/{d}" if rel_root != "." else d, is_dir=True)
            ]
            for file in files:
                file_path = Path(root) / file
                if file_path.resolve() == output_zip.resolve():
                    continue
                rel_path = file_path.relative_to(dir_path).as_posix()
                if matcher.is_ignored(rel_path, is_dir=False):
                    continue
                zipf.write(file_path, rel_path)
    return output_zip
