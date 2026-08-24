from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .errors import DevctlError
from .validation import normalize_repo_url


def canonical_origin(url: str) -> str:
    try:
        value = normalize_repo_url(url.strip(), allow_ssh=True).rstrip("/")
    except DevctlError as exc:
        raise DevctlError("existing repository origin is not a safe repository URL") from exc
    if value.endswith(".git"):
        value = value[:-4]
    if value.startswith("git@github.com:"):
        return value.lower()
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise DevctlError("repository origin is invalid") from exc
    path = parsed.path.lower() if parsed.hostname == "github.com" else parsed.path
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), path, "", ""))


def workspace_action(workspace: Path, repo_url: str, get_origin: Callable[[], str]) -> str:
    entries = list(workspace.iterdir()) if workspace.exists() else []
    if not entries:
        return "clone"
    if not (workspace / ".git").exists():
        raise DevctlError("workspace is non-empty but is not a Git repository")
    origin = get_origin()
    if canonical_origin(origin) != canonical_origin(repo_url):
        raise DevctlError(f"origin mismatch: existing repository is {origin!r}")
    return "reuse"


def clone_command(repo_url: str, workspace: Path, branch: str = "", depth: str = "") -> list[str]:
    command = ["git", "clone"]
    if branch:
        command += ["--branch", branch]
    if depth:
        if not depth.isdigit() or int(depth) < 1:
            raise DevctlError("REPO_DEPTH must be a positive integer")
        command += ["--depth", depth]
    return [*command, "--", repo_url, str(workspace)]
