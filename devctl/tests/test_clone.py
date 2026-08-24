from pathlib import Path

import pytest

from devctl.clone import clone_command, workspace_action
from devctl.errors import DevctlError


def test_empty_workspace_clones_with_argument_array(tmp_path: Path) -> None:
    command = clone_command("https://github.com/owner/repo", tmp_path, "main", "1")
    assert command == [
        "git",
        "clone",
        "--branch",
        "main",
        "--depth",
        "1",
        "--",
        "https://github.com/owner/repo",
        str(tmp_path),
    ]
    assert workspace_action(tmp_path, "https://github.com/owner/repo", lambda: "unused") == "clone"


def test_existing_matching_clone_is_idempotently_reused(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    action = workspace_action(
        tmp_path, "https://github.com/Owner/Repo.git", lambda: "https://github.com/owner/repo"
    )
    assert action == "reuse"


def test_origin_mismatch_is_rejected(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with pytest.raises(DevctlError, match="origin mismatch"):
        workspace_action(
            tmp_path, "https://github.com/owner/expected", lambda: "https://github.com/owner/other"
        )


def test_existing_origin_cannot_hide_credentials_or_query_tokens(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    with pytest.raises(DevctlError, match="safe repository URL"):
        workspace_action(
            tmp_path,
            "https://github.com/owner/repo",
            lambda: "https://token@github.com/owner/repo",
        )
    with pytest.raises(DevctlError, match="safe repository URL"):
        workspace_action(
            tmp_path,
            "https://github.com/owner/repo",
            lambda: "https://github.com/owner/repo?token=secret",
        )


def test_non_git_data_is_never_overwritten(tmp_path: Path) -> None:
    (tmp_path / "important.txt").write_text("keep", encoding="utf-8")
    with pytest.raises(DevctlError, match="non-empty"):
        workspace_action(tmp_path, "https://github.com/owner/repo", lambda: "unused")
