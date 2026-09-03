# Hermes development server

A small Docker Compose deployment containing the official Hermes Agent gateway and one browser-based VS Code companion. They share a projects directory; there is no custom session bridge.

## TLDR

Run this on the Docker server:

```bash
mkdir -p ~/hermes-dev && cd ~/hermes-dev
curl -fsSLO https://raw.githubusercontent.com/LucUrlings/devctl/main/compose.yml
curl -fsSL https://raw.githubusercontent.com/LucUrlings/devctl/main/.env.example -o .env

sed -i "s/^PUID=.*/PUID=$(id -u)/; s/^PGID=.*/PGID=$(id -g)/" .env
sed -i "s|^DATA_PATH=.*|DATA_PATH=$PWD/data|" .env
mkdir -p "$PWD/data/projects"

# Edit .env: set your Traefik network, OAuth middleware, and three DNS names.
nano .env

docker compose run --rm -e HERMES_DASHBOARD=0 hermes setup
docker compose run --rm -e HERMES_DASHBOARD=0 hermes \
  config set terminal.cwd /opt/data/projects
dashboard_host=$(sed -n 's/^DASHBOARD_HOST=//p' .env)
docker compose run --rm -e HERMES_DASHBOARD=0 hermes dashboard register \
  --redirect-uri "https://${dashboard_host}/auth/callback"

# Trust HTTPS headers from your existing Traefik network.
traefik_network=$(sed -n 's/^TRAEFIK_NETWORK=//p' .env)
traefik_cidr=$(docker network inspect "$traefik_network" \
  --format '{{(index .IPAM.Config 0).Subnet}}')
docker compose run --rm -e HERMES_DASHBOARD=0 hermes \
  config set dashboard.trusted_proxies \
  "[\"${traefik_cidr}\"]"
docker compose up -d
```

During `hermes setup`, select your model provider, Telegram, and log into Nous Portal. `dashboard register` adds the dashboard OAuth client to `data/.env`; that directory is ignored by Git.

Open `DASHBOARD_HOST` for Hermes or use Telegram. Open `CODE_HOST` for code-server. Start a development server from its terminal, make it listen on `0.0.0.0:$DEV_PORT`, then open `DEV_HOST`.

## How it works

- The official `nousresearch/hermes-agent` image runs `hermes gateway run` under its built-in s6 supervisor.
- `./data` is mounted at `/opt/data`, the official Hermes data location.
- Repositories belong in `./data/projects` on the host and `/opt/data/projects` inside Hermes.
- The companion mounts `DATA_PATH` at the same absolute path used on the host, and code-server opens `DATA_PATH/projects`.
- `terminal.cwd` makes gateway conversations start in the shared projects directory.
- Telegram uses outbound long polling, so Hermes needs no inbound port.
- Hermes's built-in dashboard runs alongside the gateway under s6 on port 9119.
- Hermes receives 1 GB of shared memory so its bundled browser automation can run reliably.
- Traefik routes `DASHBOARD_HOST` to it, while Hermes's supported Nous OAuth protects the dashboard itself.
- The container runs with the host UID and GID from `.env`, keeping bind-mounted files editable on the host.
- Traefik sends `CODE_HOST` to code-server on port 8080 and `DEV_HOST` to `DEV_PORT`.
- No HTTP service publishes a host port. The code-server and development routes use your existing Traefik OAuth middleware.
- Hermes and the companion share an internal Docker network.
- Matching host/container project paths allow repository Compose files to use bind mounts through the host Docker socket.
- Hermes and companion both receive `DEVCTL_DASHBOARD_URL`, `DEVCTL_CODE_URL`, `DEVCTL_DEV_URL`, and `DEVCTL_DEV_PORT`.

Do not run two Hermes gateway containers against the same `data/` directory.

The companion mounts `/var/run/docker.sock`. This gives it effectively root-level control of the Docker server. Only use it with repositories and extensions you trust.

The dashboard deliberately uses native Nous OAuth instead of the Traefik OAuth middleware, avoiding two consecutive login screens. The configured Traefik network CIDR is trusted only for forwarded HTTPS metadata; every dashboard request still requires Hermes authentication. Do not attach untrusted containers to that network.

## Requirements

- Docker Engine with Docker Compose
- Existing Traefik network and OAuth middleware
- DNS records for `DASHBOARD_HOST`, `CODE_HOST`, and `DEV_HOST` pointing to the server
- TLS configured by the existing Traefik deployment

The companion image supports `linux/amd64` and `linux/arm64`. It contains code-server, Node.js LTS with npm, Docker CLI with Compose, Git, Python, curl, jq, ripgrep, and basic terminal tools.

## Projects

Ask Hermes to clone repositories into `/opt/data/projects/<name>`. They appear immediately in code-server under `DATA_PATH/projects/<name>`.

From code-server, open a terminal and run the repository's development command. The server must bind to all container interfaces, for example:

```bash
npm run dev -- --host 0.0.0.0 --port "$DEVCTL_DEV_PORT"
```

The exact command depends on the repository. Hermes and companion can read the public URLs from `DEVCTL_CODE_URL` and `DEVCTL_DEV_URL`.

All repositories can stay in the shared projects directory, but `DEV_HOST` is one preview route to one `DEV_PORT` in the companion. Run one preview server at a time unless you add more Traefik routes and ports yourself.

## Useful commands

```bash
# Stop/start
docker compose stop
docker compose up -d

# Logs
docker compose logs -f hermes
docker compose logs -f companion

# Reconfigure the model or Telegram
docker compose run --rm hermes setup

# Pull the images configured in .env
docker compose pull
docker compose up -d

# Open the Hermes CLI against the same persistent state
docker compose run --rm hermes
```

Back up the complete `data/` directory. It contains both secrets and project data.

`companion-data/` contains code-server extensions and settings. It can also be backed up, but it is not required to recover Hermes or the repositories.

The deployment follows the official [Hermes Docker documentation](https://hermes-agent.nousresearch.com/docs/user-guide/docker) and [Telegram setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram).
