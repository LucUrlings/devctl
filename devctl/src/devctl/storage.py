from __future__ import annotations

import fcntl
import json
import os
import socket
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from .errors import DevctlError


def atomic_write(path: Path, content: str, mode: int = 0o600) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def atomic_json(path: Path, value: dict[str, Any], mode: int = 0o600) -> None:
    atomic_write(path, json.dumps(value, indent=2, sort_keys=True) + "\n", mode)


def upsert_env(path: Path, key: str, value: str) -> None:
    """Set one simple environment-file key without evaluating its contents."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    replacement = f"{key}={value}"
    output: list[str] = []
    replaced = False
    for line in lines:
        if line.split("=", 1)[0].strip() == key:
            if not replaced:
                output.append(replacement)
                replaced = True
        else:
            output.append(line)
    if not replaced:
        output.append(replacement)
    atomic_write(path, "\n".join(output) + "\n", 0o600)


def load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DevctlError(f"cannot read metadata {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise DevctlError(f"metadata is not an object: {path}")
    return value


@contextmanager
def locked(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


def port_available(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


def allocate_port(root: Path, minimum: int, maximum: int, requested: int | None = None) -> int:
    return _allocate_port(root, minimum, maximum, requested, reserve_for=None)


def allocate_and_reserve_port(
    root: Path, slug: str, minimum: int, maximum: int, requested: int | None = None
) -> int:
    """Choose and reserve a port while holding one registry lock."""
    return _allocate_port(root, minimum, maximum, requested, reserve_for=slug)


def _allocate_port(
    root: Path,
    minimum: int,
    maximum: int,
    requested: int | None,
    *,
    reserve_for: str | None,
) -> int:
    if not 1 <= minimum <= maximum <= 65535:
        raise DevctlError("invalid SSH port allocation range")
    registry = root / "state" / "ports.json"
    with locked(root / "state" / "ports.lock"):
        data = load_json(registry) if registry.exists() else {"allocations": {}}
        allocations = data.setdefault("allocations", {})
        used = {int(value) for value in allocations.values()}
        candidates = [requested] if requested is not None else range(minimum, maximum + 1)
        for port in candidates:
            if port is None or not minimum <= port <= maximum:
                continue
            if port not in used and port_available(port):
                if reserve_for is not None:
                    allocations[reserve_for] = port
                    atomic_json(registry, data)
                return port
    raise DevctlError("no unused SSH port is available in the configured range")


def reserve_port(root: Path, slug: str, port: int) -> None:
    registry = root / "state" / "ports.json"
    with locked(root / "state" / "ports.lock"):
        data = load_json(registry) if registry.exists() else {"allocations": {}}
        allocations = data.setdefault("allocations", {})
        if any(int(value) == port and key != slug for key, value in allocations.items()):
            raise DevctlError(f"SSH port {port} was allocated concurrently")
        allocations[slug] = port
        atomic_json(registry, data)


def release_port(root: Path, slug: str) -> None:
    registry = root / "state" / "ports.json"
    with locked(root / "state" / "ports.lock"):
        if not registry.exists():
            return
        data = load_json(registry)
        data.setdefault("allocations", {}).pop(slug, None)
        atomic_json(registry, data)
