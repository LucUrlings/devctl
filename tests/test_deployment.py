from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = (ROOT / "deploy/workspace.compose.yml").read_text(encoding="utf-8")
HUB = (ROOT / "deploy/hub.compose.yml").read_text(encoding="utf-8")
DEV_ENTER = (ROOT / "images/hub/rootfs/usr/local/bin/dev-enter").read_text(
    encoding="utf-8"
)
WORKSPACE_ENTRYPOINT = (
    ROOT / "images/workspace/rootfs/usr/local/bin/workspace-entrypoint"
).read_text(encoding="utf-8")


class DeploymentTests(unittest.TestCase):
    def test_setup_has_only_the_small_workflow(self) -> None:
        result = subprocess.run(
            [str(ROOT / "deploy/setup.sh"), "help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("./setup.sh install", result.stdout)
        self.assertIn("./setup.sh create <repo>", result.stdout)
        self.assertIn("./setup.sh agent PROJECT codex|claude|shell", result.stdout)
        self.assertIn("./setup.sh update [PROJECT]", result.stdout)
        self.assertIn("./setup.sh teardown PROJECT|--all", result.stdout)
        self.assertIn("./setup.sh list", result.stdout)
        self.assertNotIn("./setup.sh workspace", result.stdout)
        self.assertNotIn("./setup.sh hub", result.stdout)

    def test_setup_contains_ssh_output(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn("Host dev-$name", helper)
        self.assertIn("ProxyJump <server-alias>", helper)

    def test_update_and_teardown_preserve_project_data(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn(
            'workspace_compose "$name" "$file" up -d --pull always '
            "--force-recreate --remove-orphans",
            helper,
        )
        self.assertIn('workspace_compose "$name" "$file" down --remove-orphans', helper)
        self.assertNotIn("rm -rf", helper)

    def test_update_restores_agents_before_telegram(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('compose_hub --profile telegram stop telegram', helper)
        self.assertIn('start_project_agent "$name" "$agent"', helper)
        restore = helper.index('start_project_agent "$name" "$agent"')
        restart = helper.index(
            'compose_hub --profile telegram up -d --pull always '
            '--force-recreate telegram'
        )
        self.assertLess(restore, restart)

    def test_agent_command_uses_labels_and_reuses_named_tab(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn("multiple Herdr workspaces match project", helper)
        self.assertIn("multiple $agent tabs exist for project", helper)
        self.assertIn(".result.workspaces[]? | select(.label == $label)", helper)
        self.assertIn(".result.tabs[]? | select(.label == $label)", helper)
        agent_function = helper[helper.index("agent_cmd() {") : helper.index("create_cmd() {")]
        self.assertIn('start workspace', agent_function)
        self.assertNotIn('--pull always', agent_function)
        self.assertNotIn('--force-recreate', agent_function)

    def test_setup_waits_for_herdr_panes_and_agent(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('wait_pane_shell "$pane"', helper)
        self.assertIn('wait_pane_shell "$tab_pane"', helper)
        self.assertIn('wait_agent "$tab_pane"', helper)

    def test_setup_validates_generated_shell_config_values(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('invalid Traefik entrypoint', helper)
        self.assertIn('invalid certificate resolver', helper)

    def test_docker_socket_grants_developer_group_access(self) -> None:
        self.assertIn('grant_docker_socket_access("developer")', WORKSPACE_ENTRYPOINT)

    def test_workspace_persistence_and_loopback_ssh(self) -> None:
        self.assertIn("/repo:${PROJECT_DIR:?set PROJECT_DIR}/repo", WORKSPACE)
        self.assertIn("/ssh-host-keys:/etc/ssh/devctl-host-keys", WORKSPACE)
        self.assertIn("/vscode-server:/home/developer/.vscode-server", WORKSPACE)
        self.assertIn('"127.0.0.1:${SSH_PORT:?set SSH_PORT}:22"', WORKSPACE)

    def test_http_ports_are_not_published(self) -> None:
        self.assertIn('- "8080"', WORKSPACE)
        self.assertIn('- "${PREVIEW_PORT:-3000}"', WORKSPACE)
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*8080:8080")
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*3000:3000")

    def test_traefik_routes_use_oauth_and_tls(self) -> None:
        for route in ("code", "preview"):
            prefix = f"traefik.http.routers.devctl-${{PROJECT_NAME}}-{route}"
            self.assertIn(f"{prefix}.middlewares=${{TRAEFIK_AUTH_MIDDLEWARE:?set TRAEFIK_AUTH_MIDDLEWARE}}", WORKSPACE)
            self.assertIn(f"{prefix}.tls=true", WORKSPACE)
            self.assertIn(f"{prefix}.tls.certresolver=${{TRAEFIK_CERT_RESOLVER:-}}", WORKSPACE)

    def test_workspace_has_socket_but_no_herdr_state(self) -> None:
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", WORKSPACE)
        self.assertIn("/srv/devctl/herdr/run:/run/herdr:ro", WORKSPACE)
        self.assertNotIn("/srv/devctl/herdr:/srv/devctl/herdr", WORKSPACE)

    def test_workspace_exposes_routes_to_agents(self) -> None:
        self.assertIn("HOME: /home/developer", WORKSPACE)
        self.assertIn("DEVCTL_CODE_URL: https://${PROJECT_NAME}.code.${BASE_DOMAIN:?set BASE_DOMAIN}", WORKSPACE)
        self.assertIn("DEVCTL_PREVIEW_URL: https://${PROJECT_NAME}.dev.${BASE_DOMAIN:?set BASE_DOMAIN}", WORKSPACE)

    def test_telegram_is_optional(self) -> None:
        self.assertIn('profiles: ["telegram"]', HUB)
        self.assertIn("TELEGRAM_ALLOWED_USERS:-", HUB)
        self.assertIn("TELEGRAM_GROUP_ID:-", HUB)
        self.assertIn("TELEGRAM_AUTOCLOSE_DONE_MINUTES:-0", HUB)
        self.assertIn("TELEGRAM_AUTOCLOSE_DEAD_MINUTES:-0", HUB)

    def test_agent_exit_status_is_left_in_the_pane(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn("[devctl] $agent exited with status", helper)

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
        self.assertIn('label=devctl.project=$slug', DEV_ENTER)
        self.assertIn('--user developer --workdir "/srv/devctl/projects/$slug/repo"', DEV_ENTER)

    def test_generated_env_files_are_ignored(self) -> None:
        for path in ("deploy/hub.env", "deploy/devctl.env", "deploy/projects/project.env", "deploy/projects/.lock"):
            result = subprocess.run(
                ["git", "check-ignore", "--quiet", path], cwd=ROOT, check=False
            )
            self.assertEqual(result.returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
