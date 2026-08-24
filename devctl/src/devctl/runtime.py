from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from .config import Config, parse_env
from .errors import DevctlError


def run(
    command: Sequence[str], *, check: bool = True, capture: bool = False
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command), check=check, text=True, capture_output=capture, env=os.environ.copy()
        )
    except FileNotFoundError as exc:
        raise DevctlError(f"required command is unavailable: {command[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise DevctlError(f"command failed ({command[0]}): {detail or exc.returncode}") from exc


def template_path() -> Path:
    override = os.environ.get("DEVCTL_COMPOSE_DIR")
    candidates = [
        Path(override) if override else Path("/nonexistent"),
        Path("/opt/devctl/compose"),
        Path(__file__).resolve().parents[3] / "compose",
    ]
    for candidate in candidates:
        if (candidate / "workspace.compose.yml").exists():
            return candidate
    raise DevctlError("cannot locate Devctl Compose templates")


def compose_command(config: Config, slug: str, *, docker_mode: str = "none") -> list[str]:
    project_dir = config.projects / slug
    command = [
        "docker",
        "compose",
        "--project-name",
        f"devctl-{slug}",
        "--env-file",
        str(project_dir / "config.env"),
        "--file",
        str(template_path() / "workspace.compose.yml"),
    ]
    if docker_mode == "host":
        command += ["--file", str(template_path() / "workspace.docker-host.override.yml")]
    project_values = parse_env(project_dir / "config.env")
    if project_values.get("GIT_SSH_AUTH_SOCK_HOST_PATH"):
        command += ["--file", str(template_path() / "workspace.git-ssh-agent.override.yml")]
    if project_values.get("TRAEFIK_CERT_RESOLVER"):
        command += [
            "--file",
            str(template_path() / "workspace.traefik-certresolver.override.yml"),
        ]
    return command


def containers(slug: str, *, running: bool = False) -> list[str]:
    command = [
        "docker",
        "ps",
        "--filter",
        "label=devctl.managed=true",
        "--filter",
        f"label=devctl.project={slug}",
        "--format",
        "{{.ID}}",
    ]
    if not running:
        command.insert(2, "--all")
    result = run(command, capture=True)
    return [line for line in result.stdout.splitlines() if line]


def one_container(slug: str, *, running: bool = True) -> str:
    matches = containers(slug, running=running)
    if len(matches) != 1:
        raise DevctlError(
            f"expected exactly one {'running ' if running else ''}container "
            f"for {slug}; found {len(matches)}"
        )
    return matches[0]


def inspect_health(container: str) -> tuple[str, str]:
    result = run(
        [
            "docker",
            "inspect",
            "--format",
            "{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{end}}",
            container,
        ],
        capture=True,
    )
    parts = result.stdout.strip().split()
    return parts[0], parts[1] if len(parts) > 1 else "unknown"


def wait_healthy(slug: str, timeout: int) -> None:
    deadline = time.monotonic() + timeout
    last = "container not created"
    while time.monotonic() < deadline:
        try:
            container = one_container(slug)
            state, health = inspect_health(container)
            last = f"status={state}, health={health}"
            if state == "running" and health == "healthy":
                return
            if state in {"dead", "exited", "restarting"} or health == "unhealthy":
                break
        except DevctlError as exc:
            last = str(exc)
        time.sleep(2)
    raise DevctlError(f"workspace {slug} did not become healthy: {last}")


def herdr_json(command: Sequence[str]) -> dict[str, object]:
    result = run(["herdr", *command], capture=True)
    try:
        value = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise DevctlError(f"Herdr returned invalid JSON for {' '.join(command)}") from exc
    if not isinstance(value, dict):
        raise DevctlError("Herdr response was not an object")
    return value


def warn(message: str) -> None:
    print(f"WARNING: {message}", file=sys.stderr)
