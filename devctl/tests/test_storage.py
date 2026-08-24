from pathlib import Path

import pytest

from devctl.errors import DevctlError
from devctl.storage import (
    allocate_and_reserve_port,
    allocate_port,
    atomic_json,
    load_json,
    release_port,
    reserve_port,
    upsert_env,
)


def test_metadata_persistence_is_atomic(tmp_path: Path) -> None:
    target = tmp_path / "project" / "metadata.json"
    atomic_json(target, {"project": "project-one", "ssh_port": 22001})
    assert load_json(target) == {"project": "project-one", "ssh_port": 22001}
    assert target.stat().st_mode & 0o777 == 0o600


def test_upsert_env_replaces_once_and_preserves_other_lines(tmp_path: Path) -> None:
    target = tmp_path / "devctl.env"
    target.write_text("# comment\nCCGRAM_ENABLED=false\nBASE_DOMAIN=example.test\n")
    upsert_env(target, "CCGRAM_ENABLED", "true")
    assert target.read_text() == ("# comment\nCCGRAM_ENABLED=true\nBASE_DOMAIN=example.test\n")
    assert target.stat().st_mode & 0o777 == 0o600


def test_port_allocation_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("devctl.storage.port_available", lambda _port: True)
    first = allocate_port(tmp_path, 22000, 22002)
    reserve_port(tmp_path, "one", first)
    second = allocate_port(tmp_path, 22000, 22002)
    assert (first, second) == (22000, 22001)
    reserve_port(tmp_path, "two", second)
    release_port(tmp_path, "one")
    assert allocate_port(tmp_path, 22000, 22002) == 22000


def test_port_selection_and_reservation_are_one_operation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("devctl.storage.port_available", lambda _port: True)
    first = allocate_and_reserve_port(tmp_path, "one", 22000, 22002)
    second = allocate_and_reserve_port(tmp_path, "two", 22000, 22002)
    assert (first, second) == (22000, 22001)
    assert load_json(tmp_path / "state" / "ports.json") == {
        "allocations": {"one": 22000, "two": 22001}
    }


def test_requested_port_collision_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("devctl.storage.port_available", lambda _port: True)
    reserve_port(tmp_path, "one", 22001)
    with pytest.raises(DevctlError):
        allocate_port(tmp_path, 22000, 22002, 22001)
