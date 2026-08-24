from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .errors import DevctlError


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise DevctlError(f"invalid configuration line {number} in {path}")
        key, value = line.split("=", 1)
        if not key.replace("_", "").isalnum() or not key[0].isalpha():
            raise DevctlError(f"invalid configuration key on line {number} in {path}")
        values[key] = value
    return values


@dataclass(frozen=True)
class Config:
    root: Path
    values: dict[str, str]

    @classmethod
    def load(cls) -> Config:
        root = Path(os.environ.get("DEVCTL_ROOT", "/srv/devctl"))
        file_values = parse_env(root / "config" / "devctl.env")
        merged = {**file_values, **{k: v for k, v in os.environ.items() if k in DEFAULTS}}
        return cls(root=root, values={**DEFAULTS, **merged})

    def get(self, key: str) -> str:
        return self.values[key]

    @property
    def projects(self) -> Path:
        return self.root / "projects"


DEFAULTS = {
    "TRAEFIK_NETWORK": "",
    "TRAEFIK_ENTRYPOINT": "websecure",
    "TRAEFIK_AUTH_MIDDLEWARE": "",
    "TRAEFIK_CERT_RESOLVER": "",
    "BASE_DOMAIN": "",
    "CODE_SUBDOMAIN": "code",
    "PREVIEW_SUBDOMAIN": "dev",
    "SSH_PORT_MIN": "22000",
    "SSH_PORT_MAX": "22999",
    "SSH_JUMP_HOST": "dev-server",
    "SSH_IDENTITY_FILE": "~/.ssh/id_ed25519",
    "WORKSPACE_IMAGE": "ghcr.io/lucurlings/devctl-workspace:latest",
    "HUB_IMAGE": "ghcr.io/lucurlings/devctl-hub:latest",
    "ALLOW_SSH_GIT": "false",
    "GIT_SSH_AUTH_SOCK_HOST_PATH": "",
    "DEFAULT_PREVIEW_PORT": "3000",
    "DEFAULT_AGENT": "none",
    "WORKSPACE_CPUS": "4",
    "WORKSPACE_MEMORY": "8G",
    "HEALTH_TIMEOUT": "180",
    "CCGRAM_ENABLED": "false",
}
