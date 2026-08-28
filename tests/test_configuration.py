from __future__ import annotations

from datetime import date
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
    def test_version_pins_stay_synchronized(self) -> None:
        versions = dict(
            line.split("=", 1)
            for line in (ROOT / "versions.env").read_text(encoding="utf-8").splitlines()
            if line and not line.startswith("#") and "=" in line
        )
        bake = (ROOT / "docker-bake.hcl").read_text(encoding="utf-8")
        hub = (ROOT / "images/hub/Dockerfile").read_text(encoding="utf-8")
        workspace = (ROOT / "images/workspace/Dockerfile").read_text(encoding="utf-8")
        bake_pins = dict(
            re.findall(r'^\s+([A-Z][A-Z0-9_]+) = "([^"]+)"$', bake, re.MULTILINE)
        )
        self.assertTrue(bake_pins)
        for name, value in bake_pins.items():
            self.assertEqual(versions[name], value, name)
        for dockerfile in (hub, workspace):
            for name, value in re.findall(
                r"^ARG ([A-Z][A-Z0-9_]+)=([^\s]+)$", dockerfile, re.MULTILINE
            ):
                if name in versions:
                    self.assertEqual(versions[name], value, name)

    def test_third_party_actions_use_full_commit_shas(self) -> None:
        workflows = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ROOT / ".github/workflows").glob("*.yml")
        )
        revisions = re.findall(r"^\s*uses:\s*[^./][^@\s]*@([^\s#]+)", workflows, re.MULTILINE)
        self.assertTrue(revisions)
        for revision in revisions:
            self.assertRegex(revision, r"^[0-9a-f]{40}$")

    def test_only_two_images_are_published(self) -> None:
        workflow = (ROOT / ".github/workflows/containers.yml").read_text(encoding="utf-8")
        self.assertIn("matrix:\n        image: [hub, workspace]", workflow)
        self.assertNotIn("release asset", workflow.lower())
        self.assertNotIn("package-release", workflow)

    def test_ci_does_not_duplicate_pull_request_builds(self) -> None:
        workflows = ROOT / ".github/workflows"
        self.assertFalse((workflows / "test.yml").exists())
        self.assertFalse((workflows / "_test.yml").exists())
        containers = (workflows / "containers.yml").read_text(encoding="utf-8")
        self.assertIn("if: github.event_name != 'pull_request'", containers)

    def test_publish_permissions_are_not_granted_to_test_jobs(self) -> None:
        workflow = (ROOT / ".github/workflows/containers.yml").read_text(encoding="utf-8")
        workflow_permissions = workflow[
            workflow.index("permissions:") : workflow.index("concurrency:")
        ]
        self.assertIn("contents: read", workflow_permissions)
        self.assertNotIn("packages: write", workflow_permissions)
        self.assertNotIn("attestations: write", workflow_permissions)
        self.assertNotIn("id-token: write", workflow_permissions)

        publish = workflow[workflow.index("  publish:") :]
        self.assertIn("packages: write", publish)
        self.assertIn("attestations: write", publish)
        self.assertIn("id-token: write", publish)

    def test_images_do_not_install_the_removed_python_cli(self) -> None:
        dockerfiles = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("images/hub/Dockerfile", "images/workspace/Dockerfile")
        )
        self.assertNotIn("COPY devctl", dockerfiles)
        self.assertNotIn("/opt/devctl", dockerfiles)

    def test_images_remove_the_unused_system_npm_copy(self) -> None:
        for path in ("images/hub/Dockerfile", "images/workspace/Dockerfile"):
            dockerfile = (ROOT / path).read_text(encoding="utf-8")
            self.assertIn("rm -rf /usr/local/lib/node_modules/npm", dockerfile)
            self.assertIn("rm -f /usr/local/bin/npm /usr/local/bin/npx", dockerfile)

    def test_security_scans_the_image_published_by_workflow_run(self) -> None:
        workflow = (ROOT / ".github/workflows/security.yml").read_text(encoding="utf-8")
        self.assertIn("PUBLISHED_SHA: ${{ github.event.workflow_run.head_sha }}", workflow)
        self.assertIn('echo "value=sha-${PUBLISHED_SHA:0:7}"', workflow)
        self.assertIn(
            ":${{ steps.image-tag.outputs.value }}",
            workflow,
        )

    def test_docker_build_context_excludes_runtime_secrets_and_state(self) -> None:
        ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()
        for pattern in (
            ".env",
            "**/.env",
            "**/hub.env",
            "**/devctl.env",
            "**/*.local.env",
            "**/secrets",
            "**/projects",
        ):
            self.assertIn(pattern, ignored)

    def test_vulnerability_exceptions_are_owned_justified_and_unexpired(self) -> None:
        lines = (ROOT / ".trivyignore").read_text(encoding="utf-8").splitlines()
        findings = 0
        for index, line in enumerate(lines):
            if not line or line.startswith("#"):
                continue
            findings += 1
            self.assertRegex(line, r"^(CVE-\d{4}-\d+|GHSA-[0-9a-z-]+)$")
            self.assertGreater(index, 0)
            justification = re.fullmatch(
                r"# Owner: @[^;]+; .+; expires (\d{4}-\d{2}-\d{2})\.",
                lines[index - 1],
            )
            self.assertIsNotNone(justification, line)
            assert justification is not None
            self.assertGreaterEqual(
                date.fromisoformat(justification.group(1)),
                date.today(),
                line,
            )
        self.assertGreater(findings, 0)


if __name__ == "__main__":
    unittest.main()
