from __future__ import annotations

import fnmatch
from pathlib import Path

DEFAULT_IGNORED_PATTERNS = [
    # Version control
    ".git",
    ".git/**",
    ".svn",
    ".hg",
    # OS & Editor
    ".DS_Store",
    "Thumbs.db",
    ".idea",
    ".idea/**",
    ".vscode",
    ".vscode/**",
    # Environments & caches
    ".venv",
    ".venv/**",
    "venv",
    "venv/**",
    "env",
    "env/**",
    "__pycache__",
    "__pycache__/**",
    "*.pyc",
    "*.pyo",
    ".pytest_cache",
    ".pytest_cache/**",
    "node_modules",
    "node_modules/**",
    ".next",
    ".next/**",
    "dist",
    "dist/**",
    "build",
    "build/**",
    "coverage",
    "coverage/**",
    ".tox",
    "*.egg-info",
    "*.egg-info/**",
    # Secrets & credentials (except .env.example)
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    ".env.*",
    "credentials.json",
    "service-account*.json",
    "*.pem",
    "*.key",
    "id_rsa*",
    "id_ed25519*",
    # Archive outputs
    "*.zip",
    "*.tar.gz",
]


class IgnoreMatcher:
    """
    Parses and matches file paths against .aihubignore, .gitignore,
    and built-in AIStoreHub safety ignore rules.
    """

    def __init__(
        self,
        base_dir: Path | str | None = None,
        extra_patterns: list[str] | None = None,
    ) -> None:
        self.rules: list[tuple[bool, str]] = []  # (is_negated, pattern)

        # 1. Base default safety rules
        for pat in DEFAULT_IGNORED_PATTERNS:
            self._add_rule(pat)

        # 2. .gitignore (if present)
        if base_dir:
            p = Path(base_dir)
            gitignore = p / ".gitignore"
            if gitignore.is_file():
                self.load_file(gitignore)

            # 3. .aihubignore (highest priority file)
            aihubignore = p / ".aihubignore"
            if aihubignore.is_file():
                self.load_file(aihubignore)

        # 4. Extra runtime patterns
        if extra_patterns:
            for pat in extra_patterns:
                self._add_rule(pat)

    def load_file(self, file_path: Path) -> None:
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            for line in content.splitlines():
                self._add_rule(line)
        except Exception:
            pass

    def load_text(self, text: str) -> None:
        for line in text.splitlines():
            self._add_rule(line)

    def _add_rule(self, raw_line: str) -> None:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            return
        is_negated = False
        if line.startswith("!"):
            is_negated = True
            line = line[1:].strip()

        clean_pat = line.replace("\\", "/").strip()
        if clean_pat.startswith("./"):
            clean_pat = clean_pat[2:]
        if clean_pat.startswith("/") and not clean_pat.startswith("//"):
            clean_pat = clean_pat[1:]

        self.rules.append((is_negated, clean_pat))

    def is_ignored(self, rel_path: str, is_dir: bool = False) -> bool:
        norm_path = rel_path.replace("\\", "/").strip("/")

        # Whitelist exception: always allow .env.example
        if norm_path == ".env.example" or norm_path.endswith("/.env.example"):
            return False

        # Never ignore the manifest files themselves
        file_name = norm_path.split("/")[-1]
        if file_name in ("aistorehub.json", "manifest.json", "manifest.yaml", "manifest.yml", "README.md", "readme.md"):
            return False

        ignored = False
        for is_negated, pat in self.rules:
            # Trailing slash matches directories only
            if pat.endswith("/"):
                pat_dir = pat.rstrip("/")
                if not is_dir and not norm_path.startswith(f"{pat_dir}/") and norm_path != pat_dir:
                    continue
                match = (
                    fnmatch.fnmatch(norm_path, pat_dir)
                    or norm_path.startswith(f"{pat_dir}/")
                    or fnmatch.fnmatch(norm_path, f"*/{pat_dir}")
                    or fnmatch.fnmatch(norm_path, f"*/{pat_dir}/*")
                )
            else:
                match = (
                    fnmatch.fnmatch(norm_path, pat)
                    or fnmatch.fnmatch(file_name, pat)
                    or fnmatch.fnmatch(norm_path, f"*/{pat}")
                    or fnmatch.fnmatch(norm_path, f"{pat}/*")
                    or fnmatch.fnmatch(norm_path, f"*/{pat}/*")
                )

            if match:
                ignored = not is_negated

        return ignored
