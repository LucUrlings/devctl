from pathlib import Path

import pytest

from devctl.errors import DevctlError
from devctl.validation import project_path


@pytest.mark.parametrize("malicious", ["../projects2/victim", "a/b", ".", "../../srv"])
def test_purge_target_cannot_escape_project_root(tmp_path: Path, malicious: str) -> None:
    with pytest.raises(DevctlError):
        project_path(tmp_path / "projects", malicious)
