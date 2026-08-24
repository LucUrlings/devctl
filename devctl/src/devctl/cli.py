from __future__ import annotations

import argparse
import getpass
import json
import os
import platform
import shutil
import subprocess
import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import Config
from .errors import DevctlError
from .render import hosts, ssh_config, traefik_labels
from .runtime import (
    compose_command,
    herdr_json,
    inspect_health,
    one_container,
    run,
    wait_healthy,
    warn,
)
from .storage import (
    allocate_and_reserve_port,
    allocate_port,
    atomic_json,
    atomic_write,
    load_json,
    release_port,
    upsert_env,
)
from .validation import (
    derive_slug,
    normalize_repo_url,
    project_path,
    validate_hostname,
    validate_ref,
    validate_slug,
)


def now() -> str:
    return datetime.now(UTC).isoformat()


def require_project(config: Config, slug: str) -> tuple[Path, dict[str, Any]]:
    path = project_path(config.projects, validate_slug(slug))
    if not path.is_dir():
        raise DevctlError(f"unknown project: {slug}")
    return path, load_json(path / "metadata.json")


def init(config: Config) -> None:
    directories = [
        "config",
        "secrets",
        "shared/codex",
        "shared/claude",
        "shared/gh",
        "herdr",
        "herdr/run",
        "ccgram",
        "projects",
        "ssh",
        "state",
    ]
    for relative in directories:
        path = config.root / relative
        path.mkdir(parents=True, exist_ok=True)
        os.chmod(
            path,
            0o700
            if relative in {"secrets", "shared/codex", "shared/claude", "shared/gh"}
            else 0o755,
        )
    keys = config.root / "ssh" / "authorized_keys"
    if not keys.exists():
        atomic_write(keys, "# Add trusted public SSH keys here.\n", 0o600)
    ports = config.root / "state" / "ports.json"
    if not ports.exists():
        atomic_json(ports, {"allocations": {}})
    print(f"Initialized {config.root}")


def project_env(
    config: Config, slug: str, repo: str, args: argparse.Namespace, port: int
) -> dict[str, str]:
    code_host = validate_hostname(args.code_host or hosts(slug, config.values)[0])
    preview_host = validate_hostname(args.preview_host or hosts(slug, config.values)[1])
    labels = traefik_labels(
        slug, {**config.values, "BASE_DOMAIN": config.get("BASE_DOMAIN")}, args.preview_port
    )
    if args.code_host:
        labels[f"traefik.http.routers.devctl-{slug}-code.rule"] = f"Host(`{code_host}`)"
    if args.preview_host:
        labels[f"traefik.http.routers.devctl-{slug}-preview.rule"] = f"Host(`{preview_host}`)"
    values = {
        "PROJECT_NAME": slug,
        "PROJECT_DIR": str(config.projects / slug),
        "REPO_URL": repo,
        "REPO_BRANCH": args.branch or "",
        "REPO_DEPTH": str(args.depth or ""),
        "WORKSPACE_PATH": "/workspace/project",
        "SSH_PORT": str(port),
        "PREVIEW_PORT": str(args.preview_port),
        "CODE_HOST": code_host,
        "PREVIEW_HOST": preview_host,
        "WORKSPACE_IMAGE": config.get("WORKSPACE_IMAGE"),
        "WORKSPACE_CPUS": config.get("WORKSPACE_CPUS"),
        "WORKSPACE_MEMORY": config.get("WORKSPACE_MEMORY"),
        "TRAEFIK_NETWORK": config.get("TRAEFIK_NETWORK"),
        "TRAEFIK_ENTRYPOINT": config.get("TRAEFIK_ENTRYPOINT"),
        "TRAEFIK_AUTH_MIDDLEWARE": config.get("TRAEFIK_AUTH_MIDDLEWARE"),
        "TRAEFIK_CERT_RESOLVER": config.get("TRAEFIK_CERT_RESOLVER"),
        "TRAEFIK_CODE_ROUTER": f"devctl-{slug}-code",
        "TRAEFIK_PREVIEW_ROUTER": f"devctl-{slug}-preview",
        "HERDR_SOCKET_PATH": "/run/herdr/herdr.sock",
        "GIT_SSH_AUTH_SOCK_HOST_PATH": (
            config.get("GIT_SSH_AUTH_SOCK_HOST_PATH") if repo.startswith("git@") else ""
        ),
    }
    values["TRAEFIK_LABELS_JSON"] = json.dumps(labels, sort_keys=True)
    return values


