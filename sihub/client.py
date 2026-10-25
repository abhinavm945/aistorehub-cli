from pathlib import Path
from typing import Any, Dict, List, Optional
import httpx
from .config import get_config, get_token


class APIClient:
    def __init__(self, base_url: Optional[str] = None):
        cfg = get_config()
        self.base_url = (base_url or cfg.get("api_url") or "http://localhost:8000/api/v1").rstrip("/")
        self.token = get_token()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Accept": "application/json",
            "User-Agent": "aistorehub-cli/0.1.4",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def log_event(self, event_name: str, system_id: Optional[str] = None, entity_type: str = "system") -> None:
        """
        Fire-and-forget minimal telemetry event logger (records anonymous event_name and system_id only).
        Respects DO_NOT_TRACK=1, AISTOREHUB_TELEMETRY_DISABLED=1, and `aihub telemetry disable`.
        Never transmits credentials, command arguments, local file paths, or private data.
        """
        from .config import is_telemetry_enabled
        if not is_telemetry_enabled():
            return
        try:
            with httpx.Client(timeout=2.0) as client:
                client.post(
                    f"{self.base_url}/marketplace/events",
                    json={
                        "event_name": event_name,
                        "entity_type": entity_type,
                        "entity_id": system_id or "",
                    },
                    headers=self._headers(),
                )
        except Exception:
            pass

    def whoami(self) -> Dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{self.base_url}/users/me", headers=self._headers())
            if resp.status_code == 401:
                raise Exception("Not authenticated. Please run 'aistorehub login'.")
            resp.raise_for_status()
            return resp.json()

    def search(self, query: str = "", limit: int = 15) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(
                f"{self.base_url}/search",
                params={"q": query, "limit": limit},
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json().get("items", [])

    def get_system(self, owner: str, system_slug: str, repo: Optional[str] = None) -> Dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            # 1. If explicit repo provided, fetch direct endpoint
            if repo:
                resp = client.get(
                    f"{self.base_url}/systems/{owner}/{repo}/{system_slug}",
                    headers=self._headers(),
                )
                if resp.status_code == 200:
                    return resp.json()

            # 2. Try owner/system_slug/system_slug
            resp = client.get(
                f"{self.base_url}/systems/{owner}/{system_slug}/{system_slug}",
                headers=self._headers(),
            )
            if resp.status_code == 200:
                return resp.json()

            # 3. Resolve via search catalog
            search_resp = client.get(
                f"{self.base_url}/search",
                params={"q": system_slug, "limit": 10},
                headers=self._headers(),
            )
            if search_resp.status_code == 200:
                items = search_resp.json().get("items", [])
                for it in items:
                    if (
                        it.get("slug") == system_slug
                        or it.get("name", "").lower() == system_slug.lower()
                    ):
                        o = it.get("owner_username") or owner
                        r = it.get("repository_slug") or "catalog"
                        s = it.get("slug") or system_slug
                        detail_resp = client.get(
                            f"{self.base_url}/systems/{o}/{r}/{s}",
                            headers=self._headers(),
                        )
                        if detail_resp.status_code == 200:
                            return detail_resp.json()
                        return it

            resp.raise_for_status()
            return resp.json()

    def download_artifact(self, artifact_id: str) -> bytes:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(
                f"{self.base_url}/marketplace/artifacts/{artifact_id}/download",
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                try:
                    err_detail = resp.json().get("detail", resp.text)
                except Exception:
                    err_detail = resp.text
                raise Exception(f"Download failed ({resp.status_code}): {err_detail}")
            return resp.content

    def upload_artifact(self, file_path: Path, filename: Optional[str] = None) -> Dict[str, Any]:
        fname = filename or file_path.name
        content_type = "application/zip" if fname.endswith(".zip") else "application/octet-stream"
        with open(file_path, "rb") as f:
            files = {"file": (fname, f, content_type)}
            with httpx.Client(timeout=120.0) as client:
                resp = client.post(
                    f"{self.base_url}/uploads/artifact",
                    files=files,
                    headers=self._headers(),
                )
                if resp.status_code >= 400:
                    try:
                        err_detail = resp.json().get("detail", resp.text)
                    except Exception:
                        err_detail = resp.text
                    raise Exception(f"Upload failed ({resp.status_code}): {err_detail}")
                return resp.json()

    def create_system(self, data: Dict[str, Any]) -> Dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}/systems",
                json=data,
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                try:
                    err_detail = resp.json().get("detail", resp.text)
                except Exception:
                    err_detail = resp.text
                raise Exception(f"System creation failed ({resp.status_code}): {err_detail}")
            return resp.json()

    def add_version(self, system_id: str, version_data: Dict[str, Any]) -> Dict[str, Any]:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                f"{self.base_url}/systems/id/{system_id}/versions",
                json=version_data,
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                try:
                    err_detail = resp.json().get("detail", resp.text)
                except Exception:
                    err_detail = resp.text
                raise Exception(f"Adding version failed ({resp.status_code}): {err_detail}")
            return resp.json()

    def get_user_repos(self) -> List[Dict[str, Any]]:
        with httpx.Client(timeout=15.0) as client:
            resp = client.get(
                f"{self.base_url}/repos",
                headers=self._headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def create_repository(self, name: str, slug: Optional[str] = None, description: Optional[str] = None) -> Dict[str, Any]:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(
                f"{self.base_url}/repos",
                json={
                    "name": name,
                    "slug": slug or name.lower().replace(" ", "-"),
                    "description": description or f"Repository for {name}",
                    "visibility": "public",
                },
                headers=self._headers(),
            )
            if resp.status_code >= 400:
                try:
                    err_detail = resp.json().get("detail", resp.text)
                except Exception:
                    err_detail = resp.text
                raise Exception(f"Repository creation failed ({resp.status_code}): {err_detail}")
            return resp.json()
