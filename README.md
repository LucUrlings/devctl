# Devctl

Docker workspaces with code-server, VS Code SSH, Herdr, Codex, Claude, and optional Telegram control.

## Quick start

Run on the Docker server. Download the setup script first:

```bash
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/setup.sh
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

Open the printed code-server URL on your phone. Add the printed SSH block to your laptop’s `~/.ssh/config`, then use `ssh dev-<project>` or VS Code Remote SSH and open `/workspace/project`.

## How it works

One hub runs the only Herdr server and optional CCGram. Each repository gets an isolated workspace. Only the hub mounts `/var/run/docker.sock` (host-equivalent control). Workspaces persist the checkout, SSH host keys, VS Code server, and shared credentials.

Traefik routes `<project>.code.<base-domain>` to code-server (`8080`) and `<project>.dev.<base-domain>` to preview (`3000` by default). Both use TLS and the configured OAuth middleware; neither HTTP port is published publicly.

## Authentication

```bash
./setup.sh login github
./setup.sh login codex
./setup.sh login claude
```

Credentials are shared from `/srv/devctl/shared`; use this only with trusted workspaces.

## Telegram (optional)

CCGram connects Telegram to the existing Herdr server. Create a BotFather bot, enable forum topics in a private supergroup, add the bot, and collect allowed numeric user IDs plus the `-100...` group ID:

```bash
./setup.sh telegram --token-file <bot-token-file> \
  --allowed-users <user-id>[,<user-id>] --group-id <-100-supergroup-id>
```

Keep the token file mode `0600`. Telegram uses long polling and an explicit allowlist.

## Docker socket opt-in

Workspaces have Docker CLI but no socket by default. For trusted repositories only, add `workspace.docker-host.override.yml` when starting the project; socket access is effectively root access to the server.

## Operations and backups

```bash
./setup.sh list
docker compose --env-file hub.env -f hub.compose.yml logs -f
```

Back up `/srv/devctl/projects`, `/srv/devctl/shared`, `/srv/devctl/herdr`, `/srv/devctl/ccgram`, `/srv/devctl/ssh`, and `/srv/devctl/secrets`.

Images: `ghcr.io/lucurlings/devctl-hub:latest` and `ghcr.io/lucurlings/devctl-workspace:latest` (amd64/arm64).
