"""Test suite for gemini-actions-lab-cli."""

from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


if "requests" not in sys.modules:
    requests_stub = ModuleType("requests")

    def _request(*_args: object, **_kwargs: object) -> None:  # pragma: no cover - safeguard
        raise RuntimeError("requests stub called during tests")

    requests_stub.request = _request  # type: ignore[attr-defined]
    sys.modules["requests"] = requests_stub


if "nacl" not in sys.modules:
    nacl_stub = ModuleType("nacl")
    encoding_stub = ModuleType("nacl.encoding")
    public_stub = ModuleType("nacl.public")

    class _Base64Encoder:  # pragma: no cover - used only to satisfy imports
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

    class _PublicKey:  # pragma: no cover - safeguard for unexpected usage
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("nacl stub called during tests")

    class _SealedBox:  # pragma: no cover - safeguard for unexpected usage
        def __init__(self, *_args: object, **_kwargs: object) -> None:
            raise RuntimeError("nacl stub called during tests")

        def encrypt(self, *_args: object, **_kwargs: object) -> bytes:
            raise RuntimeError("nacl stub called during tests")

    encoding_stub.Base64Encoder = _Base64Encoder  # type: ignore[attr-defined]
    public_stub.PublicKey = _PublicKey  # type: ignore[attr-defined]
    public_stub.SealedBox = _SealedBox  # type: ignore[attr-defined]

    nacl_stub.encoding = encoding_stub  # type: ignore[attr-defined]
    nacl_stub.public = public_stub  # type: ignore[attr-defined]

    sys.modules["nacl"] = nacl_stub
    sys.modules["nacl.encoding"] = encoding_stub
    sys.modules["nacl.public"] = public_stub
