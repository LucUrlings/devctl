# Hermes development server

A small Docker Compose deployment for running the official Hermes Agent gateway. Hermes keeps its configuration, credentials, sessions, memory, skills, and projects in one local `data/` directory.

## TLDR

Run this on the Docker server:

```bash
cp .env.example .env
sed -i "s/^PUID=.*/PUID=$(id -u)/; s/^PGID=.*/PGID=$(id -g)/" .env
mkdir -p data/projects

docker compose run --rm hermes setup
docker compose run --rm hermes config set terminal.cwd /opt/data/projects
docker compose up -d hermes
docker compose logs -f hermes
```

During `hermes setup`, select your model provider and Telegram. Hermes writes secrets into `data/.env`; that directory is ignored by Git.

## How it works

- The official `nousresearch/hermes-agent` image runs `hermes gateway run` under its built-in s6 supervisor.
- `./data` is mounted at `/opt/data`, the official Hermes data location.
- Repositories belong in `./data/projects` on the host and `/opt/data/projects` inside Hermes.
- `terminal.cwd` makes gateway conversations start in the shared projects directory.
- Telegram uses outbound long polling, so Hermes needs no inbound port.
- The container runs with the host UID and GID from `.env`, keeping bind-mounted files editable on the host.

Do not run two Hermes gateway containers against the same `data/` directory.

## Useful commands

```bash
# Stop/start
docker compose stop hermes
docker compose up -d hermes

# Logs
docker compose logs -f hermes

# Reconfigure the model or Telegram
docker compose run --rm hermes setup

# Update to the image pinned in .env
docker compose pull hermes
docker compose up -d hermes

# Open the Hermes CLI against the same persistent state
docker compose run --rm hermes
```

Back up the complete `data/` directory. It contains both secrets and project data.

The deployment follows the official [Hermes Docker documentation](https://hermes-agent.nousresearch.com/docs/user-guide/docker) and [Telegram setup](https://hermes-agent.nousresearch.com/docs/user-guide/messaging/telegram).
