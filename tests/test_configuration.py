from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class ConfigurationTests(unittest.TestCase):
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

    def test_images_do_not_install_the_removed_python_cli(self) -> None:
        dockerfiles = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("images/hub/Dockerfile", "images/workspace/Dockerfile")
        )
        self.assertNotIn("COPY devctl", dockerfiles)
        self.assertNotIn("/opt/devctl", dockerfiles)


if __name__ == "__main__":
    unittest.main()
