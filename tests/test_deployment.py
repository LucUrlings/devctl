from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SETUP = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
WORKSPACE = (ROOT / "deploy/workspace.compose.yml").read_text(encoding="utf-8")
HUB = (ROOT / "deploy/hub.compose.yml").read_text(encoding="utf-8")
DEV_ENTER = (ROOT / "images/hub/rootfs/usr/local/bin/dev-enter").read_text(
    encoding="utf-8"
)
WORKSPACE_ENTRYPOINT = (
    ROOT / "images/workspace/rootfs/usr/local/bin/workspace-entrypoint"
).read_text(encoding="utf-8")
SSHD_CONFIG = (
    ROOT / "images/workspace/rootfs/etc/ssh/sshd_config.d/99-devctl.conf"
).read_text(encoding="utf-8")


class DeploymentTests(unittest.TestCase):
    def test_stock_ccgram_and_herdr_are_not_monkey_patched(self) -> None:
        ccgram_launch = (
            ROOT / "images/hub/rootfs/usr/local/bin/ccgram-launch"
        ).read_text(encoding="utf-8")
        herdr_launch = (
            ROOT / "images/hub/rootfs/usr/local/bin/herdr-server-launch"
        ).read_text(encoding="utf-8")
        healthcheck = (
            ROOT / "images/hub/rootfs/usr/local/bin/hub-healthcheck"
        ).read_text(encoding="utf-8")
        self.assertIn("-- ccgram", ccgram_launch)
        self.assertNotIn("ccgram-runtime", ccgram_launch + healthcheck)
        self.assertNotIn("hub-reconcile", herdr_launch + healthcheck)
        for removed in (
            "ccgram-runtime",
            "ccgram-runtime-launch",
            "dev-session",
            "hub-reconcile",
        ):
            self.assertFalse(
                (ROOT / "images/hub/rootfs/usr/local/bin" / removed).exists()
            )

    def test_user_facing_cli_installations_are_developer_owned(self) -> None:
        workspace = (ROOT / "images/workspace/Dockerfile").read_text()
        hub = (ROOT / "images/hub/Dockerfile").read_text()
        self.assertIn("NPM_CONFIG_PREFIX=/home/developer/.local", workspace)
        self.assertIn("HERDR_INSTALL_DIR=/home/developer/.local/bin", workspace)
        self.assertIn("GH_INSTALL_DIR=/home/developer/.local/bin", workspace)
        for source in (workspace, hub):
            self.assertIn("uv tool install", source)
            self.assertIn("/ccgram/uv-receipt.toml", source)

    def test_hub_repairs_persisted_agent_directory_ownership(self) -> None:
        entrypoint = (
            ROOT / "images/hub/rootfs/usr/local/bin/hub-entrypoint"
        ).read_text()
        self.assertIn('chown -R developer:developer -- "$@"', entrypoint)
        self.assertIn('root chown -R 1000:1000 "${dirs[@]}"', SETUP)
        for path in (
            "/shared/codex",
            "/shared/claude",
            "/shared/gh",
            "/ccgram",
        ):
            self.assertIn(f'"$STATE{path}"', SETUP)

    def test_setup_has_only_explicit_agent_start(self) -> None:
        result = subprocess.run(
            [str(ROOT / "deploy/setup.sh"), "help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        for command in (
            "./setup.sh install [global options]",
            "./setup.sh create <repo>",
            "./setup.sh agent PROJECT codex|claude|shell",
            "./setup.sh update [PROJECT]",
            "./setup.sh reset-sessions",
            "./setup.sh teardown PROJECT|--all",
        ):
            self.assertIn(command, result.stdout)
        self.assertNotIn("--agent", result.stdout)
        create = SETUP[SETUP.index("create_cmd() {") : SETUP.index("project_workspace_id() {")]
        update = SETUP[SETUP.index("update_cmd() {") : SETUP.index("reset_sessions_cmd() {")]
        self.assertNotIn("start_project_agent", create + update)
        self.assertNotIn("reconcile", SETUP)
        self.assertNotIn("PROJECT_AGENT", SETUP + WORKSPACE)

    def test_agent_command_reuses_named_tab_and_runs_one_direct_process(self) -> None:
        self.assertIn("multiple Herdr workspaces match project", SETUP)
        self.assertIn("multiple $agent tabs exist for project", SETUP)
        self.assertIn(".result.workspaces[]? | select(.label == $label)", SETUP)
        self.assertIn(".result.tabs[]? | select(.label == $label)", SETUP)
        self.assertIn('"exec dev-enter $project $agent"', SETUP)
        self.assertNotIn("resume --last", SETUP)
        self.assertNotIn("--continue", SETUP)
        agent = SETUP[SETUP.index("agent_cmd() {") : SETUP.index("create_cmd() {")]
        self.assertIn('start_project_agent "$project" "$agent"', agent)
        self.assertNotIn("--pull always", agent)
        self.assertNotIn("--force-recreate", agent)

    def test_reset_sessions_is_scoped_and_recoverable(self) -> None:
        reset = SETUP[SETUP.index("reset_sessions_cmd() {") : SETUP.index("teardown_cmd() {")]
        self.assertIn('read -r -p "Type RESET to continue: "', reset)
        self.assertIn("$STATE/backups/sessions-$timestamp", reset)
        self.assertIn('root mv -- "$STATE/herdr" "$backup/herdr"', reset)
        self.assertIn('root mv -- "$STATE/ccgram" "$backup/ccgram"', reset)
        self.assertNotIn("rm -rf", reset)
        for preserved in ("projects", "shared", "ssh", "secrets"):
            self.assertNotIn(f'root mv -- "$STATE/{preserved}"', reset)
        self.assertIn('workspace_compose "$name" "$file" up -d --force-recreate', reset)
        self.assertIn("trap '", reset)
        self.assertIn("restart_telegram=false", reset)
        self.assertIn("trap - EXIT", reset)
        self.assertLess(
            reset.index('root mv -- "$STATE/ccgram"'),
            reset.index('workspace_compose "$name"'),
        )

    def test_update_handles_telegram_without_restoring_agents(self) -> None:
        update = SETUP[SETUP.index("update_cmd() {") : SETUP.index("reset_sessions_cmd() {")]
        self.assertIn("telegram_status == running", update)
        self.assertIn("$telegram_status == restarting", update)
        self.assertIn("compose_hub --profile telegram stop telegram", update)
        self.assertIn("compose_hub --profile telegram start telegram", update)
        self.assertNotIn("start_project_agent", update)
        self.assertNotIn("prepare_shared_dirs", update)

    def test_stateful_commands_check_installation_before_doing_work(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            setup = temporary / "setup.sh"
            setup.write_text(SETUP, encoding="utf-8")
            setup.chmod(0o755)
            fake_curl = temporary / "curl"
            called = temporary / "curl-called"
            fake_curl.write_text(
                '#!/bin/sh\ntouch "$CURL_CALLED"\nexit 99\n', encoding="utf-8"
            )
            fake_curl.chmod(0o755)
            environment = os.environ | {
                "CURL_CALLED": str(called),
                "PATH": f"{temporary}:{os.environ['PATH']}",
            }
            commands = (
                ("create", "https://github.com/owner/repository"),
                ("agent", "project", "codex"),
                ("update",),
                ("reset-sessions",),
                ("teardown", "project"),
                ("list",),
                ("telegram",),
                ("login", "codex"),
            )
            for command in commands:
                with self.subTest(command=command[0]):
                    result = subprocess.run(
                        [str(setup), *command],
                        check=False,
                        capture_output=True,
                        text=True,
                        env=environment,
                    )
                    self.assertEqual(result.returncode, 2)
                    self.assertIn("run './setup.sh install' first", result.stderr)
                    self.assertFalse(called.exists())

    def test_setup_validates_inputs_and_allocates_real_ports(self) -> None:
        self.assertIn("invalid Traefik entrypoint", SETUP)
        self.assertIn("invalid certificate resolver", SETUP)
        port_free = SETUP[SETUP.index("port_free() {") : SETUP.index("next_port() {")]
        self.assertIn('docker ps --filter "publish=$port"', port_free)
        self.assertIn("tcp_tables=(/proc/net/tcp)", port_free)

    def test_setup_prints_ssh_configuration(self) -> None:
        self.assertIn("Host dev-$name", SETUP)
        self.assertIn("ProxyJump <server-alias>", SETUP)

    def test_docker_socket_grants_developer_access(self) -> None:
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", WORKSPACE)
        self.assertIn('grant_docker_socket_access("developer")', WORKSPACE_ENTRYPOINT)

    def test_workspace_persistence_and_loopback_ssh(self) -> None:
        self.assertIn("/repo:${PROJECT_DIR:?set PROJECT_DIR}/repo", WORKSPACE)
        self.assertIn("/ssh-host-keys:/etc/ssh/devctl-host-keys", WORKSPACE)
        self.assertIn("/vscode-server:/home/developer/.vscode-server", WORKSPACE)
        self.assertIn('"127.0.0.1:${SSH_PORT:?set SSH_PORT}:22"', WORKSPACE)

    def test_ssh_agent_forwarding_uses_openssh_managed_socket(self) -> None:
        self.assertIn("AllowAgentForwarding yes", SSHD_CONFIG)
        self.assertNotIn("SSH_AUTH_SOCK=", SSHD_CONFIG)

    def test_http_routes_are_private_and_use_oauth(self) -> None:
        self.assertIn('- "8080"', WORKSPACE)
        self.assertIn('- "${PREVIEW_PORT:-3000}"', WORKSPACE)
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*8080:8080")
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*3000:3000")
        for route in ("code", "preview"):
            prefix = f"traefik.http.routers.devctl-${{PROJECT_NAME}}-{route}"
            self.assertIn(
                f"{prefix}.middlewares=${{TRAEFIK_AUTH_MIDDLEWARE:?set TRAEFIK_AUTH_MIDDLEWARE}}",
                WORKSPACE,
            )
            self.assertIn(f"{prefix}.tls=true", WORKSPACE)

    def test_workspace_has_only_herdr_runtime_socket(self) -> None:
        self.assertIn("/srv/devctl/herdr/run:/run/herdr:ro", WORKSPACE)
        self.assertNotIn("/srv/devctl/herdr:/srv/devctl/herdr", WORKSPACE)

    def test_workspace_exposes_urls_to_agents(self) -> None:
        self.assertIn("DEVCTL_CODE_URL", WORKSPACE)
        self.assertIn("DEVCTL_PREVIEW_URL", WORKSPACE)

    def test_telegram_is_optional(self) -> None:
        self.assertIn('profiles: ["telegram"]', HUB)
        self.assertIn("TELEGRAM_ALLOWED_USERS:-", HUB)
        self.assertIn("TELEGRAM_GROUP_ID:-", HUB)
        self.assertIn("TELEGRAM_AUTOCLOSE_DONE_MINUTES:-0", HUB)
        self.assertIn("TELEGRAM_AUTOCLOSE_DEAD_MINUTES:-0", HUB)

    def test_dev_enter_is_label_based_and_safe(self) -> None:
        result = subprocess.run(
            [str(ROOT / "images/hub/rootfs/usr/local/bin/dev-enter"), "../bad", "shell"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid project slug", result.stderr)
        self.assertIn("--filter label=devctl.managed=true", DEV_ENTER)
        self.assertIn("label=devctl.project=$slug", DEV_ENTER)
        self.assertIn('--user developer --workdir "/srv/devctl/projects/$slug/repo"', DEV_ENTER)
        self.assertIn("--env HERDR_ENV=1", DEV_ENTER)

    def test_generated_env_files_are_ignored(self) -> None:
        for path in (
            "deploy/hub.env",
            "deploy/devctl.env",
            "deploy/projects/project.env",
            "deploy/projects/.lock",
        ):
            result = subprocess.run(
                ["git", "check-ignore", "--quiet", path], cwd=ROOT, check=False
            )
            self.assertEqual(result.returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
