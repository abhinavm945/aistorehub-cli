import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

try:
    import keyring
except ImportError:
    keyring = None

DEFAULT_API_URL = (
    os.environ.get("AISTOREHUB_API_URL")
    or os.environ.get("AIHUB_API_URL")
    or os.environ.get("SIHUB_API_URL")
    or "https://aistorehub-be.onrender.com/api/v1"
)
CONFIG_DIR = Path.home() / ".aistorehub"
LEGACY_CONFIG_DIR = Path.home() / ".sihub"
CONFIG_FILE = CONFIG_DIR / "config.json"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"
LEGACY_CONFIG_FILE = LEGACY_CONFIG_DIR / "config.json"

KEYRING_SERVICE = "aistorehub"
KEYRING_USERNAME = "default"


def _set_restrictive_permissions(file_path: Path) -> None:
    """Apply restrictive permissions (0o600 on POSIX: owner read/write only)."""
    try:
        if os.name == "posix":
            os.chmod(file_path, 0o600)
    except Exception:
        pass


def _store_token_securely(token: str) -> None:
    """
    Store token at rest using OS credential vault (Windows Credential Manager,
    macOS Keychain, Linux Secret Service). If unavailable, fall back to a
    dedicated credentials file with restrictive permissions (0o600).
    """
    stored_in_keyring = False
    if keyring is not None:
        try:
            keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME, token)
            stored_in_keyring = True
        except Exception:
            stored_in_keyring = False

    if not stored_in_keyring:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            if os.name == "posix":
                os.chmod(CONFIG_DIR, 0o700)
        except Exception:
            pass

        with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
            json.dump({"token": token}, f, indent=2)
        _set_restrictive_permissions(CREDENTIALS_FILE)


def _retrieve_token_securely() -> Optional[str]:
    """Retrieve token from OS credential vault or restrictive credentials file."""
    # 1. Check OS Keyring
    if keyring is not None:
        try:
            val = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME)
            if val:
                return val.strip()
        except Exception:
            pass

    # 2. Check dedicated credentials.json file
    if CREDENTIALS_FILE.exists():
        try:
            with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                val = data.get("token")
                if val:
                    return val.strip()
        except Exception:
            pass

    # 3. Legacy migration: if token was stored in config.json, migrate it to secure storage
    cfg = get_config()
    legacy_token = cfg.get("token")
    if legacy_token:
        try:
            _store_token_securely(legacy_token)
            cfg["token"] = None
            save_config(cfg)
        except Exception:
            pass
        return legacy_token.strip()

    return None


def _delete_token_securely() -> None:
    """Remove token from OS credential vault and credentials file."""
    if keyring is not None:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_USERNAME)
        except Exception:
            pass

    if CREDENTIALS_FILE.exists():
        try:
            CREDENTIALS_FILE.unlink()
        except Exception:
            pass

    cfg = get_config()
    cfg["token"] = None
    cfg["user"] = None
    save_config(cfg)


def get_config() -> Dict[str, Any]:
    file_to_read = CONFIG_FILE if CONFIG_FILE.exists() else (LEGACY_CONFIG_FILE if LEGACY_CONFIG_FILE.exists() else None)
    if not file_to_read:
        return {"api_url": DEFAULT_API_URL, "user": None}
    try:
        with open(file_to_read, "r", encoding="utf-8") as f:
            data = json.load(f)
            if "api_url" not in data:
                data["api_url"] = DEFAULT_API_URL
            return data
    except Exception:
        return {"api_url": DEFAULT_API_URL, "user": None}


def save_config(config_data: Dict[str, Any]) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config_data, f, indent=2)


def get_token() -> Optional[str]:
    # 1. Environment variable has highest precedence (for CI/CD pipelines & automation)
    env_token = os.environ.get("AISTOREHUB_TOKEN") or os.environ.get("AIHUB_TOKEN") or os.environ.get("SIHUB_TOKEN")
    if env_token:
        return env_token.strip()

    # 2. Retrieve from OS Credential Manager / secure credentials store
    return _retrieve_token_securely()


def set_token(token: str, user_info: Optional[Dict[str, Any]] = None) -> None:
    # Save token in secure OS vault / restricted file
    _store_token_securely(token)

    # Save non-sensitive metadata (public profile) in config.json
    cfg = get_config()
    cfg["token"] = None  # Plaintext token is never persisted in config.json
    if user_info:
        cfg["user"] = user_info
    save_config(cfg)


def clear_auth() -> None:
    _delete_token_securely()


def is_telemetry_enabled() -> bool:
    # 1. Standard cross-tool opt-out
    if os.environ.get("DO_NOT_TRACK") == "1":
        return False
    # 2. AIStoreHub-specific opt-out flags
    if os.environ.get("AISTOREHUB_TELEMETRY_DISABLED") in ("1", "true", "True"):
        return False
    if os.environ.get("AIHUB_TELEMETRY_DISABLED") in ("1", "true", "True"):
        return False
    if os.environ.get("AISTOREHUB_TELEMETRY") in ("0", "false", "False"):
        return False
    if os.environ.get("AIHUB_TELEMETRY") in ("0", "false", "False"):
        return False
    # 3. Local persisted config (~/.aistorehub/config.json)
    cfg = get_config()
    return cfg.get("telemetry", True) is not False


def set_telemetry(enabled: bool) -> None:
    cfg = get_config()
    cfg["telemetry"] = bool(enabled)
    save_config(cfg)