def env_text(values: dict[str, str]) -> str:
    lines = []
    for key, value in values.items():
        if any(char in value for char in "\n\r\x00"):
            raise DevctlError(f"unsafe newline in configuration value {key}")
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def cmd_create(config: Config, args: argparse.Namespace) -> None:
    allow_ssh = config.get("ALLOW_SSH_GIT").lower() == "true"
    repo = normalize_repo_url(args.repo_url, allow_ssh=allow_ssh)
    slug = validate_slug(args.name) if args.name else derive_slug(repo)
    validate_ref(args.branch)
    try:
        preview_port = (
            args.preview_port
            if args.preview_port is not None
            else int(config.get("DEFAULT_PREVIEW_PORT"))
        )
    except ValueError as exc:
        raise DevctlError("DEFAULT_PREVIEW_PORT must be an integer") from exc
    if not 1 <= preview_port <= 65535:
        raise DevctlError("preview port must be between 1 and 65535")
    args.preview_port = preview_port
    if args.depth is not None and args.depth < 1:
        raise DevctlError("clone depth must be a positive integer")
    selected_agent = args.agent or config.get("DEFAULT_AGENT")
    if selected_agent not in {"none", "codex", "claude"}:
        raise DevctlError("DEFAULT_AGENT must be none, codex, or claude")
    if repo.startswith("git@") and not config.get("GIT_SSH_AUTH_SOCK_HOST_PATH"):
        raise DevctlError("SSH Git requires an explicitly configured GIT_SSH_AUTH_SOCK_HOST_PATH")
    path = project_path(config.projects, slug)
    if path.exists():
        raise DevctlError(f"project already exists: {slug}")
    if (
        not config.get("BASE_DOMAIN")
        or not config.get("TRAEFIK_NETWORK")
        or not config.get("TRAEFIK_AUTH_MIDDLEWARE")
    ):
        raise DevctlError(
            "BASE_DOMAIN, TRAEFIK_NETWORK, and TRAEFIK_AUTH_MIDDLEWARE must be configured"
        )
    if args.docker_mode == "host":
        warn(
            "--docker-mode host grants this workspace effective root control over the "
            "Docker server; use only trusted repositories"
        )
    try:
        port_minimum = int(config.get("SSH_PORT_MIN"))
        port_maximum = int(config.get("SSH_PORT_MAX"))
    except ValueError as exc:
        raise DevctlError("SSH_PORT_MIN and SSH_PORT_MAX must be integers") from exc
    path.mkdir(mode=0o750, parents=True)
    command: list[str] | None = None
    port: int | None = None
    metadata_written = False
    try:
        port = allocate_and_reserve_port(
            config.root, slug, port_minimum, port_maximum, args.ssh_port
        )
        for child in ["repo", "ssh-host-keys", "vscode-server"]:
            (path / child).mkdir(mode=0o700)
        values = project_env(config, slug, repo, args, port)
        metadata: dict[str, Any] = {
            "schema_version": 1,
            "project": slug,
            "repo_url": repo,
            "branch": args.branch,
            "ssh_port": port,
            "preview_port": args.preview_port,
            "code_host": values["CODE_HOST"],
            "preview_host": values["PREVIEW_HOST"],
            "docker_mode": args.docker_mode,
            "herdr": {"registered": False, "enabled": not args.no_herdr},
            "created_at": now(),
            "traefik_labels": json.loads(values["TRAEFIK_LABELS_JSON"]),
        }
        atomic_write(path / "config.env", env_text(values))
        atomic_json(path / "metadata.json", metadata)
        metadata_written = True
        command = compose_command(config, slug, docker_mode=args.docker_mode)
        run([*command, "up", "--detach"])
        wait_healthy(slug, int(config.get("HEALTH_TIMEOUT")))
        if not args.no_herdr:
            register_herdr(config, slug)
        if selected_agent != "none":
            start_agent(config, slug, selected_agent)
        print_project_summary(config, slug)
    except Exception:
        if metadata_written:
            warn(
                f"project state was preserved at {path}; inspect it with "
                f"'devctl logs {slug}' or remove it with 'devctl remove {slug} --purge'"
            )
        else:
            if command is not None:
                try:
                    run([*command, "down", "--remove-orphans"], check=False)
                except DevctlError as cleanup_error:
                    warn(f"could not clean up failed Compose resources: {cleanup_error}")
            if port is not None:
                release_port(config.root, slug)
            if path.exists():
                shutil.rmtree(path)
        raise


