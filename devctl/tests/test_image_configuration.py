from pathlib import Path


def test_ssh_sessions_receive_only_server_controlled_integration_paths() -> None:
    config = (
        Path(__file__).resolve().parents[2]
        / "images/workspace/rootfs/etc/ssh/sshd_config.d/99-devctl.conf"
    ).read_text(encoding="utf-8")
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
