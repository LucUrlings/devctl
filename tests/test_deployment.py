from __future__ import annotations

import asyncio
import importlib.util
from importlib.machinery import SourceFileLoader
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = (ROOT / "deploy/workspace.compose.yml").read_text(encoding="utf-8")
HUB = (ROOT / "deploy/hub.compose.yml").read_text(encoding="utf-8")
DEV_ENTER = (ROOT / "images/hub/rootfs/usr/local/bin/dev-enter").read_text(
    encoding="utf-8"
)
DEV_SESSION = (ROOT / "images/hub/rootfs/usr/local/bin/dev-session").read_text(
    encoding="utf-8"
)
HUB_RECONCILE = (ROOT / "images/hub/rootfs/usr/local/bin/hub-reconcile").read_text(
    encoding="utf-8"
)
WORKSPACE_ENTRYPOINT = (
    ROOT / "images/workspace/rootfs/usr/local/bin/workspace-entrypoint"
).read_text(encoding="utf-8")

RECONCILE_PATH = ROOT / "images/hub/rootfs/usr/local/bin/hub-reconcile"
RECONCILE_SPEC = importlib.util.spec_from_loader(
    "hub_reconcile", SourceFileLoader("hub_reconcile", str(RECONCILE_PATH))
)
assert RECONCILE_SPEC and RECONCILE_SPEC.loader
HUB_RECONCILE_MODULE = importlib.util.module_from_spec(RECONCILE_SPEC)
RECONCILE_SPEC.loader.exec_module(HUB_RECONCILE_MODULE)

CCGRAM_RUNTIME_PATH = ROOT / "images/hub/rootfs/usr/local/bin/ccgram-runtime"
CCGRAM_RUNTIME_SPEC = importlib.util.spec_from_loader(
    "ccgram_runtime", SourceFileLoader("ccgram_runtime", str(CCGRAM_RUNTIME_PATH))
)
assert CCGRAM_RUNTIME_SPEC and CCGRAM_RUNTIME_SPEC.loader
CCGRAM_RUNTIME_MODULE = importlib.util.module_from_spec(CCGRAM_RUNTIME_SPEC)
CCGRAM_RUNTIME_SPEC.loader.exec_module(CCGRAM_RUNTIME_MODULE)