def print_project_summary(config: Config, slug: str) -> None:
    _, metadata = require_project(config, slug)
    print(f"Project: {slug}")
    try:
        container = one_container(slug, running=False)
        state, health = inspect_health(container)
        print(f"Container: {container} (status={state}, health={health})")
    except DevctlError:
        print("Container: unavailable")
    print(f"Code: https://{metadata['code_host']}")
    print(f"Preview: https://{metadata['preview_host']}")
    print(f"SSH: dev-{slug}")
    print(f"Next: devctl ssh-config {slug}")


def compose_action(config: Config, slug: str, action: str) -> None:
    _, metadata = require_project(config, slug)
    command = compose_command(config, slug, docker_mode=str(metadata.get("docker_mode", "none")))
    if action == "start":
        run([*command, "up", "--detach"])
        wait_healthy(slug, int(config.get("HEALTH_TIMEOUT")))
        herdr = metadata.get("herdr", {})
        if not isinstance(herdr, dict) or herdr.get("enabled", True):
            register_herdr(config, slug)
    elif action == "stop":
        unregister_herdr(config, slug)
        run([*command, "stop"])
    elif action == "restart":
        unregister_herdr(config, slug)
        run([*command, "restart"])
        wait_healthy(slug, int(config.get("HEALTH_TIMEOUT")))
        herdr = metadata.get("herdr", {})
        if not isinstance(herdr, dict) or herdr.get("enabled", True):
            register_herdr(config, slug)


def register_herdr(config: Config, slug: str) -> None:
    path, metadata = require_project(config, slug)
    current = metadata.get("herdr", {})
    if isinstance(current, dict) and current.get("registered"):
        return
    created = herdr_json(
        ["workspace", "create", "--cwd", str(path / "repo"), "--label", slug, "--no-focus"]
    )
    result = created.get("result", {})
    if not isinstance(result, dict):
        raise DevctlError("Herdr workspace creation did not return result metadata")
    workspace = result.get("workspace", {})
    tab = result.get("tab", {})
    pane = result.get("root_pane", {})
    root_pane = pane.get("pane_id") if isinstance(pane, dict) else None
    workspace_id = workspace.get("workspace_id") if isinstance(workspace, dict) else None
    if not isinstance(root_pane, str) or not isinstance(workspace_id, str):
        if isinstance(workspace_id, str):
            try:
                herdr_json(["workspace", "close", workspace_id])
            except DevctlError as cleanup_error:
                warn(f"could not close incomplete Herdr workspace: {cleanup_error}")
        raise DevctlError("Herdr did not return workspace and root pane IDs")
    ids: dict[str, Any] = {
        "registered": True,
        "enabled": True,
        "workspace_id": workspace_id,
        "tabs": {
            "Shell": {
                "tab_id": tab.get("tab_id") if isinstance(tab, dict) else None,
                "pane_id": root_pane,
            }
        },
    }
    try:
        herdr_json(["pane", "run", root_pane, f"dev-enter {slug} shell"])
        metadata["herdr"] = ids
        atomic_json(path / "metadata.json", metadata)
    except Exception:
        try:
            herdr_json(["workspace", "close", workspace_id])
        except DevctlError as cleanup_error:
            warn(f"could not close incomplete Herdr workspace: {cleanup_error}")
        raise


def unregister_herdr(config: Config, slug: str, *, disable: bool = False) -> None:
    path, metadata = require_project(config, slug)
    current = metadata.get("herdr", {})
    if not isinstance(current, dict):
        return
    if current.get("registered"):
        workspace_id = current.get("workspace_id")
        if isinstance(workspace_id, str):
            herdr_json(["workspace", "close", workspace_id])
    metadata["herdr"] = {
        "registered": False,
        "enabled": False if disable else current.get("enabled", True),
    }
    atomic_json(path / "metadata.json", metadata)


