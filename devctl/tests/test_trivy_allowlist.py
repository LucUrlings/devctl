import re
from datetime import UTC, datetime
from pathlib import Path


def test_every_trivy_exception_has_an_owner_reason_and_unexpired_date() -> None:
    allowlist = Path(__file__).resolve().parents[2] / ".trivyignore"
    previous = ""
    entries = 0
    for raw in allowlist.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            previous = ""
            continue
        if line.startswith("#"):
            previous = line
            continue
        entries += 1
        match = re.fullmatch(r"# Owner: @[^;]+; (.+); expires (\d{4}-\d{2}-\d{2})\.", previous)
        assert match is not None, f"{line} needs an adjacent owner, reason, and expiry"
        assert match.group(1).strip(), f"{line} needs a justification"
        expiry = datetime.strptime(match.group(2), "%Y-%m-%d").replace(tzinfo=UTC)
        assert expiry > datetime.now(UTC), f"{line} allowlist entry expired"
        previous = ""
    assert entries > 0
