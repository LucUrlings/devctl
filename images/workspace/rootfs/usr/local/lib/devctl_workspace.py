from __future__ import annotations

import base64
import binascii
import re
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


class WorkspaceError(ValueError):
    pass


SAFE_REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
SAFE_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
PUBLIC_KEY_TYPES = {
    "ssh-ed25519",
    "ssh-rsa",
    "ecdsa-sha2-nistp256",
    "ecdsa-sha2-nistp384",
    "ecdsa-sha2-nistp521",
    "sk-ssh-ed25519@openssh.com",
    "sk-ecdsa-sha2-nistp256@openssh.com",
}


def validate_slug(value: str) -> str:
    if not SAFE_SLUG.fullmatch(value):
        raise WorkspaceError("PROJECT_NAME must match [a-z0-9][a-z0-9-]{0,40}")
    return value


def normalize_repo_url(value: str) -> str:
    if not value or any(char.isspace() or ord(char) < 32 for char in value):
        raise WorkspaceError("repository URL is empty or contains whitespace/control characters")
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise WorkspaceError("repository URL is invalid") from exc
    if parsed.scheme != "https" or not parsed.netloc:
        raise WorkspaceError("repository URL must use HTTPS")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise WorkspaceError("repository URL must not contain credentials, query, or fragment")
    try:
        port = parsed.port
    except ValueError as exc:
        raise WorkspaceError("repository URL has an invalid port") from exc
    if port not in (None, 443):
        raise WorkspaceError("repository HTTPS URL may only use port 443")
    path = parsed.path.rstrip("/")
    if path in ("", "/") or path.endswith("/.") or "/../" in f"{path}/":
        raise WorkspaceError("repository URL has an invalid path")
    if parsed.hostname is None:
        raise WorkspaceError("repository URL has no hostname")
    return urlunsplit(("https", parsed.hostname.lower(), path, "", ""))


def canonical_origin(value: str) -> str:
    url = normalize_repo_url(value.strip()).rstrip("/")
    if url.endswith(".git"):
        url = url[:-4]
    parsed = urlsplit(url)
    path = parsed.path.lower() if parsed.hostname == "github.com" else parsed.path
    return urlunsplit((parsed.scheme, parsed.netloc.lower(), path, "", ""))


def validate_ref(value: str) -> str:
    if value and (
        not SAFE_REF.fullmatch(value)
        or value.startswith("-")
        or ".." in value
        or "//" in value
    ):
        raise WorkspaceError("branch is not a safe Git ref")
    return value


def authorized_keys_configured(path: Path) -> bool:
    """Accept at least one structurally valid public-key line, including key options."""
    if not path.is_file():
        return False
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        fields = line.split()
        for index, field in enumerate(fields[:-1]):
            if field not in PUBLIC_KEY_TYPES:
                continue
            try:
                decoded = base64.b64decode(fields[index + 1], validate=True)
            except (binascii.Error, ValueError):
                continue
            if decoded:
                return True
    return False


def workspace_action(workspace: Path, repo_url: str, get_origin: Callable[[], str]) -> str:
    entries = list(workspace.iterdir()) if workspace.exists() else []
    if not entries:
        return "clone"
    if not (workspace / ".git").exists():
        raise WorkspaceError("workspace is non-empty but is not a Git repository")
    origin = get_origin()
    if canonical_origin(origin) != canonical_origin(repo_url):
        raise WorkspaceError("origin mismatch: existing repository origin does not match REPO_URL")
    return "reuse"


def clone_command(
    repo_url: str, workspace: Path, branch: str = "", depth: str = ""
) -> list[str]:
    repo_url = normalize_repo_url(repo_url)
    branch = validate_ref(branch)
    command = ["git", "clone"]
    if branch:
        command += ["--branch", branch]
    if depth:
        if (
            not depth.isdigit()
            or len(depth) > 10
            or not 1 <= int(depth) <= 2_147_483_647
        ):
            raise WorkspaceError("REPO_DEPTH must be between 1 and 2147483647")
        command += ["--depth", depth]
    return [*command, "--", repo_url, str(workspace)]