def start_agent(config: Config, slug: str, agent: str) -> None:
    if agent not in {"codex", "claude", "shell"}:
        raise DevctlError("agent must be codex, claude, or shell")
    path, metadata = require_project(config, slug)
    current = metadata.get("herdr", {})
    if not isinstance(current, dict) or not current.get("registered"):
        register_herdr(config, slug)
        metadata = load_json(path / "metadata.json")
        current = metadata["herdr"]
    if agent == "shell":
        container = one_container(slug)
        os.execvp(
            "docker",
            [
                "docker",
                "exec",
                "--interactive",
                "--tty",
                "--user",
                "developer",
                "--workdir",
                "/workspace/project",
                container,
                "bash",
                "-l",
            ],
        )
    workspace_id = current.get("workspace_id")
    if not isinstance(workspace_id, str):
        raise DevctlError("project metadata has no valid Herdr workspace ID")
    response = herdr_json(
        [
            "tab",
            "create",
            "--workspace",
            str(workspace_id),
            "--cwd",
            str(path / "repo"),
            "--label",
            agent.title(),
            "--no-focus",
        ]
    )
    result = response.get("result", {})
    tab = result.get("tab", {}) if isinstance(result, dict) else {}
    pane = result.get("root_pane", {}) if isinstance(result, dict) else {}
    tab_id = tab.get("tab_id") if isinstance(tab, dict) else None
    pane_id = pane.get("pane_id") if isinstance(pane, dict) else None
    if not isinstance(pane_id, str) or not isinstance(tab_id, str):
        if isinstance(tab_id, str):
            try:
                herdr_json(["tab", "close", tab_id])
            except DevctlError as cleanup_error:
                warn(f"could not close incomplete Herdr tab: {cleanup_error}")
        raise DevctlError("Herdr did not return an agent pane ID")
    try:
        herdr_json(["pane", "run", pane_id, f"HERDR_AGENT={agent} dev-enter {slug} {agent}"])
        tabs = current.setdefault("tabs", {})
        if not isinstance(tabs, dict):
            raise DevctlError("project metadata has invalid Herdr tabs")
        tabs[agent.title()] = {"tab_id": tab_id, "pane_id": pane_id}
        atomic_json(path / "metadata.json", metadata)
    except Exception:
        try:
            herdr_json(["tab", "close", tab_id])
        except DevctlError as cleanup_error:
            warn(f"could not close incomplete Herdr tab: {cleanup_error}")
        raise
    print(f"Started {agent} in Herdr pane {pane_id}")


