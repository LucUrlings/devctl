# Optional Telegram profile

Telegram is absent from the default deployment. Running Compose without `--profile telegram` starts only Herdr and does not inspect or require Telegram configuration.

CCGram starts only with all three values:

- `/srv/devctl/secrets/telegram-bot-token`: BotFather token, file mode `0600`
- `TELEGRAM_ALLOWED_USERS`: comma-separated numeric user IDs
- `TELEGRAM_GROUP_ID`: forum supergroup ID beginning with `-100`

Setup:

1. Create a bot with BotFather.
2. Create a private supergroup and enable Topics.
3. Add the bot and allow it to send messages and manage topics.
4. Obtain each allowed user's numeric ID.
5. Obtain the supergroup ID beginning with `-100`.
6. Write only the token to a temporary file and set its mode to `0600`.
7. Run `./setup.sh telegram --allowed-users <ids> --group-id <-100-id> --token-file <file>`.
8. Delete the temporary input file after the helper copies it into `/srv/devctl/secrets` and starts the profile.

Inspect it with:

```bash
docker compose --profile telegram --env-file hub.env -f hub.compose.yml ps
docker compose --profile telegram --env-file hub.env -f hub.compose.yml logs -f telegram
```

The service validates the allowlist, group ID, token file, and `CCGRAM_MULTIPLEXER=herdr` before starting. It uses the central Herdr socket and long polling; it receives no Docker socket or inbound network port.
