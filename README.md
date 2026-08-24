# Devctl

Two Docker images and two Compose deployments: one permanent Herdr control plane and any number of persistent development workspaces. A small optional setup script turns arguments into env files and runs Compose; there is no installed CLI, project registry, package, or automatic port allocator.

## TL;DR

```bash
# On the Docker server: download only the deployment bundle.
mkdir -p ~/devctl-deploy/projects && cd ~/devctl-deploy
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/hub.compose.yml
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/hub.env.example
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/workspace.compose.yml
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/workspace.env.example
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/workspace.docker-host.override.yml
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/setup.sh
chmod +x setup.sh

./setup.sh hub --authorized-key ~/.ssh/authorized_keys

./setup.sh workspace \
  --name <project> \
  --repo <repo> \
  --ssh-port <free-port-in-22000-22999> \
  --base-domain <base-domain> \
  --traefik-network <traefik-network> \
  --auth-middleware <oauth-middleware>

# Paste the printed SSH block into ~/.ssh/config, then:
ssh dev-<project>

# Optional Telegram only:
./setup.sh telegram --allowed-users <user-id>[,<user-id>] \
  --group-id <-100-supergroup-id> --token-file <bot-token-file>
```

Use project names matching `[a-z0-9][a-z0-9-]{0,40}`. Choose a different free loopback SSH port in `22000-22999` for every project. Set `REPO_URL=<repo>` in each project env file.

Requirements: a Linux amd64 or arm64 Docker server with Docker Compose, an existing Traefik network and OAuth middleware, and DNS/TLS coverage for the code and preview hostnames. The workstation needs an SSH client; VS Code is optional.

## What runs

`hub.compose.yml` starts exactly one `herdr server`. It persists `/srv/devctl/herdr`, mounts the Docker socket, and contains `dev-enter`, which finds one workspace by the `devctl.project` Docker label and enters it as `developer`. The Docker socket gives the hub host-equivalent control.

`workspace.compose.yml` starts one workspace with `sshd` and code-server. It safely clones into `/workspace/project` only when empty, verifies `origin` on every later start, and refuses non-Git data or an origin mismatch. It never executes repository setup scripts.

Each workspace contains Codex, Claude Code, Herdr, GitHub CLI, Git, Node.js, Python, pip, pipx, uv, Docker CLI/Compose, and common terminal tools. Images are published for amd64 and arm64:

```text
ghcr.io/lucurlings/devctl-hub:latest
ghcr.io/lucurlings/devctl-workspace:latest
```

## Setup helper

`setup.sh hub` creates `/srv/devctl`, installs public keys, creates `hub.env`, and starts Herdr. `setup.sh workspace` validates its arguments, rejects configured or currently listening SSH ports, creates the project directories and env file, starts Compose, waits for health, and prints URLs plus the SSH block.

Authentication is also argument-driven:

```bash
./setup.sh auth github
./setup.sh auth codex
./setup.sh auth claude
```

Run `./setup.sh help` for optional branch, clone depth, preview port, entrypoint, certificate resolver, and image arguments. The script is only a thin Compose helper: it has no registry or hidden state. You can always edit the env files and run Compose directly.

## Generated configuration

Edit `projects/<project>.env`:

```env
PROJECT_NAME=<project>
PROJECT_DIR=/srv/devctl/projects/<project>
REPO_URL=<repo>
REPO_BRANCH=
REPO_DEPTH=
SSH_PORT=<unused-port-in-22000-22999>
PREVIEW_PORT=3000
BASE_DOMAIN=<base-domain>
TRAEFIK_NETWORK=<external-traefik-network>
TRAEFIK_ENTRYPOINT=websecure
TRAEFIK_AUTH_MIDDLEWARE=<google-oauth-middleware>
TRAEFIK_CERT_RESOLVER=
WORKSPACE_IMAGE=ghcr.io/lucurlings/devctl-workspace:latest
```

The Compose file creates:

- `<project>.code.<base-domain>` → code-server port `8080`
- `<project>.dev.<base-domain>` → `PREVIEW_PORT`

