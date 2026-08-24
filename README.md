# Devctl

Persistent Docker workspaces with code-server, VS Code Remote SSH, Herdr, Codex, Claude Code, and optional Telegram control.

## Quick start

Run on the Docker server:

```bash
./setup.sh install --agent codex \
  --base-domain <base-domain> \
  --traefik-network <traefik-network> \
  --auth-middleware <oauth-middleware>
./setup.sh create <repo>
```

`create` derives the project name, allocates an SSH port, clones the repository, starts the workspace, creates its Herdr workspace, and starts the selected agent. Run it again for more repositories.

Use the printed code-server URL from a phone. Add the printed SSH block to your laptop’s `~/.ssh/config` for VS Code Remote SSH.

## Architecture

One hub container runs the only Herdr server and optional CCGram. Every repository gets an isolated workspace container. Only the hub receives `/var/run/docker.sock`, which grants host-equivalent Docker control.

Workspaces persist repositories, SSH host keys, VS Code server data, and shared agent authentication. Restarting them preserves the checkout and SSH identity.

Traefik routes `<project>.code.<base-domain>` to code-server port `8080` and `<project>.dev.<base-domain>` to the preview port (default `3000`). Both use TLS and the configured OAuth middleware. Neither HTTP port is published publicly.

## Authentication

Authenticate once when needed:

```bash
./setup.sh login codex
./setup.sh login claude
./setup.sh login github
```

Shared credentials live under `/srv/devctl/shared` and are available to trusted workspaces.

## Telegram

Telegram is optional. CCGram connects Telegram to the central Herdr server; it does not run another Herdr server.

Create a BotFather bot, enable forum topics in a private supergroup, add the bot, collect allowed numeric user IDs and the `-100...` group ID, then run:

```bash
./setup.sh telegram \
  --token-file <bot-token-file> \
  --allowed-users <user-id>[,<user-id>] \
  --group-id <-100-supergroup-id>
```

The token file must be mode `0600`. Telegram uses long polling and no inbound webhook.

## SSH and VS Code

Workspace SSH is bound to `127.0.0.1` on the server:

```ssh-config
Host dev-<project>
    HostName 127.0.0.1
    Port <ssh-port>
    User developer
    ProxyJump <server-alias>
    IdentityFile ~/.ssh/id_ed25519
```

Connect with `ssh dev-<project>`, then use VS Code Remote SSH and open `/workspace/project`.

## Docker access

Workspaces have Docker CLI but no Docker socket by default. For trusted repositories only:

```bash
docker compose --project-name devctl-<project> \
  --env-file projects/<project>.env \
  -f workspace.compose.yml -f workspace.docker-host.override.yml up -d
```

## Operations and backup

```bash
./setup.sh list
docker compose --env-file hub.env -f hub.compose.yml logs -f
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml logs -f
```

Back up `/srv/devctl/projects`, `/srv/devctl/shared`, `/srv/devctl/herdr`, `/srv/devctl/ccgram`, `/srv/devctl/ssh`, and `/srv/devctl/secrets`.

Images: `ghcr.io/lucurlings/devctl-hub:latest` and `ghcr.io/lucurlings/devctl-workspace:latest` for amd64 and arm64.
