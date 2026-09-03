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

# Edit .env: set your Traefik network, OAuth middleware, and two DNS names.
nano .env

docker compose run --rm hermes setup
docker compose run --rm hermes config set terminal.cwd /opt/data/projects
docker compose up -d
```

During `hermes setup`, select your model provider and Telegram. Hermes writes secrets into `data/.env`; that directory is ignored by Git.

Open the URL configured as `CODE_HOST`. Start a development server from the code-server terminal, making it listen on `0.0.0.0:$DEV_PORT`, then open `DEV_HOST`.

## How it works

- The official `nousresearch/hermes-agent` image runs `hermes gateway run` under its built-in s6 supervisor.
- `./data` is mounted at `/opt/data`, the official Hermes data location.
- Repositories belong in `./data/projects` on the host and `/opt/data/projects` inside Hermes.
- The companion mounts `DATA_PATH` at the same absolute path used on the host, and code-server opens `DATA_PATH/projects`.
- `terminal.cwd` makes gateway conversations start in the shared projects directory.
- Telegram uses outbound long polling, so Hermes needs no inbound port.
- The container runs with the host UID and GID from `.env`, keeping bind-mounted files editable on the host.
- Traefik sends `CODE_HOST` to code-server on port 8080 and `DEV_HOST` to `DEV_PORT`.
- Neither HTTP service publishes a host port. Both routes use your existing Traefik OAuth middleware.
- Hermes and the companion share an internal Docker network.
- Matching host/container project paths allow repository Compose files to use bind mounts through the host Docker socket.
- Hermes and companion both receive `DEVCTL_CODE_URL`, `DEVCTL_DEV_URL`, and `DEVCTL_DEV_PORT`.

Do not run two Hermes gateway containers against the same `data/` directory.

The companion mounts `/var/run/docker.sock`. This gives it effectively root-level control of the Docker server. Only use it with repositories and extensions you trust.

## Requirements

- Docker Engine with Docker Compose
- Existing Traefik network and OAuth middleware
- DNS records for `CODE_HOST` and `DEV_HOST` pointing to the server
- TLS configured by the existing Traefik deployment

The companion image supports `linux/amd64` and `linux/arm64`. It contains code-server, Docker CLI with Compose, Git, Python, curl, jq, ripgrep, and basic terminal tools.

## Projects

Ask Hermes to clone repositories into `/opt/data/projects/<name>`. They appear immediately in code-server under `DATA_PATH/projects/<name>`.

From code-server, open a terminal and run the repository's development command. The server must bind to all container interfaces, for example:

```bash
npm run dev -- --host 0.0.0.0 --port "$DEVCTL_DEV_PORT"
```

The exact command depends on the repository. Hermes and companion can read the public URLs from `DEVCTL_CODE_URL` and `DEVCTL_DEV_URL`.

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

# Update to the image pinned in .env
docker compose pull
docker compose up -d

# Open the Hermes CLI against the same persistent state
docker compose run --rm hermes
```

Back up the complete `data/` directory. It contains both secrets and project data.

`companion-data/` contains code-server extensions and settings. It can also be backed up, but it is not required to recover Hermes or the repositories.

The deployment follows the official [Hermes Docker documentation](https://hermes-agent.nousresearch.com/docs/user-guide/docker) and [Telegram setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram).
