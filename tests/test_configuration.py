from __future__ import annotations

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

    def test_images_do_not_install_the_removed_python_cli(self) -> None:
        dockerfiles = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("images/hub/Dockerfile", "images/workspace/Dockerfile")
        )
        self.assertNotIn("COPY devctl", dockerfiles)
        self.assertNotIn("/opt/devctl", dockerfiles)


if __name__ == "__main__":
    unittest.main()
