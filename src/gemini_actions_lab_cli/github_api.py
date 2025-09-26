"""Helpers for interacting with the GitHub REST API."""

from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

import requests
from nacl import encoding, public

API_URL = "https://api.github.com"
USER_AGENT = "gemini-actions-lab-cli/0.1.0"


class GitHubError(RuntimeError):
    """Raised when the GitHub API returns an unexpected response."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


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
                f"GitHub API error {response.status_code}: {response.text.strip()}",
                status=response.status_code,
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

    def get_repository(self, owner: str, repo: str) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}"
        return self._request("GET", url).json()

    def get_default_branch(self, owner: str, repo: str) -> str:
        repo_info = self.get_repository(owner, repo)
        default_branch = repo_info.get("default_branch")
        if not default_branch:
            raise GitHubError("Unable to determine the default branch for the repository")
        return default_branch

    def get_ref(self, owner: str, repo: str, ref: str) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}/git/ref/{ref}"
        return self._request("GET", url).json()

    def get_git_commit(self, owner: str, repo: str, sha: str) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}/git/commits/{sha}"
        return self._request("GET", url).json()

    def get_tree(self, owner: str, repo: str, sha: str, recursive: bool = False) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}/git/trees/{sha}"
        params = {"recursive": "1"} if recursive else None
        return self._request("GET", url, params=params).json()

    def create_blob(self, owner: str, repo: str, content: bytes) -> str:
        url = f"{self.api_url}/repos/{owner}/{repo}/git/blobs"
        payload = {
            "content": base64.b64encode(content).decode("utf-8"),
            "encoding": "base64",
        }
        response = self._request("POST", url, json=payload)
        return response.json()["sha"]

    def create_tree(
        self,
        owner: str,
        repo: str,
        tree: List[Dict[str, Any]],
        base_tree: Optional[str] = None,
    ) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}/git/trees"
        payload: Dict[str, Any] = {"tree": tree}
        if base_tree:
            payload["base_tree"] = base_tree
        return self._request("POST", url, json=payload).json()

    def create_commit(
        self,
        owner: str,
        repo: str,
        message: str,
        tree_sha: str,
        parents: List[str],
    ) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}/git/commits"
        payload = {"message": message, "tree": tree_sha, "parents": parents}
        return self._request("POST", url, json=payload).json()

    def update_ref(
        self,
        owner: str,
        repo: str,
        branch: str,
        sha: str,
        *,
        force: bool = False,
    ) -> None:
        url = f"{self.api_url}/repos/{owner}/{repo}/git/refs/heads/{branch}"
        payload = {"sha": sha, "force": force}
        self._request("PATCH", url, json=payload)

    def configure_pages_actions(self, owner: str, repo: str) -> None:
        url = f"{self.api_url}/repos/{owner}/{repo}/pages"
        payload = {"build_type": "workflow"}
        try:
            self._request("PUT", url, json=payload)
        except GitHubError as exc:
            if exc.status == 404:
                self._request("POST", url, json=payload)
            else:
                raise

    def get_pages_info(self, owner: str, repo: str) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}/pages"
        return self._request("GET", url).json()

    def update_repository(self, owner: str, repo: str, **fields: Any) -> Mapping[str, Any]:
        url = f"{self.api_url}/repos/{owner}/{repo}"
        return self._request("PATCH", url, json=fields).json()


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