def auth(config: Config, provider: str) -> None:
    if provider == "status":
        checks = {
            "github": (
                ["gh", "auth", "status"],
                {"GH_CONFIG_DIR": str(config.root / "shared" / "gh")},
            ),
            "codex": (
                ["codex", "login", "status"],
                {"CODEX_HOME": str(config.root / "shared" / "codex")},
            ),
            "claude": (
                ["claude", "auth", "status"],
                {"CLAUDE_CONFIG_DIR": str(config.root / "shared" / "claude")},
            ),
        }
        for name, (command, additions) in checks.items():
            environment = os.environ.copy()
            environment.update(additions)
            environment["HOME"] = "/home/developer"
            if os.geteuid() == 0 and shutil.which("runuser"):
                command = [
                    "runuser",
                    "--user",
                    "developer",
                    "--",
                    "env",
                    "HOME=/home/developer",
                    *[f"{key}={value}" for key, value in additions.items()],
                    *command,
                ]
            result = subprocess.run(
                command,
                check=False,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print(f"{name}: {'authenticated' if result.returncode == 0 else 'not authenticated'}")
        return
    env = os.environ.copy()
    if provider == "github":
        env["GH_CONFIG_DIR"] = str(config.root / "shared" / "gh")
        command = [
            "gh",
            "auth",
            "login",
            "--hostname",
            "github.com",
            "--git-protocol",
            "https",
            "--web",
        ]
    elif provider == "codex":
        env["CODEX_HOME"] = str(config.root / "shared" / "codex")
        command = ["codex", "login", "--device-auth"]
    else:
        env["CLAUDE_CONFIG_DIR"] = str(config.root / "shared" / "claude")
        command = ["claude", "auth", "login"]
    env["HOME"] = "/home/developer"
    if os.geteuid() == 0 and shutil.which("runuser"):
        additions = {
            key: env[key]
            for key in ("GH_CONFIG_DIR", "CODEX_HOME", "CLAUDE_CONFIG_DIR")
            if key in env
        }
        command = [
            "runuser",
            "--user",
            "developer",
            "--",
            "env",
            "HOME=/home/developer",
            *[f"{key}={value}" for key, value in additions.items()],
            *command,
        ]
    raise SystemExit(subprocess.run(command, check=False, env=env).returncode)


def telegram(config: Config, action: str) -> None:
    def hub_container() -> str:
        result = run(
            [
                "docker",
                "ps",
                "--filter",
                "label=devctl.managed=true",
                "--filter",
                "label=devctl.role=hub",
                "--format",
                "{{.ID}}",
            ],
            capture=True,
        )
        matches = [line for line in result.stdout.splitlines() if line]
        if len(matches) != 1:
            raise DevctlError(f"expected exactly one running hub container; found {len(matches)}")
        return matches[0]

    if action == "logs":
        matches = [hub_container()]
        run(["docker", "logs", "--tail", "200", matches[0]])
        return
    env_file = config.root / "config" / "ccgram.env"
    token_file = config.root / "secrets" / "telegram-bot-token"
    if action == "status":
        enabled = config.get("CCGRAM_ENABLED").lower() == "true"
        print(f"enabled: {'yes' if enabled else 'no'}")
        print(f"configuration: {'present' if env_file.exists() else 'missing'}")
        token_present = token_file.exists() and token_file.stat().st_size > 0
        print(f"bot token: {'present' if token_present else 'missing'}")
        running = False
        try:
            running = (
                subprocess.run(
                    [
                        "docker",
                        "exec",
                        hub_container(),
                        "pgrep",
                        "-f",
                        "/usr/local/bin/ccgram($| )",
                    ],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )
        except DevctlError:
            pass
        print(f"CCGram process: {'running' if running else 'not running'}")
        if enabled and (not env_file.exists() or not token_present or not running):
            raise SystemExit(1)
        return
    user_ids = input("Allowed Telegram user IDs (comma-separated): ").strip()
    group_id = input("Telegram forum group ID: ").strip()
    if not user_ids or not all(part.strip().isdigit() for part in user_ids.split(",")):
        raise DevctlError("ALLOWED_USERS must contain numeric Telegram user IDs")
    user_ids = ",".join(part.strip() for part in user_ids.split(","))
    if not group_id.startswith("-100") or not group_id[1:].isdigit():
        raise DevctlError("CCGRAM_GROUP_ID must be a Telegram supergroup ID beginning with -100")
    token = getpass.getpass("Bot token: ").strip()
    if not token:
        raise DevctlError("bot token cannot be empty")
    atomic_write(
        env_file,
        f"ALLOWED_USERS={user_ids}\nCCGRAM_GROUP_ID={group_id}\nCCGRAM_MULTIPLEXER=herdr\n",
        0o600,
    )
    atomic_write(token_file, token + "\n", 0o600)
    upsert_env(config.root / "config" / "devctl.env", "CCGRAM_ENABLED", "true")
    print("Telegram configuration written and CCGRAM_ENABLED=true")
    print("The installed host devctl wrapper will now recreate the hub.")


def doctor(config: Config) -> int:
    checks: list[tuple[str, bool, str]] = []
    docker = (
        subprocess.run(
            ["docker", "info"], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        ).returncode
        == 0
    )
    checks.append(("Docker connectivity", docker, "start Docker or verify /var/run/docker.sock"))
    compose = (
        subprocess.run(
            ["docker", "compose", "version"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    checks.append(("Docker Compose", compose, "install the Docker Compose plugin"))
    machine = platform.machine().lower()
    supported_arch = machine in {"x86_64", "amd64", "aarch64", "arm64"}
    checks.append(("Host architecture", supported_arch, f"unsupported architecture: {machine}"))
    required = ["BASE_DOMAIN", "TRAEFIK_NETWORK", "TRAEFIK_AUTH_MIDDLEWARE"]
    configuration_error = f"set {', '.join(required)}"
    configuration_valid = all(config.get(key) for key in required)
    if configuration_valid:
        try:
            validate_hostname(config.get("BASE_DOMAIN"))
            port_minimum = int(config.get("SSH_PORT_MIN"))
            port_maximum = int(config.get("SSH_PORT_MAX"))
            preview_port = int(config.get("DEFAULT_PREVIEW_PORT"))
            if not 1 <= port_minimum <= port_maximum <= 65535:
                raise ValueError("invalid SSH port range")
            if not 1 <= preview_port <= 65535:
                raise ValueError("invalid default preview port")
            if config.get("DEFAULT_AGENT") not in {"none", "codex", "claude"}:
                raise ValueError("invalid default agent")
            if config.get("CCGRAM_ENABLED").lower() not in {"true", "false"}:
                raise ValueError("CCGRAM_ENABLED is not true or false")
        except (DevctlError, ValueError) as exc:
            configuration_valid = False
            configuration_error = str(exc)
    checks.append(("Configuration", configuration_valid, configuration_error))
    writable = config.root.exists() and os.access(config.root, os.W_OK)
    checks.append(
        ("State root writable", writable, f"run devctl init and fix permissions on {config.root}")
    )
    keys = config.root / "ssh" / "authorized_keys"
    has_keys = keys.exists() and any(
        line.strip() and not line.lstrip().startswith("#")
        for line in keys.read_text(encoding="utf-8").splitlines()
    )
    checks.append(("Authorized keys", has_keys, f"add a public key to {keys}"))
    network = False
    if docker and config.get("TRAEFIK_NETWORK"):
        network = (
            subprocess.run(
                ["docker", "network", "inspect", config.get("TRAEFIK_NETWORK")],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode
            == 0
        )
    checks.append(
        (
            "Traefik network",
            network,
            "create/configure the external network; Devctl will not modify Traefik",
        )
    )
    herdr = (
        subprocess.run(
            ["herdr", "status", "server"],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode
        == 0
    )
    checks.append(("Herdr server", herdr, "start or inspect the hub"))
    ccgram_enabled = config.get("CCGRAM_ENABLED").lower() == "true"
    checks.append(
        (
            "CCGram configuration" if ccgram_enabled else "CCGram (optional, disabled)",
            not ccgram_enabled
            or (
                (config.root / "config" / "ccgram.env").exists()
                and (config.root / "secrets" / "telegram-bot-token").exists()
            ),
            "run devctl telegram configure",
        )
    )
    for name, relative in [
        ("Codex auth", "codex/auth.json"),
        ("Claude auth", "claude"),
        ("GitHub auth", "gh/hosts.yml"),
    ]:
        target = config.root / "shared" / relative
        checks.append(
            (
                name,
                target.exists() and (target.is_file() or any(target.iterdir())),
                f"run devctl auth {name.split()[0].lower()}",
            )
        )
    available = False
    try:
        allocate_port(config.root, int(config.get("SSH_PORT_MIN")), int(config.get("SSH_PORT_MAX")))
        available = True
    except (DevctlError, ValueError):
        pass
    checks.append(("SSH port range", available, "expand or free the configured range"))
    for label, key in [("Hub image", "HUB_IMAGE"), ("Workspace image", "WORKSPACE_IMAGE")]:
        image_access = False
        if docker:
            image_access = (
                subprocess.run(
                    ["docker", "manifest", "inspect", config.get(key)],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            )
        checks.append(
            (
                f"{label} accessibility",
                image_access,
                f"authenticate Docker to GHCR and verify {key}",
            )
        )
    for label, ok, fix in checks:
        print(f"[{'OK' if ok else 'FAIL'}] {label}{'' if ok else f': {fix}'}")
    return 0 if all(item[1] for item in checks) else 1


def remove(config: Config, slug: str, purge: bool, yes: bool) -> None:
    path, metadata = require_project(config, slug)
    command = compose_command(config, slug, docker_mode=str(metadata.get("docker_mode", "none")))
    unregister_herdr(config, slug)
    run([*command, "down", "--remove-orphans"])
    if not purge:
        print(f"Removed containers; preserved {path}")
        return
    exact = project_path(config.projects, slug)
    print(f"Purge directory: {exact}")
    if not yes and input(f"Type the project name '{slug}' to permanently delete it: ") != slug:
        raise DevctlError("purge cancelled")
    if exact.parent != config.projects.resolve() or exact.name != slug:
        raise DevctlError("refusing unsafe purge path")
    shutil.rmtree(exact)
    release_port(config.root, slug)
    print(f"Permanently deleted {exact}; recovery requires a backup")


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="devctl")
    sub = root.add_subparsers(dest="command", required=True)
    sub.add_parser("init")
    create = sub.add_parser("create")
    create.add_argument("repo_url")
    create.add_argument("--name")
    create.add_argument("--branch")
    create.add_argument("--depth", type=int)
    create.add_argument("--preview-port", type=int)
    create.add_argument("--ssh-port", type=int)
    create.add_argument("--code-host")
    create.add_argument("--preview-host")
    create.add_argument("--no-herdr", action="store_true")
    create.add_argument("--agent", choices=["none", "codex", "claude"], default=None)
    create.add_argument("--docker-mode", choices=["none", "host"], default="none")
    sub.add_parser("list")
    for name in ["status", "start", "stop", "restart", "logs", "shell", "ssh-config", "urls"]:
        item = sub.add_parser(name)
        item.add_argument("project")
    execute = sub.add_parser("exec")
    execute.add_argument("project")
    execute.add_argument("exec_command", nargs=argparse.REMAINDER)
    agent = sub.add_parser("agent")
    agent.add_argument("project")
    agent.add_argument("agent", choices=["codex", "claude", "shell"])
    remove_parser = sub.add_parser("remove")
    remove_parser.add_argument("project")
    remove_parser.add_argument("--purge", action="store_true")
    remove_parser.add_argument("--yes", action="store_true")
    herdr = sub.add_parser("herdr")
    herdr.add_argument("action", choices=["register", "unregister", "attach"])
    herdr.add_argument("project", nargs="?")
    auth_parser = sub.add_parser("auth")
    auth_parser.add_argument("provider", choices=["github", "codex", "claude", "status"])
    telegram_parser = sub.add_parser("telegram")
    telegram_parser.add_argument("action", choices=["configure", "status", "logs"])
    sub.add_parser("doctor")
    return root


def dispatch(args: argparse.Namespace, config: Config) -> int:
    if args.command == "init":
        init(config)
    elif args.command == "create":
        cmd_create(config, args)
    elif args.command == "list":
        for item in (
            sorted(config.projects.glob("*/metadata.json")) if config.projects.exists() else []
        ):
            metadata = load_json(item)
            print(f"{metadata['project']:<42} {metadata['repo_url']}")
    elif args.command == "status":
        print_project_summary(config, args.project)
    elif args.command in {"start", "stop", "restart"}:
        compose_action(config, args.project, args.command)
    elif args.command == "logs":
        run(
            [
                "docker",
                "logs",
                "--follow",
                one_container(validate_slug(args.project), running=False),
            ]
        )
    elif args.command in {"exec", "shell"}:
        slug = validate_slug(args.project)
        container = one_container(slug)
        command: Sequence[str] = (
            args.exec_command if args.command == "exec" and args.exec_command else ["bash", "-l"]
        )
        docker_arguments = ["docker", "exec", "--interactive"]
        if sys.stdin.isatty() and sys.stdout.isatty():
            docker_arguments.append("--tty")
        os.execvp(
            "docker",
            [
                *docker_arguments,
                "--user",
                "developer",
                "--workdir",
                "/workspace/project",
                container,
                *command,
            ],
        )
    elif args.command == "agent":
        start_agent(config, validate_slug(args.project), args.agent)
    elif args.command == "remove":
        remove(config, validate_slug(args.project), args.purge, args.yes)
    elif args.command == "herdr":
        if args.action == "attach":
            os.execvp("herdr", ["herdr"])
        if not args.project:
            raise DevctlError("project is required for register/unregister")
        slug = validate_slug(args.project)
        if args.action == "register":
            register_herdr(config, slug)
        else:
            unregister_herdr(config, slug, disable=True)
    elif args.command == "auth":
        auth(config, args.provider)
    elif args.command == "telegram":
        telegram(config, args.action)
    elif args.command == "ssh-config":
        _, metadata = require_project(config, validate_slug(args.project))
        print(ssh_config(args.project, int(metadata["ssh_port"]), config.values), end="")
    elif args.command == "urls":
        _, metadata = require_project(config, validate_slug(args.project))
        print(f"Code: https://{metadata['code_host']}\nPreview: https://{metadata['preview_host']}")
    elif args.command == "doctor":
        return doctor(config)
    return 0


def main(argv: Sequence[str] | None = None) -> None:
    try:
        raise SystemExit(dispatch(parser().parse_args(argv), Config.load()))
    except DevctlError as exc:
        print(f"devctl: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
