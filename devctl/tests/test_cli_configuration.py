import argparse
from pathlib import Path

import pytest

from devctl.cli import parser, project_env, start_agent
from devctl.config import DEFAULTS, Config
from devctl.errors import DevctlError
from devctl.runtime import template_path


def configured(tmp_path: Path) -> Config:
    return Config(
        root=tmp_path,
        values={
            **DEFAULTS,
            "BASE_DOMAIN": "example.test",
            "TRAEFIK_NETWORK": "proxy",
            "TRAEFIK_AUTH_MIDDLEWARE": "oauth@docker",
            "WORKSPACE_CPUS": "2.5",
            "WORKSPACE_MEMORY": "6G",
        },
    )


def test_create_parser_defers_preview_default_to_host_configuration() -> None:
    arguments = parser().parse_args(["create", "https://github.com/owner/repo"])
    assert arguments.preview_port is None


def test_project_environment_carries_resource_configuration(tmp_path: Path) -> None:
    arguments = argparse.Namespace(
        branch=None,
        depth=None,
        preview_port=4321,
        code_host=None,
        preview_host=None,
    )
    values = project_env(
        configured(tmp_path), "project", "https://github.com/owner/repo", arguments, 22000
    )
    assert values["PREVIEW_PORT"] == "4321"
    assert values["WORKSPACE_CPUS"] == "2.5"
    assert values["WORKSPACE_MEMORY"] == "6G"


def test_default_agent_cannot_become_a_shell_command(tmp_path: Path) -> None:
    with pytest.raises(DevctlError, match="agent must be"):
        start_agent(configured(tmp_path), "project", "codex; touch /tmp/unsafe")


def test_source_checkout_compose_templates_are_discoverable() -> None:
    assert (template_path() / "workspace.compose.yml").is_file()
