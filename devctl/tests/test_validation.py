from pathlib import Path

import pytest

from devctl.errors import DevctlError
from devctl.validation import (
    derive_slug,
    normalize_repo_url,
    project_path,
    validate_ref,
    validate_slug,
)


@pytest.mark.parametrize("slug", ["a", "project-one", "project-42", "a" * 41])
def test_valid_slugs(slug: str) -> None:
    assert validate_slug(slug) == slug


@pytest.mark.parametrize("slug", ["", "UPPER", "-bad", "bad_thing", "a" * 42, "../escape"])
def test_invalid_slugs(slug: str) -> None:
    with pytest.raises(DevctlError):
        validate_slug(slug)


def test_repo_url_is_normalized_without_embedding_credentials() -> None:
    assert (
        normalize_repo_url("https://GitHub.com/Owner/Repo.git/")
        == "https://github.com/Owner/Repo.git"
    )
    with pytest.raises(DevctlError):
        normalize_repo_url("https://token@github.com/owner/repo")
    with pytest.raises(DevctlError):
        normalize_repo_url("https://github.com /owner/repo")
    with pytest.raises(DevctlError):
        normalize_repo_url("https://github.com:invalid/owner/repo")
    with pytest.raises(DevctlError):
        normalize_repo_url("https://[invalid/owner/repo")


def test_ssh_requires_explicit_enablement() -> None:
    with pytest.raises(DevctlError):
        normalize_repo_url("git@github.com:owner/repo.git")
    assert normalize_repo_url("git@github.com:owner/repo.git", allow_ssh=True).endswith("repo.git")


def test_slug_derivation_and_ref_safety() -> None:
    assert derive_slug("https://github.com/example/project-one.git") == "project-one"
    assert validate_ref("feature/safe-name") == "feature/safe-name"
    with pytest.raises(DevctlError):
        validate_ref("--upload-pack=evil")


def test_project_path_cannot_escape(tmp_path: Path) -> None:
    assert project_path(tmp_path, "safe") == tmp_path / "safe"
    with pytest.raises(DevctlError):
        project_path(tmp_path, "../escape")