Both routes use TLS and the configured Traefik OAuth middleware. Traefik must already exist, and wildcard or explicit DNS/certificates must cover both names. Neither HTTP port is published on the host; code-server uses `auth: none` internally because Traefik OAuth is the security boundary.

## SSH and VS Code

Add this on your workstation:

```ssh-config
Host dev-server
    HostName <server-hostname>
    User <server-user>
    IdentityFile ~/.ssh/id_ed25519

Host dev-<project>
    HostName 127.0.0.1
    Port <ssh-port>
    User developer
    ProxyJump dev-server
    IdentityFile ~/.ssh/id_ed25519
```

Connect with `ssh dev-<project>`, or install VS Code Remote SSH, connect to `dev-<project>`, and open `/workspace/project`.

The checkout, SSH host keys, and `/home/developer/.vscode-server` are bind-mounted under `PROJECT_DIR`. Disconnecting does not stop the container. Restarting or recreating it preserves its SSH identity and VS Code installation, so you can reconnect normally.

## Shared authentication

Authenticate once through the helper; every trusted workspace receives the same host directories:

```bash
./setup.sh auth github
./setup.sh auth codex
./setup.sh auth claude
```

GitHub state persists in `/srv/devctl/shared/gh`, Codex in `/srv/devctl/shared/codex`, and Claude in `/srv/devctl/shared/claude`. All trusted workspaces can access these credentials.

## Herdr

Attach to the control plane:

```bash
docker compose --env-file hub.env -f hub.compose.yml exec herdr herdr
```

Create workspaces/tabs and launch `dev-enter` using the exact pinned Herdr commands in [docs/herdr.md](docs/herdr.md). Detach with `Ctrl+B`, then `Q`; run the attach command again to reconnect without terminating panes.

## Optional Telegram

The default hub command starts only Herdr and requires no Telegram values, token, or config file. CCGram exists only in the `telegram` profile.

To enable it:

1. Create a bot with BotFather.
2. Create a private Telegram supergroup and enable forum topics.
3. Add the bot to the group with permission to send messages and manage topics.
4. Obtain the numeric Telegram user IDs allowed to use it.
5. Obtain the supergroup ID beginning with `-100`.
6. Put only the BotFather token in a temporary local file and run `chmod 600` on it.
7. Run the helper with that file, the allowlist, and the group ID:

```bash
./setup.sh telegram --allowed-users <user-id>[,<user-id>] \
  --group-id <-100-supergroup-id> --token-file <bot-token-file>
```

The helper copies the token to `/srv/devctl/secrets/telegram-bot-token` with mode `0600`, updates the protected `hub.env`, and starts the profile. You may then delete the input file.

CCGram uses `CCGRAM_MULTIPLEXER=herdr` and Telegram long polling. It opens no inbound port. See [docs/telegram.md](docs/telegram.md).

## Docker socket opt-in

Workspaces contain Docker CLI but do not receive a Docker socket by default. For a trusted repository only:

```bash
docker compose --project-name devctl-<project> \
  --env-file projects/<project>.env \
  -f workspace.compose.yml -f workspace.docker-host.override.yml up -d
```

This grants that workspace effective root control over the Docker server. See [docs/security.md](docs/security.md).

## Lifecycle

```bash
# workspace
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml ps
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml logs -f
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml stop
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml start
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml down

# update images without deleting bind-mounted state
docker compose --env-file hub.env -f hub.compose.yml pull
docker compose --env-file hub.env -f hub.compose.yml up -d
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml pull
docker compose --project-name devctl-<project> --env-file projects/<project>.env -f workspace.compose.yml up -d
```

`down` removes containers and networks, not `/srv/devctl`. Delete project data only by manually targeting the exact `/srv/devctl/projects/<project>` directory after making a backup.

Back up `/srv/devctl/herdr`, `/srv/devctl/ccgram`, `/srv/devctl/projects`, `/srv/devctl/shared`, `/srv/devctl/ssh`, and `/srv/devctl/secrets`.
