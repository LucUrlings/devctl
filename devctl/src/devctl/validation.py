from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from .errors import DevctlError

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,40}$")
SCP_SSH_RE = re.compile(r"^git@github\.com:([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?$")
SAFE_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$")
HOST_RE = re.compile(
    r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$"
)


def validate_slug(value: str) -> str:
    if not SLUG_RE.fullmatch(value):
        raise DevctlError("project name must match [a-z0-9][a-z0-9-]{0,40}")
    return value


def derive_slug(repo_url: str) -> str:
    path = SCP_SSH_RE.fullmatch(repo_url)
    name = path.group(2) if path else Path(urlsplit(repo_url).path).name
    if name.endswith(".git"):
        name = name[:-4]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:41].rstrip("-")
    return validate_slug(slug)


def normalize_repo_url(value: str, *, allow_ssh: bool = False) -> str:
    if not value or any(char.isspace() or ord(char) < 32 for char in value):
        raise DevctlError("repository URL is empty or contains whitespace/control characters")
    ssh = SCP_SSH_RE.fullmatch(value)
    if ssh:
        if not allow_ssh:
            raise DevctlError("SSH Git URLs require ALLOW_SSH_GIT=true and an agent/deploy key")
        return f"git@github.com:{ssh.group(1)}/{ssh.group(2)}.git"
    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise DevctlError("repository URL is invalid") from exc
    if parsed.scheme != "https" or not parsed.netloc:
        raise DevctlError("repository URL must use HTTPS (or explicitly enabled GitHub SSH)")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise DevctlError(
            "repository URLs must not contain credentials, query strings, or fragments"
        )
    try:
        port = parsed.port
    except ValueError as exc:
        raise DevctlError("repository URL has an invalid port") from exc
    if port not in (None, 443):
        raise DevctlError("repository HTTPS URLs may only use port 443")
    path = parsed.path.rstrip("/")
    if path in ("", "/") or path.endswith("/.") or "/../" in f"{path}/":
        raise DevctlError("repository URL has an invalid path")
    hostname = parsed.hostname
    if hostname is None:
        raise DevctlError("repository URL has no hostname")
    return urlunsplit(("https", hostname.lower(), path, "", ""))


def validate_ref(value: str | None) -> str | None:
    if value is not None and not SAFE_REF_RE.fullmatch(value):
        raise DevctlError("branch contains unsupported characters")
    if value and (value.startswith("-") or ".." in value or "//" in value):
        raise DevctlError("branch is not a safe Git ref")
    return value


def project_path(projects_root: Path, slug: str) -> Path:
    validate_slug(slug)
    root = projects_root.resolve()
    candidate = (root / slug).resolve(strict=False)
    if candidate.parent != root:
        raise DevctlError("project path escaped the configured project root")
    return candidate


def validate_hostname(value: str) -> str:
    normalized = value.lower().rstrip(".")
    if not HOST_RE.fullmatch(normalized):
        raise DevctlError(f"invalid route hostname: {value!r}")
    return normalized