class DeploymentTests(unittest.TestCase):
    def test_ccgram_prompt_correlation_survives_herdr_target_changes(self) -> None:
        module = CCGRAM_RUNTIME_MODULE
        self.assertEqual(
            module._topic_key(7, "old-target", 42, -1001),
            module._topic_key(7, "new-target", 42, -1001),
        )
        self.assertGreater(module._TELEGRAM_INJECTION_TTL_SECONDS, 60 * 60)

    def test_ccgram_uses_atomic_herdr_agent_prompt(self) -> None:
        module = CCGRAM_RUNTIME_MODULE

        class FakeError(Exception):
            pass

        class FakeManager:
            def __init__(self) -> None:
                self.calls: list[list[str]] = []
                self.fallback_calls: list[tuple[str, str]] = []

            async def send(
                self,
                window_id: str,
                text: str,
                *,
                enter: bool = True,
                literal: bool = True,
                raw: bool = False,
            ) -> bool:
                del enter, literal, raw
                self.fallback_calls.append((window_id, text))
                return True

            async def guard_session_target(self, window_id: str) -> object:
                del window_id
                composite = type("Composite", (), {"agent": "codex"})()
                return type(
                    "Record", (), {"pane_id": "w1:p2", "composite": composite}
                )()

            async def _call_ok(self, args: list[str]) -> bool:
                self.calls.append(args)
                return True

            async def _after_action_failure(self, window_id: str) -> None:
                raise AssertionError(f"unexpected failure for {window_id}")

        module._install_herdr_prompt(FakeManager, FakeError)
        manager = FakeManager()
        self.assertTrue(asyncio.run(manager.send("target", "git pull please")))
        self.assertEqual(
            manager.calls,
            [["agent", "prompt", "w1:p2", "git pull please"]],
        )
        self.assertEqual(manager.fallback_calls, [])

        self.assertTrue(
            asyncio.run(manager.send("target", "Enter", enter=False, literal=False))
        )
        self.assertEqual(manager.fallback_calls, [("target", "Enter")])

    def test_ccgram_keeps_raw_herdr_behavior_for_shell_topics(self) -> None:
        module = CCGRAM_RUNTIME_MODULE

        class FakeError(Exception):
            pass

        class FakeManager:
            def __init__(self) -> None:
                self.atomic_calls: list[list[str]] = []
                self.fallback_calls: list[tuple[str, str, bool]] = []

            async def send(
                self,
                window_id: str,
                text: str,
                *,
                enter: bool = True,
                literal: bool = True,
                raw: bool = False,
            ) -> bool:
                del enter, literal
                self.fallback_calls.append((window_id, text, raw))
                return True

            async def guard_session_target(self, window_id: str) -> object:
                del window_id
                composite = type("Composite", (), {"agent": "shell"})()
                return type(
                    "Record", (), {"pane_id": "w1:p1", "composite": composite}
                )()

            async def _call_ok(self, args: list[str]) -> bool:
                self.atomic_calls.append(args)
                return True

        module._install_herdr_prompt(FakeManager, FakeError)
        manager = FakeManager()
        self.assertTrue(asyncio.run(manager.send("shell-target", "pwd", raw=True)))
        self.assertEqual(manager.fallback_calls, [("shell-target", "pwd", True)])
        self.assertEqual(manager.atomic_calls, [])

    def test_ccgram_reports_atomic_prompt_failure(self) -> None:
        module = CCGRAM_RUNTIME_MODULE

        class FakeError(Exception):
            pass

        class FakeManager:
            def __init__(self) -> None:
                self.refreshed: list[str] = []

            async def send(self, *args: object, **kwargs: object) -> bool:
                del args, kwargs
                raise AssertionError("unexpected fallback")

            async def guard_session_target(self, window_id: str) -> object:
                del window_id
                composite = type("Composite", (), {"agent": "claude"})()
                return type(
                    "Record", (), {"pane_id": "w2:p3", "composite": composite}
                )()

            async def _call_ok(self, args: list[str]) -> bool:
                del args
                return False

            async def _after_action_failure(self, window_id: str) -> None:
                self.refreshed.append(window_id)

        module._install_herdr_prompt(FakeManager, FakeError)
        manager = FakeManager()
        self.assertFalse(asyncio.run(manager.send("claude-target", "continue")))
        self.assertEqual(manager.refreshed, ["claude-target"])

    def test_user_facing_cli_installations_are_developer_owned(self) -> None:
        dockerfile = (ROOT / "images/workspace/Dockerfile").read_text()
        hub_dockerfile = (ROOT / "images/hub/Dockerfile").read_text()
        self.assertIn("NPM_CONFIG_PREFIX=/home/developer/.local", dockerfile)
        self.assertIn("@anthropic-ai/claude-code", dockerfile)
        self.assertIn(
            "HERDR_INSTALL_DIR=/home/developer/.local/bin",
            dockerfile,
        )
        self.assertIn("GH_INSTALL_DIR=/home/developer/.local/bin", dockerfile)
        self.assertIn("chown -R developer:developer /home/developer/.local", dockerfile)
        for source in (dockerfile, hub_dockerfile):
            self.assertIn("uv tool install", source)
            self.assertIn("/ccgram/uv-receipt.toml", source)
            self.assertNotIn('"ccgram==${CCGRAM_VERSION}" \\\n+      "msgpack==', source)

    def test_ccgram_upgrade_restarts_in_its_uv_tool_environment(self) -> None:
        launcher = (
            ROOT / "images/hub/rootfs/usr/local/bin/ccgram-runtime-launch"
        ).read_text(encoding="utf-8")
        runtime = CCGRAM_RUNTIME_PATH.read_text(encoding="utf-8")
        ccgram_launch = (
            ROOT / "images/hub/rootfs/usr/local/bin/ccgram-launch"
        ).read_text(encoding="utf-8")
        self.assertIn("ccgram/bin/python", launcher)
        self.assertIn("import sys", runtime)
        self.assertIn('sys.argv[0] = "/usr/local/bin/ccgram-runtime-launch"', runtime)
        self.assertIn("ccgram-runtime-launch run", ccgram_launch)

    def test_setup_has_only_the_small_workflow(self) -> None:
        result = subprocess.run(
            [str(ROOT / "deploy/setup.sh"), "help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("./setup.sh install", result.stdout)
        self.assertIn("./setup.sh create <repo>", result.stdout)
        self.assertIn("./setup.sh agent PROJECT codex|claude|shell", result.stdout)
        self.assertIn("./setup.sh update [PROJECT]", result.stdout)
        self.assertIn("./setup.sh teardown PROJECT|--all", result.stdout)
        self.assertIn("./setup.sh list", result.stdout)
        self.assertNotIn("./setup.sh workspace", result.stdout)
        self.assertNotIn("./setup.sh hub", result.stdout)

    def test_setup_contains_ssh_output(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn("Host dev-$name", helper)
        self.assertIn("ProxyJump <server-alias>", helper)

    def test_port_allocation_checks_docker_and_linux_listeners(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        port_free = helper[helper.index("port_free() {") : helper.index("next_port() {")]
        self.assertIn('docker ps --filter "publish=$port"', port_free)
        self.assertIn("tcp_tables=(/proc/net/tcp)", port_free)
        self.assertIn("tcp_tables+=(/proc/net/tcp6)", port_free)
        self.assertIn('[[ -r /proc/net/tcp ]] || return 1', port_free)

    def test_update_and_teardown_preserve_project_data(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('DEVCTL_SETUP_REFRESHED=true exec "$HERE/setup.sh" "$@"', helper)
        self.assertIn('setup.sh?devctl_cache=$cache_bust', helper)
        self.assertIn('[[ ! -s $temporary ]]', helper)
        self.assertIn('bash -n "$temporary"', helper)
        self.assertIn('$file?devctl_cache=$cache_bust', helper)
        self.assertIn('stage_dir=$(mktemp -d "$HERE/.bundle.XXXXXX")', helper)
        self.assertLess(
            helper.index('downloaded+=("$file")'),
            helper.index('mv -- "$stage_dir/$file" "$HERE/$file"'),
        )
        self.assertIn(
            'workspace_compose "$name" "$file" up -d --pull always '
            "--force-recreate --remove-orphans",
            helper,
        )
        self.assertIn('workspace_compose "$name" "$file" down --remove-orphans', helper)
        self.assertIn('herdr workspace close "$workspace"', helper)
        teardown = helper[helper.index("teardown_cmd() {") : helper.index("login_cmd() {")]
        self.assertIn('project_workspace_id "$name" >/dev/null', teardown)
        self.assertIn('workspace=$(project_workspace_id "$name")', teardown)
        self.assertIn('"code":"workspace_not_found"', teardown)
        self.assertIn('die "could not close Herdr workspace $workspace"', teardown)
        self.assertNotIn("rm -rf", helper)

    def test_self_update_rejects_an_invalid_download_without_replacing_it(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            setup = temporary / "setup.sh"
            setup.write_bytes((ROOT / "deploy/setup.sh").read_bytes())
            setup.chmod(0o755)
            (temporary / "devctl.env").write_text("", encoding="utf-8")
            (temporary / "hub.env").write_text("", encoding="utf-8")
            original = setup.read_bytes()

            fake_curl = temporary / "curl"
            fake_curl.write_text(
                "#!/bin/sh\n"
                "while [ \"$#\" -gt 0 ]; do\n"
                "  if [ \"$1\" = -o ]; then printf '%s\\n' 'not valid bash (' > \"$2\"; exit 0; fi\n"
                "  shift\n"
                "done\n"
                "exit 1\n",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)
            result = subprocess.run(
                [str(setup), "update"],
                check=False,
                capture_output=True,
                text=True,
                env=os.environ | {"PATH": f"{temporary}:{os.environ['PATH']}"},
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("could not update setup.sh", result.stderr)
            self.assertEqual(setup.read_bytes(), original)
            self.assertFalse(any(temporary.glob(".setup.sh.*")))

    def test_update_checks_installation_before_downloading_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            setup = temporary / "setup.sh"
            setup.write_bytes((ROOT / "deploy/setup.sh").read_bytes())
            setup.chmod(0o755)
            called = temporary / "curl-called"
            fake_curl = temporary / "curl"
            fake_curl.write_text(
                "#!/bin/sh\n"
                'touch "$CURL_CALLED"\n'
                "exit 1\n",
                encoding="utf-8",
            )
            fake_curl.chmod(0o755)

            result = subprocess.run(
                [str(setup), "update"],
                check=False,
                capture_output=True,
                text=True,
                env=os.environ
                | {
                    "CURL_CALLED": str(called),
                    "PATH": f"{temporary}:{os.environ['PATH']}",
                },
            )

            self.assertEqual(result.returncode, 2)
            self.assertIn("run './setup.sh install' first", result.stderr)
            self.assertFalse(called.exists())
            for name in (
                "hub.compose.yml",
                "hub.env.example",
                "workspace.compose.yml",
                "workspace.env.example",
            ):
                self.assertFalse((temporary / name).exists())

    def test_create_is_idempotent_with_background_reconciliation(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        create = helper[helper.index("create_cmd() {") : helper.index("project_workspace_id() {")]
        self.assertIn('start_project_agent "$name" "$DEFAULT_AGENT"', create)
        self.assertIn("reconcile_now", create)
        self.assertNotIn('herdr_create "$name"', create)
        self.assertIn('[[ $agent == none ]] && return', helper)
        self.assertIn("fcntl.flock(lock, fcntl.LOCK_EX)", HUB_RECONCILE)

    def test_update_restores_agents_before_telegram(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('compose_hub --profile telegram stop telegram', helper)
        self.assertIn('start_project_agent "$name" "$agent"', helper)
        restore = helper.index('start_project_agent "$name" "$agent"')
        restart = helper.index(
            'compose_hub --profile telegram up -d --pull always '
            '--force-recreate telegram'
        )
        self.assertLess(restore, restart)

    def test_project_update_does_not_upgrade_or_restart_a_stopped_hub_profile(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn("ps --all --quiet telegram", helper)
        self.assertIn("telegram_status == running || $telegram_status == created", helper)
        self.assertIn('[[ $telegram_status != running ]] || compose_hub --profile telegram stop telegram', helper)
        self.assertIn('compose_hub --profile telegram start telegram', helper)
        self.assertIn('compose_hub start herdr', helper)
        self.assertIn('compose_hub up -d --pull missing herdr', helper)
        project_update = helper[
            helper.index("if [[ $update_hub == false ]]") : helper.index(
                'wait_healthy devctl-hub'
            )
        ]
        self.assertNotIn("--pull always", project_update)
        self.assertNotIn("--force-recreate", project_update)

    def test_telegram_settings_are_updated_atomically(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('set_env_value "$HERE/hub.env" TELEGRAM_ALLOWED_USERS "$users"', helper)
        self.assertIn('set_env_value "$HERE/hub.env" TELEGRAM_GROUP_ID "$group"', helper)
        self.assertNotIn("sed -i.bak", helper)

    def test_agent_command_uses_labels_and_reuses_named_tab(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn("multiple Herdr workspaces match project", helper)
        self.assertIn("multiple $agent tabs exist for project", helper)
        self.assertIn(".result.workspaces[]? | select(.label == $label)", helper)
        self.assertIn(".result.tabs[]? | select(.label == $label)", helper)
        agent_function = helper[helper.index("agent_cmd() {") : helper.index("create_cmd() {")]
        self.assertIn('start workspace', agent_function)
        self.assertNotIn('--pull always', agent_function)
        self.assertNotIn('--force-recreate', agent_function)
        self.assertLess(
            agent_function.index('set_project_agent "$file" "$agent"'),
            agent_function.index('container=$(workspace_compose'),
        )

    def test_setup_waits_for_herdr_panes_and_agent(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('wait_pane_shell "$pane"', helper)
        self.assertIn('wait_pane_shell "$tab_pane"', helper)
        self.assertIn('wait_agent "$tab_pane"', helper)

    def test_setup_validates_generated_shell_config_values(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('invalid Traefik entrypoint', helper)
        self.assertIn('invalid certificate resolver', helper)

    def test_docker_socket_grants_developer_group_access(self) -> None:
        self.assertIn('grant_docker_socket_access("developer")', WORKSPACE_ENTRYPOINT)

    def test_workspace_persistence_and_loopback_ssh(self) -> None:
        self.assertIn("/repo:${PROJECT_DIR:?set PROJECT_DIR}/repo", WORKSPACE)
        self.assertIn("/ssh-host-keys:/etc/ssh/devctl-host-keys", WORKSPACE)
        self.assertIn("/vscode-server:/home/developer/.vscode-server", WORKSPACE)
        self.assertIn('"127.0.0.1:${SSH_PORT:?set SSH_PORT}:22"', WORKSPACE)

    def test_http_ports_are_not_published(self) -> None:
        self.assertIn('- "8080"', WORKSPACE)
        self.assertIn('- "${PREVIEW_PORT:-3000}"', WORKSPACE)
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*8080:8080")
        self.assertNotRegex(WORKSPACE, r"ports:[\s\S]*3000:3000")

    def test_traefik_routes_use_oauth_and_tls(self) -> None:
        for route in ("code", "preview"):
            prefix = f"traefik.http.routers.devctl-${{PROJECT_NAME}}-{route}"
            self.assertIn(f"{prefix}.middlewares=${{TRAEFIK_AUTH_MIDDLEWARE:?set TRAEFIK_AUTH_MIDDLEWARE}}", WORKSPACE)
            self.assertIn(f"{prefix}.tls=true", WORKSPACE)
            self.assertIn(f"{prefix}.tls.certresolver=${{TRAEFIK_CERT_RESOLVER:-}}", WORKSPACE)

    def test_workspace_has_socket_but_no_herdr_state(self) -> None:
        self.assertIn("/var/run/docker.sock:/var/run/docker.sock", WORKSPACE)
        self.assertIn("/srv/devctl/herdr/run:/run/herdr:ro", WORKSPACE)
        self.assertNotIn("/srv/devctl/herdr:/srv/devctl/herdr", WORKSPACE)
        self.assertIn(
            "/srv/devctl/shared/codex:/srv/devctl/shared/codex:ro", WORKSPACE
        )
        self.assertIn(
            "/srv/devctl/shared/claude:/srv/devctl/shared/claude:ro", WORKSPACE
        )

    def test_workspace_exposes_routes_to_agents(self) -> None:
        self.assertIn("HOME: /home/developer", WORKSPACE)
        self.assertIn("DEVCTL_CODE_URL: https://${PROJECT_NAME}.code.${BASE_DOMAIN:?set BASE_DOMAIN}", WORKSPACE)
        self.assertIn("DEVCTL_PREVIEW_URL: https://${PROJECT_NAME}.dev.${BASE_DOMAIN:?set BASE_DOMAIN}", WORKSPACE)

    def test_readme_documents_preview_listener_binding(self) -> None:
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("listen on `0.0.0.0:<port>`", readme)

    def test_telegram_is_optional(self) -> None:
        self.assertIn('profiles: ["telegram"]', HUB)
        self.assertIn("TELEGRAM_ALLOWED_USERS:-", HUB)
        self.assertIn("TELEGRAM_GROUP_ID:-", HUB)
        self.assertIn("TELEGRAM_AUTOCLOSE_DONE_MINUTES:-0", HUB)
        self.assertIn("TELEGRAM_AUTOCLOSE_DEAD_MINUTES:-0", HUB)

    def test_telegram_healthcheck_tracks_the_compatibility_runtime(self) -> None:
        healthcheck = (
            ROOT / "images/hub/rootfs/usr/local/bin/hub-healthcheck"
        ).read_text(encoding="utf-8")
        self.assertIn("ccgram-runtime run", healthcheck)
        self.assertNotIn("'(^|/)ccgram run($| )'", healthcheck)

    def test_agent_pane_uses_persistent_resuming_session(self) -> None:
        helper = (ROOT / "deploy/setup.sh").read_text(encoding="utf-8")
        self.assertIn('"exec dev-session $project $agent $mode"', helper)
        self.assertIn('"exec dev-enter $project shell"', helper)
        self.assertIn("export HERDR_AGENT=$agent", DEV_SESSION)
        self.assertIn('dev-enter "$slug" "$agent" resume --last', DEV_SESSION)
        self.assertIn('dev-enter "$slug" "$agent" --continue', DEV_SESSION)
        self.assertIn("elif [[ $was_resume == true ]]", DEV_SESSION)
        self.assertIn("while true", DEV_SESSION)
        self.assertIn("[[ $mode == resume ]] && resume=true", DEV_SESSION)
        self.assertIn("[[ $status -eq 75 || $running_count -ne 1 ]]", DEV_SESSION)
        self.assertIn("resume_failures >= 3", DEV_SESSION)

    def test_agent_resume_survives_temporary_workspace_unavailability(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            log = temporary / "calls"
            marker = temporary / "first-call"
            fake_enter = temporary / "dev-enter"
            fake_enter.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >> "$AUDIT_LOG"\n'
                'if [ ! -e "$AUDIT_MARKER" ]; then : > "$AUDIT_MARKER"; exit 75; fi\n'
                "sleep 30\n",
                encoding="utf-8",
            )
            fake_docker = temporary / "docker"
            fake_docker.write_text("#!/bin/sh\nprintf '%s\\n' container-id\n", encoding="utf-8")
            fake_enter.chmod(0o755)
            fake_docker.chmod(0o755)
            environment = os.environ | {
                "AUDIT_LOG": str(log),
                "AUDIT_MARKER": str(marker),
                "DEV_SESSION_RESTART_DELAY": "0",
                "PATH": f"{temporary}:{os.environ['PATH']}",
            }
            process = subprocess.Popen(
                [str(ROOT / "images/hub/rootfs/usr/local/bin/dev-session"), "audit", "codex", "resume"],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
                    if len(calls) >= 2:
                        break
                    time.sleep(0.05)
                self.assertGreaterEqual(len(calls), 2)
                self.assertEqual(calls[:2], ["audit codex resume --last"] * 2)
            finally:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=3)

    def test_agent_requires_repeated_resume_failures_before_clean_launch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            log = temporary / "calls"
            fake_enter = temporary / "dev-enter"
            fake_enter.write_text(
                "#!/bin/sh\n"
                'printf "%s\\n" "$*" >> "$AUDIT_LOG"\n'
                "exit 1\n",
                encoding="utf-8",
            )
            fake_docker = temporary / "docker"
            fake_docker.write_text("#!/bin/sh\nprintf '%s\\n' container-id\n", encoding="utf-8")
            fake_enter.chmod(0o755)
            fake_docker.chmod(0o755)
            environment = os.environ | {
                "AUDIT_LOG": str(log),
                "DEV_SESSION_RESTART_DELAY": "0",
                "PATH": f"{temporary}:{os.environ['PATH']}",
            }
            process = subprocess.Popen(
                [str(ROOT / "images/hub/rootfs/usr/local/bin/dev-session"), "audit", "codex", "resume"],
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 3
                while time.monotonic() < deadline:
                    calls = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
                    if len(calls) >= 4:
                        break
                    time.sleep(0.05)
                self.assertGreaterEqual(len(calls), 4)
                self.assertEqual(calls[:3], ["audit codex resume --last"] * 3)
                self.assertEqual(calls[3], "audit codex")
            finally:
                process.terminate()
                process.wait(timeout=3)

    def test_hub_restart_reconciles_workspace_panes_before_health(self) -> None:
        entrypoint = (ROOT / "images/hub/rootfs/usr/local/bin/hub-entrypoint").read_text()
        launcher = (ROOT / "images/hub/rootfs/usr/local/bin/herdr-server-launch").read_text()
        healthcheck = (ROOT / "images/hub/rootfs/usr/local/bin/hub-healthcheck").read_text()
        self.assertIn("herdr integration install codex", entrypoint)
        self.assertIn("herdr integration install claude", entrypoint)
        self.assertEqual(entrypoint.count("herdr integration install codex"), 2)
        self.assertLess(
            entrypoint.index("ccgram hook --provider codex --install"),
            entrypoint.rindex("herdr integration install codex"),
        )
        self.assertIn("/usr/local/bin/hub-reconcile --watch", launcher)
        self.assertIn("reconciler exited unexpectedly", launcher)
        self.assertIn("STARTUP_GRACE_SECONDS = 10", HUB_RECONCILE)
        self.assertIn("STARTUP_DISCOVERY_SECONDS = 30", HUB_RECONCILE)
        self.assertIn('docker_ps.append("--all")', HUB_RECONCILE)
        self.assertIn("devctl-herdr-reconciled", healthcheck)
        self.assertIn('"--filter",\n            "label=devctl.project"', HUB_RECONCILE)
        self.assertIn('command = f"exec dev-session {slug} {label} resume"', HUB_RECONCILE)
        self.assertIn('command = f"exec dev-enter {slug} shell"', HUB_RECONCILE)
        self.assertIn("PROJECT_AGENT: ${PROJECT_AGENT:-none}", WORKSPACE)

    def test_reconciler_does_not_recreate_an_intentionally_closed_agent_tab(self) -> None:
        module = HUB_RECONCILE_MODULE
        with (
            mock.patch.object(module, "ensure_tab", return_value="shell-pane") as ensure,
            mock.patch.object(module, "launch") as launch,
            mock.patch.object(
                module,
                "herdr",
                return_value={"tabs": [{"label": "shell", "tab_id": "w1:t1"}]},
            ),
        ):
            module.reconcile_project(
                "project", "codex", [{"label": "project", "workspace_id": "w1"}]
            )
        ensure.assert_called_once_with("w1", "shell")
        launch.assert_called_once_with("shell-pane", "project", "shell")

    def test_reconciler_uses_configured_agent_when_herdr_state_is_missing(self) -> None:
        module = HUB_RECONCILE_MODULE
        with (
            mock.patch.object(module, "create_workspace", return_value=("w1", "shell-pane")),
            mock.patch.object(module, "ensure_tab", return_value="agent-pane") as ensure,
            mock.patch.object(module, "launch") as launch,
            mock.patch.object(module, "herdr", return_value={"tabs": []}),
        ):
            module.reconcile_project("project", "codex", [])
        ensure.assert_called_once_with("w1", "codex")
        self.assertEqual(
            launch.call_args_list,
            [
                mock.call("shell-pane", "project", "shell"),
                mock.call("agent-pane", "project", "codex"),
            ],
        )

    def test_reconciler_only_injects_into_an_idle_shell(self) -> None:
        module = HUB_RECONCILE_MODULE
        self.assertTrue(module.is_shell([{"name": "sh", "argv": ["/bin/sh"]}]))
        self.assertTrue(module.is_shell([{"name": "bash", "argv": ["bash", "-i"]}]))
        self.assertFalse(
            module.is_shell(
                [{"name": "bash", "argv": ["bash", "/usr/local/bin/unmanaged-task"]}]
            )
        )

    def test_failed_reconciliation_never_marks_the_hub_ready(self) -> None:
        module = HUB_RECONCILE_MODULE
        with tempfile.TemporaryDirectory() as directory:
            ready = Path(directory) / "ready"
            with (
                mock.patch.object(module, "READY_PATH", ready),
                mock.patch.object(module, "reconcile_locked", return_value=False),
                mock.patch.object(sys, "argv", ["hub-reconcile"]),
            ):
                self.assertEqual(module.main(), 1)
            self.assertFalse(ready.exists())

            with (
                mock.patch.object(module, "READY_PATH", ready),
                mock.patch.object(module, "reconcile_locked", return_value=True),
                mock.patch.object(sys, "argv", ["hub-reconcile"]),
            ):
                self.assertEqual(module.main(), 0)
            self.assertTrue(ready.exists())

    def test_reconciler_waits_for_workspace_health(self) -> None:
        module = HUB_RECONCILE_MODULE

        def result(stdout: str) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

        starting = {
            "Config": {
                "Labels": {"devctl.project": "project"},
                "Env": ["PROJECT_AGENT=codex"],
            },
            "State": {"Health": {"Status": "starting"}},
        }
        with mock.patch.object(
            module,
            "run",
            side_effect=[result("container\n"), result(f"[{json.dumps(starting)}]")],
        ):
            projects, pending = module.running_projects()
        self.assertEqual(projects, {})
        self.assertTrue(pending)

        starting["State"]["Health"]["Status"] = "healthy"
        with mock.patch.object(
            module,
            "run",
            side_effect=[result("container\n"), result(f"[{json.dumps(starting)}]")],
        ):
            projects, pending = module.running_projects()
        self.assertEqual(projects, {"project": ("container", "codex")})
        self.assertFalse(pending)
        self.assertFalse(
            module.is_shell(
                [
                    {"name": "bash", "argv": ["bash"]},
                    {"name": "sleep", "argv": ["sleep", "10"]},
                ]
            )
        )

    def test_reconciler_preserves_a_live_pre_wrapper_agent(self) -> None:
        module = HUB_RECONCILE_MODULE
        with (
            mock.patch.object(
                module,
                "foreground",
                return_value=[{"name": "codex", "argv": ["codex"]}],
            ),
            mock.patch.object(
                module,
                "herdr",
                return_value={
                    "agents": [{"pane_id": "w1:p2", "agent": "codex"}]
                },
            ) as herdr,
            mock.patch.object(module, "wait_for") as wait_for,
            mock.patch.object(module, "run") as run,
        ):
            self.assertTrue(module.launch("w1:p2", "project", "codex"))
        herdr.assert_called_once_with("agent", "list")
        wait_for.assert_not_called()
        run.assert_not_called()

    def test_reconciler_still_rejects_an_unknown_busy_process(self) -> None:
        module = HUB_RECONCILE_MODULE
        with (
            mock.patch.object(
                module,
                "foreground",
                return_value=[{"name": "python", "argv": ["python", "server.py"]}],
            ),
            mock.patch.object(module, "herdr", return_value={"agents": []}),
            mock.patch.object(module, "wait_for", return_value=False),
            mock.patch.object(module, "run") as run,
        ):
            self.assertFalse(module.launch("w1:p2", "project", "codex"))
        run.assert_not_called()

    def test_cold_start_waits_for_docker_to_start_known_workspaces(self) -> None:
        module = HUB_RECONCILE_MODULE

        def result(stdout: str) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess([], 0, stdout=stdout, stderr="")

        stopped = {
            "Config": {
                "Labels": {"devctl.project": "project"},
                "Env": ["PROJECT_AGENT=codex"],
            },
            "State": {"Running": False, "Status": "exited"},
        }
        with mock.patch.object(
            module,
            "run",
            side_effect=[result("container\n"), result(f"[{json.dumps(stopped)}]")],
        ) as run:
            projects, pending = module.running_projects(include_stopped=True)
        self.assertEqual(projects, {})
        self.assertTrue(pending)
        self.assertIn("--all", run.call_args_list[0].args[0])

    def test_dev_enter_is_label_based_and_safe(self) -> None:
        result = subprocess.run(
            [str(ROOT / "images/hub/rootfs/usr/local/bin/dev-enter"), "../bad", "shell"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("invalid project slug", result.stderr)
        self.assertIn("--filter label=devctl.managed=true", DEV_ENTER)
        self.assertIn('label=devctl.project=$slug', DEV_ENTER)
        self.assertIn('--user developer --workdir "/srv/devctl/projects/$slug/repo"', DEV_ENTER)
        self.assertIn('codex) command=(codex "$@")', DEV_ENTER)
        self.assertIn('claude) command=(claude "$@")', DEV_ENTER)
        self.assertIn("docker inspect --format", DEV_ENTER)
        self.assertIn("[[ $health != healthy ]]", DEV_ENTER)
        self.assertIn("--env HERDR_ENV=1", DEV_ENTER)
        self.assertIn("exit 75", DEV_ENTER)

    def test_generated_env_files_are_ignored(self) -> None:
        for path in ("deploy/hub.env", "deploy/devctl.env", "deploy/projects/project.env", "deploy/projects/.lock"):
            result = subprocess.run(
                ["git", "check-ignore", "--quiet", path], cwd=ROOT, check=False
            )
            self.assertEqual(result.returncode, 0, path)


if __name__ == "__main__":
    unittest.main()
