"""Command line tools for the Gemini Actions Lab."""

from .secrets import SecretSyncError, SecretSyncResult, sync_repository_secrets, sync_secrets_from_env_file

__all__ = [
    "__version__",
    "SecretSyncError",
    "SecretSyncResult",
    "sync_repository_secrets",
    "sync_secrets_from_env_file",
]

__version__ = "0.1.0"
