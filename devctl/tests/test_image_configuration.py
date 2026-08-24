from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ssh_sessions_receive_only_server_controlled_integration_paths() -> None:
    config = (ROOT / "images/workspace/rootfs/etc/ssh/sshd_config.d/99-devctl.conf").read_text(
        encoding="utf-8"
    )
    expected = {
        "CODEX_HOME=/home/developer/.codex",
        "CLAUDE_CONFIG_DIR=/home/developer/.claude",
        "GH_CONFIG_DIR=/home/developer/.config/gh",
        "HERDR_SOCKET_PATH=/run/herdr/herdr.sock",
        "CCGRAM_DIR=/srv/devctl/ccgram",
        "WORKSPACE_PATH=/workspace/project",
        "SSH_AUTH_SOCK=/run/devctl-ssh-agent",
    }
    setenv_lines = [line for line in config.splitlines() if line.startswith("SetEnv ")]
    assert len(setenv_lines) == 1
    assert expected <= set(setenv_lines[0].split()[1:])
    assert "PermitUserEnvironment no" in config
    assert "PermitUserEnvironment yes" not in config


def test_herdr_socket_is_restricted_to_the_shared_developer_identity() -> None:
    launcher = (ROOT / "images/hub/rootfs/usr/local/bin/herdr-server-launch").read_text(
        encoding="utf-8"
    )
    assert 'chown developer:developer "$HERDR_SOCKET_PATH"' in launcher
    assert 'chmod 0600 "$HERDR_SOCKET_PATH"' in launcher
    assert "chmod 0666" not in launcher


def test_telegram_is_optional_when_disabled() -> None:
    ccgram = (ROOT / "images/hub/rootfs/usr/local/bin/ccgram-launch").read_text(encoding="utf-8")
    health = (ROOT / "images/hub/rootfs/usr/local/bin/hub-healthcheck").read_text(encoding="utf-8")
    compose = (ROOT / "compose/hub.compose.yml").read_text(encoding="utf-8")
    assert "CCGRAM_ENABLED: ${CCGRAM_ENABLED:-false}" in compose
    assert "if [[ ${CCGRAM_ENABLED:-false} != true ]]; then\n  exec sleep infinity\nfi" in ccgram
    assert "if [[ ${CCGRAM_ENABLED:-false} == true ]]; then" in health
