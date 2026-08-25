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
        self.assertIn("./setup.sh list", result.stdout)
        self.assertNotIn("./setup.sh workspace", result.stdout)
        self.assertNotIn("./setup.sh hub", result.stdout)

    def test_setup_contains_ssh_output(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn("Host dev-$name", helper)
        self.assertIn("ProxyJump <server-alias>", helper)

    def test_workspace_persistence_and_loopback_ssh(self) -> None:
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

    def test_workspace_has_no_default_socket_or_herdr_state(self) -> None:
        self.assertNotIn("/var/run/docker.sock", WORKSPACE)
        self.assertIn("/srv/devctl/herdr/run:/run/herdr:ro", WORKSPACE)
        self.assertNotIn("/srv/devctl/herdr:/srv/devctl/herdr", WORKSPACE)
        override = (ROOT / "deploy/workspace.docker-host.override.yml").read_text(encoding="utf-8")
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", override)

    def test_telegram_is_optional(self) -> None:
        self.assertIn('profiles: ["telegram"]', HUB)
        self.assertIn("TELEGRAM_ALLOWED_USERS:-", HUB)
        self.assertIn("TELEGRAM_GROUP_ID:-", HUB)

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
        self.assertIn("--user developer --workdir /workspace/project", DEV_ENTER)

    def test_generated_env_files_are_ignored(self) -> None:
        for path in ("deploy/hub.env", "deploy/devctl.env", "deploy/projects/project.env", "deploy/projects/.lock"):
            result = subprocess.run(
                ["git", "check-ignore", "--quiet", path], cwd=ROOT, check=False
            )
            self.assertEqual(result.returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
