from __future__ import annotations

import re
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
    def test_workspace_persists_ssh_identity_and_vscode_server(self) -> None:
        self.assertIn("/ssh-host-keys:/etc/ssh/devctl-host-keys", WORKSPACE)
        self.assertIn("/vscode-server:/home/developer/.vscode-server", WORKSPACE)
        self.assertIn('"127.0.0.1:${SSH_PORT:?set SSH_PORT}:22"', WORKSPACE)

    def test_http_ports_are_exposed_but_not_published(self) -> None:
        self.assertIn('- "8080"', WORKSPACE)
        self.assertIn('- "${PREVIEW_PORT:-3000}"', WORKSPACE)
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*8080:8080")
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*3000:3000")

    def test_both_traefik_routes_use_oauth_tls_and_optional_resolver(self) -> None:
        for route in ("code", "preview"):
            prefix = f"traefik.http.routers.devctl-${{PROJECT_NAME}}-{route}"
            self.assertIn(
                f"{prefix}.middlewares=${{TRAEFIK_AUTH_MIDDLEWARE:?set TRAEFIK_AUTH_MIDDLEWARE}}",
                WORKSPACE,
            )
            self.assertIn(f"{prefix}.tls=true", WORKSPACE)
            self.assertIn(
                f"{prefix}.tls.certresolver=${{TRAEFIK_CERT_RESOLVER:-}}", WORKSPACE
            )

    def test_workspace_has_no_default_docker_socket_or_herdr_state(self) -> None:
        self.assertNotIn("/var/run/docker.sock", WORKSPACE)
        self.assertIn("/srv/devctl/herdr/run:/run/herdr:ro", WORKSPACE)
        self.assertNotIn("/srv/devctl/herdr:/srv/devctl/herdr", WORKSPACE)
        override = (ROOT / "deploy/workspace.docker-host.override.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", override)

    def test_telegram_is_optional_without_required_interpolation(self) -> None:
        self.assertIn('profiles: ["telegram"]', HUB)
        self.assertIn("TELEGRAM_ALLOWED_USERS:-", HUB)
        self.assertIn("TELEGRAM_GROUP_ID:-", HUB)
        telegram = HUB.split("  telegram:", 1)[1]
        self.assertNotIn("/var/run/docker.sock", telegram)

    def test_telegram_entrypoint_rejects_missing_configuration(self) -> None:
        entrypoint = ROOT / "images/hub/rootfs/usr/local/bin/hub-entrypoint"
        result = subprocess.run(
            [str(entrypoint), "ccgram"],
            check=False,
            env={"PATH": "/usr/bin:/bin", "CCGRAM_MULTIPLEXER": "herdr"},
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("ALLOWED_USERS", result.stderr)
        self.assertIn("must have mode 0600", entrypoint.read_text(encoding="utf-8"))

    def test_dev_enter_validates_slug_and_resolves_labels(self) -> None:
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
        self.assertIn("export HERDR_AGENT=$agent", DEV_ENTER)
        self.assertRegex(DEV_ENTER, re.escape("--user developer --workdir /workspace/project"))

    def test_no_host_side_cli_or_package_installer_remains(self) -> None:
        self.assertFalse((ROOT / "devctl").exists())
        self.assertFalse((ROOT / "scripts/devctl-host").exists())
        self.assertFalse((ROOT / ".github/workflows/release.yml").exists())


if __name__ == "__main__":
    unittest.main()
