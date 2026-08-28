# Devctl

Docker workspaces with code-server, VS Code SSH, Herdr, Codex, Claude, and optional Telegram control.

## Quick start

Run on the Docker server. Download the setup script first:

Requires Docker Compose plus an existing Traefik network and OAuth middleware. Point wildcard DNS for `*.code.<base-domain>` and `*.dev.<base-domain>` at the server.

```bash
curl -fsSL "https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/setup.sh?$(date +%s)" -o setup.sh
chmod +x setup.sh
```

Then run:

```bash
./setup.sh install --agent codex \
  --base-domain <base-domain> \
  --traefik-network <traefik-network> \
  --auth-middleware <oauth-middleware>
./setup.sh create <repo>
```

The first command starts the hub. The second safely clones a repository, starts its workspace, creates its Herdr tabs, starts the agent, and prints URLs plus SSH config. Repeat `./setup.sh create <repo>` for more projects.

The preview route uses port `3000` by default. Pass the port your frontend listens on when it differs:

```bash
./setup.sh create <repo> --preview-port <port>
```

The development server must listen on `0.0.0.0:<port>` inside the workspace. A server bound only to `localhost` cannot be reached by Traefik.

Open the printed code-server URL on your phone. Add the printed SSH block to your laptop’s `~/.ssh/config`, then use `ssh dev-<project>` or VS Code Remote SSH and open `/workspace/project`.

## How it works

One hub runs the only Herdr server and optional CCGram. Each repository gets an isolated workspace. Workspaces persist the checkout, SSH host keys, VS Code server, and shared credentials.

Traefik routes `<project>.code.<base-domain>` to code-server (`8080`) and `<project>.dev.<base-domain>` to preview (`3000` by default). Both use TLS and the configured OAuth middleware; neither HTTP port is published publicly.

Inside the workspace and its Codex/Claude sessions, `DEVCTL_CODE_URL` and `DEVCTL_PREVIEW_URL` contain those exact URLs.

## Authentication

```bash
./setup.sh login github
./setup.sh login codex
./setup.sh login claude
```

Credentials are shared from `/srv/devctl/shared`; use this only with trusted workspaces.

## Telegram (optional)

CCGram connects Telegram to the existing Herdr server. Create a BotFather bot, enable forum topics in a private supergroup, and add the bot as an administrator with **Manage Topics**. Disable the bot's Group Privacy in BotFather, then collect allowed numeric user IDs plus the `-100...` group ID:

```bash
./setup.sh telegram --token-file <bot-token-file> \
  --allowed-users <user-id>[,<user-id>] --group-id <-100-supergroup-id>
```

Keep the token file mode `0600`. Telegram uses long polling and an explicit allowlist. Automatic done/dead topic deletion is disabled. Devctl also keeps the Herdr session wrapper alive: if Codex or Claude exits unexpectedly, it restarts and resumes the latest conversation in that project instead of leaving the Telegram topic at `/`. If a workspace is temporarily stopped or recreated, the wrapper waits for it and keeps resume mode instead of opening a fresh conversation.

After a hub-container restart or full server reboot, the hub automatically reconnects restored Herdr shell and agent tabs. Agent entry waits for each workspace to finish clone/origin validation and become healthy; Telegram remains gated until every discovered project has reattached successfully. Codex and Claude then resume their latest project conversation before Telegram begins tracking the restored sessions. Official Herdr hooks publish stable agent-session identities so CCGram can retain the existing topic binding across a recreated pane terminal.

CCGram automatically creates one topic per active Herdr agent. Codex or Claude may show first-run update, repository-trust, or hook-trust prompts before the topic becomes ready; review those prompts rather than automatically accepting them.

For an older topic that was already stale before this behavior was installed, recover it once on the Docker server:

```bash
./setup.sh agent <project> codex
```

Use the newly created project topic. A Telegram screen showing `Select Working Directory` with `Current: /` means the old topic is unbound and browsing inside the hub container; do not use it to start a project agent. `/sync` → **Fix** cleans up stale bindings and may close their old topics—it does not reconnect them.

If Telegram shows the entire Codex terminal or `SessionStart hook (failed) ... code 127`, run `./setup.sh update` and then `./setup.sh agent <project> codex`. The update restores the native Herdr session hook inside every workspace.

## Docker access

Every workspace has Docker CLI and the host Docker socket, so its agent can start development containers. Docker socket access is effectively root access to the server: only create workspaces for repositories and agents you trust.

The checkout is mounted at the same `/srv/devctl/projects/<project>/repo` path on the host and in the workspace, allowing relative bind mounts from nested Compose projects to work. `/workspace/project` remains a compatibility link for VS Code and SSH.

## Operations and backups

```bash
./setup.sh list
./setup.sh update              # Update hub and every workspace
./setup.sh update <project>    # Update one workspace; leave the hub unchanged
./setup.sh agent <project> codex
./setup.sh teardown <project>  # Stop one project and close its live Herdr workspace
./setup.sh teardown --all      # Remove all containers, including the hub
docker compose --env-file hub.env -f hub.compose.yml logs -f
```

After confirming the folder was installed, update refreshes `setup.sh` and the deployment bundle. Update and teardown preserve repositories, shared credentials, SSH host keys, VS Code state, project env files, and agent conversation history. Single-project teardown also closes that project's live Herdr workspace so it cannot keep retrying against a stopped container; `./setup.sh agent <project> codex|claude|shell` recreates it later. Update pauses Telegram, recreates the requested containers, restores each configured agent in its existing Herdr tab, and then resumes Telegram.

Codex and Claude may update themselves when you accept their update prompts. Codex, Claude, GitHub CLI, and the workspace Herdr CLI are installed under the non-root `developer` user. In-container changes survive normal restarts; recreating the workspace uses the pinned versions from the newly pulled image. The central Herdr server remains image-managed and is upgraded by `./setup.sh update`.

Back up `/srv/devctl/projects`, `/srv/devctl/shared`, `/srv/devctl/herdr`, `/srv/devctl/ccgram`, `/srv/devctl/ssh`, and `/srv/devctl/secrets`.

Images: `ghcr.io/lucurlings/devctl-hub:latest` and `ghcr.io/lucurlings/devctl-workspace:latest` (amd64/arm64).
