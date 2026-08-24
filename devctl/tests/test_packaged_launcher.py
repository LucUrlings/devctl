import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LAUNCHER = (ROOT / "scripts/devctl-host").read_text(encoding="utf-8")


def payload(function: str) -> list[str]:
    block = LAUNCHER.split(f"{function}() {{", 1)[1].split("\n}", 1)[0]
    return re.findall(r"^\s+'([^']*)'", block, re.MULTILINE)


def active_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line and not line.startswith("#")]


def test_packaged_launcher_embeds_the_validated_hub_compose() -> None:
    source = (ROOT / "compose/hub.compose.yml").read_text(encoding="utf-8")
    assert active_lines("\n".join(payload("write_compose"))) == active_lines(source)


def test_packaged_launcher_embeds_every_example_configuration_value() -> None:
    source = (ROOT / "config/devctl.example.env").read_text(encoding="utf-8")
    expected = {line for line in active_lines(source) if "=" in line}
    generated = {line for line in payload("write_config") if "=" in line}
    assert generated == expected


def test_packaged_launcher_requires_no_server_repository_checkout() -> None:
    assert "git clone" not in LAUNCHER
    assert "/srv/devctl/scripts" not in LAUNCHER
    assert "--filter label=devctl.role=hub" in LAUNCHER
    assert "--filter label=devctl.managed=true" in LAUNCHER


def test_telegram_guidance_does_not_reference_a_server_checkout() -> None:
    cli = (ROOT / "devctl/src/devctl/cli.py").read_text(encoding="utf-8")
    assert "scripts/install.sh" not in cli
