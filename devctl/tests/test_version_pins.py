import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def versions() -> dict[str, str]:
    result: dict[str, str] = {}
    for raw in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines():
        if raw and not raw.startswith("#") and "=" in raw:
            key, value = raw.split("=", 1)
            result[key] = value
    return result


def dockerfile_argument(dockerfile: str, key: str) -> str | None:
    match = re.search(rf"^ARG {re.escape(key)}(?:=(.+))?$", dockerfile, re.MULTILINE)
    assert match is not None, f"missing Dockerfile argument {key}"
    return match.group(1)


def test_direct_ci_builds_and_bake_share_release_pins() -> None:
    selected = versions()
    bake = (ROOT / "docker-bake.hcl").read_text(encoding="utf-8")
    hub = (ROOT / "images/hub/Dockerfile").read_text(encoding="utf-8")
    workspace = (ROOT / "images/workspace/Dockerfile").read_text(encoding="utf-8")

    shared = {
        "PYTHON_VERSION",
        "NODE_VERSION",
        "NPM_VERSION",
        "DOCKER_CLI_VERSION",
        "CODEX_VERSION",
        "CLAUDE_CODE_VERSION",
        "HERDR_VERSION",
        "CCGRAM_VERSION",
        "GH_VERSION",
        "UV_VERSION",
        "MSGPACK_VERSION",
        "SETUPTOOLS_VERSION",
        "BASH_PACKAGE_VERSION",
        "CA_CERTIFICATES_PACKAGE_VERSION",
        "CURL_PACKAGE_VERSION",
        "GIT_PACKAGE_VERSION",
        "JQ_PACKAGE_VERSION",
        "OPENSSH_PACKAGE_VERSION",
        "PROCPS_PACKAGE_VERSION",
        "RIPGREP_PACKAGE_VERSION",
        "TINI_PACKAGE_VERSION",
        "UTIL_LINUX_PACKAGE_VERSION",
        "LOGIN_PACKAGE_VERSION",
        "HERDR_AMD64_SHA256",
        "HERDR_ARM64_SHA256",
        "GH_AMD64_SHA256",
        "GH_ARM64_SHA256",
    }
    workspace_only = {
        "CODE_SERVER_VERSION",
        "PIPX_VERSION",
        "BUILD_ESSENTIAL_PACKAGE_VERSION",
        "LESS_PACKAGE_VERSION",
        "NANO_PACKAGE_VERSION",
        "SUDO_PACKAGE_VERSION",
        "VIM_PACKAGE_VERSION",
        "WGET_PACKAGE_VERSION",
        "CODE_SERVER_AMD64_SHA256",
        "CODE_SERVER_ARM64_SHA256",
    }
    for key in shared | workspace_only:
        assert f'{key} = "{selected[key]}"' in bake
        assert dockerfile_argument(workspace, key) == selected[key]
    for key in shared:
        assert dockerfile_argument(hub, key) == selected[key]


def test_every_action_revision_is_used_as_a_full_sha() -> None:
    workflows = "\n".join(
        path.read_text(encoding="utf-8") for path in (ROOT / ".github/workflows").glob("*.yml")
    )
    for key, revision in versions().items():
        if key.startswith("ACTION_"):
            assert re.fullmatch(r"[0-9a-f]{40}", revision)
            assert f"@{revision}" in workflows


def test_project_version_is_centralized() -> None:
    selected = versions()["DEVCTL_VERSION"]
    pyproject = (ROOT / "devctl/pyproject.toml").read_text(encoding="utf-8")
    package = (ROOT / "devctl/src/devctl/__init__.py").read_text(encoding="utf-8")
    launcher = (ROOT / "scripts/devctl-host").read_text(encoding="utf-8")
    assert f'version = "{selected}"' in pyproject
    assert f'__version__ = "{selected}"' in package
    assert f"DEVCTL_LAUNCHER_VERSION={selected}" in launcher
