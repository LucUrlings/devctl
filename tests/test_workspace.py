from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "images/workspace/rootfs/usr/local/lib/devctl_workspace.py"
SPEC = importlib.util.spec_from_file_location("devctl_workspace", MODULE_PATH)
assert SPEC and SPEC.loader
workspace = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(workspace)


class WorkspaceCloneTests(unittest.TestCase):
    def test_project_slug_is_strict(self) -> None:
        self.assertEqual(workspace.validate_slug("project-one"), "project-one")
        for unsafe in ("", "Upper", "../bad", "bad_name", "a" * 42):
            with self.assertRaises(workspace.WorkspaceError):
                workspace.validate_slug(unsafe)

    def test_https_url_is_normalized_without_credentials(self) -> None:
        self.assertEqual(
            workspace.normalize_repo_url("https://GitHub.com/Owner/Repo.git/"),
            "https://github.com/Owner/Repo.git",
        )
        for unsafe in (
            "https://token@github.com/owner/repo",
            "https://github.com/owner/repo?token=secret",
            "git@github.com:owner/repo.git",
            "https://github.com /owner/repo",
        ):
            with self.assertRaises(workspace.WorkspaceError):
                workspace.normalize_repo_url(unsafe)

    def test_clone_uses_an_argument_array_and_operand_separator(self) -> None:
        command = workspace.clone_command(
            "https://github.com/owner/repo", Path("/workspace/project"), "main", "1"
        )
        self.assertEqual(
            command,
            [
                "git",
                "clone",
                "--branch",
                "main",
                "--depth",
                "1",
                "--",
                "https://github.com/owner/repo",
                "/workspace/project",
            ],
        )

    def test_empty_workspace_clones(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                workspace.workspace_action(
                    Path(directory), "https://github.com/owner/repo", lambda: "unused"
                ),
                "clone",
            )

    def test_existing_matching_clone_is_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            self.assertEqual(
                workspace.workspace_action(
                    root,
                    "https://github.com/Owner/Repo.git",
                    lambda: "https://github.com/owner/repo",
                ),
                "reuse",
            )

    def test_origin_mismatch_and_non_git_data_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".git").mkdir()
            with self.assertRaisesRegex(workspace.WorkspaceError, "origin mismatch") as error:
                workspace.workspace_action(
                    root,
                    "https://github.com/owner/expected",
                    lambda: "https://github.com/owner/other",
                )
            self.assertNotIn("other", str(error.exception))
            with self.assertRaises(workspace.WorkspaceError) as credential_error:
                workspace.workspace_action(
                    root,
                    "https://github.com/owner/expected",
                    lambda: "https://secret@github.com/owner/other",
                )
            self.assertNotIn("secret", str(credential_error.exception))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(workspace.WorkspaceError, "non-empty"):
                workspace.workspace_action(
                    root, "https://github.com/owner/repo", lambda: "unused"
                )

    def test_unsafe_branch_and_depth_are_rejected(self) -> None:
        with self.assertRaises(workspace.WorkspaceError):
            workspace.clone_command(
                "https://github.com/owner/repo", Path("/workspace/project"), "--evil"
            )
        with self.assertRaises(workspace.WorkspaceError):
            workspace.clone_command(
                "https://github.com/owner/repo", Path("/workspace/project"), depth="0"
            )


if __name__ == "__main__":
    unittest.main()
