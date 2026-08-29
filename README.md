# Devctl

Docker workspaces with code-server, VS Code SSH, Herdr, Codex, Claude, and optional Telegram access.

## TLDR

Run on the Docker server:

```bash
curl -fsSL "https://raw.githubusercontent.com/LucUrlings/devctl/main/deploy/setup.sh?$(date +%s)" -o setup.sh
chmod +x setup.sh

./setup.sh install \
  --base-domain <base-domain> \
  --traefik-network <traefik-network> \
  --auth-middleware <oauth-middleware>

./setup.sh login github
./setup.sh login codex
./setup.sh create <repo> --preview-port <port>
./setup.sh agent <project> codex
```

Open the printed `https://<project>.code.<base-domain>` URL from a phone or browser.

## How it works

The hub runs one Herdr server and, optionally, one stock CCGram process. Each repository gets one isolated workspace containing code-server, SSH, Codex, Claude, GitHub CLI, Herdr, Docker CLI, Node.js, and Python.

`./setup.sh create <repo>` clones and starts a workspace. It does not start an agent. Start one explicitly:

```bash
./setup.sh agent <project> codex
./setup.sh agent <project> claude
./setup.sh agent <project> shell
```

The command creates or reuses a matching Herdr tab and runs one process in the project repository, which is also available at `/workspace/project`. CCGram discovers active Codex and Claude panes using its upstream Herdr backend.

There is no custom CCGram patch, prompt relay, background reconciler, or automatic agent restart. If an agent exits, its topic ends. Start it again explicitly with `./setup.sh agent <project> codex|claude`.

## Requirements and routes

- Linux Docker server with Docker Compose
- Existing Traefik network and OAuth middleware
- Wildcard DNS for `*.code.<base-domain>` and `*.dev.<base-domain>`

Traefik routes `<project>.code.<base-domain>` to code-server on `8080` and `<project>.dev.<base-domain>` to the preview port. Both use TLS and OAuth; neither HTTP port is published on the host.

The preview server must listen on `0.0.0.0:<port>` inside the workspace. Port `3000` is the default; pass `--preview-port <port>` when the project uses another port.

Agents can read the exact routes from `DEVCTL_CODE_URL` and `DEVCTL_PREVIEW_URL`.

## Authentication

```bash
./setup.sh login github
./setup.sh login codex
./setup.sh login claude
```

Credentials persist under `/srv/devctl/shared` and are available to every trusted workspace.

## Telegram (optional)

1. Create a bot with BotFather.
2. Create a private Telegram supergroup and enable Topics.
3. Disable Group Privacy for the bot in BotFather.
4. Add the bot as an administrator with permission to manage topics.
5. Obtain the allowed numeric user IDs and the group ID beginning with `-100`.
6. Put the token in a temporary file and run `chmod 600 <bot-token-file>`.
7. Run:

```bash
./setup.sh telegram \
  --token-file <bot-token-file> \
  --allowed-users <user-id>[,<user-id>] \
  --group-id <-100-supergroup-id>
```

Without this command, Telegram is not started and no Telegram configuration is required.

## SSH and VS Code

`create` prints a `Host dev-<project>` block. Add it to the laptop’s `~/.ssh/config`, configure its `ProxyJump` server alias, then run:

```bash
ssh dev-<project>
```

VS Code Remote SSH should open `/workspace/project`. Repository data, SSH host keys, and `/home/developer/.vscode-server` persist across recreation, so disconnecting does not stop the workspace.

For an SSH Git remote, add `ForwardAgent yes` to that project block. Devctl never mounts a private SSH key; only use agent forwarding with trusted workspaces.

## Operations

```bash
./setup.sh list
./setup.sh update
./setup.sh update <project>
./setup.sh agent <project> codex
./setup.sh teardown <project>
./setup.sh teardown --all
```

`update` refreshes `setup.sh`, Compose files, and images. It deliberately does not start or resume agents.

### Clean session reset

After upgrading from a version that used automatic session recovery, reset old bindings once:

```bash
./setup.sh update
./setup.sh reset-sessions
./setup.sh agent <project> codex
```

`reset-sessions` requires typing `RESET`. It archives Herdr and CCGram state under `/srv/devctl/backups`, then recreates the hub and workspaces so their session mounts point at the fresh state. It does not modify repositories, credentials, project configuration, SSH keys, or secrets. Delete obsolete Telegram topics manually after the new topic works.

## Security and backups

Every workspace receives `/var/run/docker.sock`, which is effectively root access to the server. Use only trusted repositories and agents. The hub also needs the socket to enter labeled workspaces.

Back up `/srv/devctl/projects`, `/srv/devctl/shared`, `/srv/devctl/herdr`, `/srv/devctl/ccgram`, `/srv/devctl/ssh`, and `/srv/devctl/secrets`.

Images:

- `ghcr.io/lucurlings/devctl-hub:latest`
- `ghcr.io/lucurlings/devctl-workspace:latest`
