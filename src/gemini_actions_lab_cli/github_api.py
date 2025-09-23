"""Helpers for interacting with the GitHub REST API."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any, Dict, Mapping, Optional

import requests
from nacl import encoding, public

API_URL = "https://api.github.com"
USER_AGENT = "gemini-actions-lab-cli/0.1.0"


class GitHubError(RuntimeError):
    """Raised when the GitHub API returns an unexpected response."""


@dataclass(slots=True)
class GitHubClient:
    """Small wrapper around the GitHub REST API."""

    token: Optional[str] = None
    api_url: str = API_URL

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def _request(self, method: str, url: str, **kwargs: Any) -> requests.Response:
        response = requests.request(method, url, headers=self._headers(), timeout=30, **kwargs)
        if response.status_code >= 400:
            raise GitHubError(
                f"GitHub API error {response.status_code}: {response.text.strip()}"
            )
        return response

    def get_actions_public_key(self, owner: str, repo: str) -> Mapping[str, str]:
        url = f"{self.api_url}/repos/{owner}/{repo}/actions/secrets/public-key"
        response = self._request("GET", url)
        data = response.json()
        if not {"key", "key_id"} <= data.keys():
            raise GitHubError("Unexpected response payload when fetching repository key")
        return {"key": data["key"], "key_id": data["key_id"]}

    def put_actions_secret(
        self,
        owner: str,
        repo: str,
        secret_name: str,
        encrypted_value: str,
        key_id: str,
    ) -> None:
        url = f"{self.api_url}/repos/{owner}/{repo}/actions/secrets/{secret_name}"
        payload = {"encrypted_value": encrypted_value, "key_id": key_id}
        self._request("PUT", url, json=payload)

    def download_repository_archive(self, owner: str, repo: str, ref: Optional[str] = None) -> bytes:
        ref_part = f"/{ref}" if ref else ""
        url = f"{self.api_url}/repos/{owner}/{repo}/zipball{ref_part}"
        response = self._request("GET", url, stream=True)
        buffer = io.BytesIO()
        for chunk in response.iter_content(chunk_size=65536):
            buffer.write(chunk)
        return buffer.getvalue()


def encrypt_secret(public_key: str, value: str) -> str:
    """Encrypt ``value`` using the repository ``public_key``."""

    key = public.PublicKey(public_key.encode("utf-8"), encoding.Base64Encoder())
    sealed_box = public.SealedBox(key)
    encrypted = sealed_box.encrypt(value.encode("utf-8"))
    return base64.b64encode(encrypted).decode("utf-8")


def parse_repo(repo: str) -> tuple[str, str]:
    """Split ``owner/repo`` notation into a tuple."""

    if "/" not in repo:
        raise ValueError("Repository must be in the format 'owner/name'")
    owner, name = repo.split("/", 1)
    if not owner or not name:
        raise ValueError("Both owner and repository name are required")
    return owner, name
