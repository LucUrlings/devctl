# Optional Telegram profile

Telegram is disabled by default. The hub starts without a bot token, Telegram IDs, or CCGram state.

## Setup

1. Create a bot with BotFather.
2. Create a private supergroup and enable Topics.
3. In BotFather, allow groups and disable Group Privacy.
4. Add the bot as an administrator with permission to manage topics.
5. Obtain each allowed user’s numeric ID.
6. Obtain the supergroup ID beginning with `-100`.
7. Save only the token in a temporary file and set mode `0600`.
8. Run:

```bash
./setup.sh telegram \
  --token-file <bot-token-file> \
  --allowed-users <user-id>[,<user-id>] \
  --group-id <-100-supergroup-id>
```

The helper copies the token to `/srv/devctl/secrets/telegram-bot-token`, validates the settings, and starts the `telegram` Compose profile using long polling.

## Agent topics

Start agents explicitly:

```bash
./setup.sh agent <project> codex
./setup.sh agent <project> claude
```

CCGram’s upstream Herdr backend discovers the active pane and creates its topic. Devctl does not intercept prompts, patch CCGram internals, restart exited agents, or reconnect stale bindings.

If an agent ends, start it again with the same command. `Select Working Directory` at `/` is CCGram’s hub-container browser, not the project workspace.

## Resetting old bindings

When moving from a version that used automatic session recovery:

```bash
./setup.sh update
./setup.sh reset-sessions
./setup.sh agent <project> codex
```

The reset archives only Herdr and CCGram state under `/srv/devctl/backups`, then recreates the containers so their session mounts use the fresh state. Repositories, credentials, project configuration, SSH data, and secrets remain untouched. Delete obsolete Telegram topics manually after the new one works.

## Status and logs

```bash
docker compose --profile telegram --env-file hub.env -f hub.compose.yml ps
docker compose --profile telegram --env-file hub.env -f hub.compose.yml logs -f telegram
```
