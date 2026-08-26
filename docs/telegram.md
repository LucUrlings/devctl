# Optional Telegram profile

Telegram is absent from the default deployment. Running Compose without `--profile telegram` starts only Herdr and does not inspect or require Telegram configuration.

CCGram starts only with all three values:

- `/srv/devctl/secrets/telegram-bot-token`: BotFather token, file mode `0600`
- `TELEGRAM_ALLOWED_USERS`: comma-separated numeric user IDs
- `TELEGRAM_GROUP_ID`: forum supergroup ID beginning with `-100`

Setup:

1. Create a bot with BotFather.
2. Create a private supergroup and enable Topics.
3. In BotFather, enable groups and disable Group Privacy for the bot.
4. Add the bot to the supergroup as an administrator and enable **Manage Topics**.
5. Obtain each allowed user's numeric ID.
6. Obtain the supergroup ID beginning with `-100`.
7. Write only the token to a temporary file and set its mode to `0600`.
8. Run `./setup.sh telegram --allowed-users <ids> --group-id <-100-id> --token-file <file>`.
9. Delete the temporary input file after the helper copies it into `/srv/devctl/secrets` and starts the profile.

CCGram creates one forum topic for each active Herdr agent tab. Agent first-run prompts may need approval before the topic becomes ready. A bare shell tab is not exposed as a Telegram topic.

Inspect it with:

```bash
docker compose --profile telegram --env-file hub.env -f hub.compose.yml ps
docker compose --profile telegram --env-file hub.env -f hub.compose.yml logs -f telegram
```

The service validates the allowlist, group ID, token file, and `CCGRAM_MULTIPLEXER=herdr` before starting. It uses the central Herdr socket and long polling; it receives no Docker socket or inbound network port.
