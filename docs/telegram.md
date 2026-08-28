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

Devctl sets `TELEGRAM_AUTOCLOSE_DONE_MINUTES=0` and `TELEGRAM_AUTOCLOSE_DEAD_MINUTES=0`, disabling timer-based topic deletion. A persistent Herdr wrapper also restarts an unexpectedly exited Codex or Claude CLI and resumes its latest project conversation. During workspace recreation it waits for the container without discarding that resume intent. Set either timer to a positive number of minutes in `hub.env` only when automatic topic deletion is wanted.

On a hub restart, Herdr restores the saved workspace/tab layout and Devctl reconnects those tabs only after each workspace finishes clone/origin validation and becomes healthy. Telegram stays gated until all discovered project panes have reattached successfully. Devctl installs Herdr's official Codex and Claude integration hooks into the shared configuration so resumed conversations retain a stable session identity even though the pane terminal itself was recreated.

## Recovering an agent topic

Current sessions should remain bound. Run this once on the Docker server for a topic that was already stale before the persistent wrapper was installed:

```bash
./setup.sh agent <project> codex
# or
./setup.sh agent <project> claude
```

This starts a persistent agent wrapper in the selected workspace repository. CCGram then creates a correctly bound project topic. If the child CLI later exits unexpectedly, the wrapper uses the tool's supported resume command (`codex resume --last` or `claude --continue`) in the same project. Close its Herdr agent tab when you intentionally want to stop the session; the reconciler does not recreate an intentionally removed tab.

`Select Working Directory` with `Current: /` is CCGram's hub-container directory browser. It means the Telegram topic is unbound; it is not the project workspace. Do not use that browser to recover a Devctl project.

`/sync` audits CCGram state. Choosing **Fix** removes stale bindings and may close their old Telegram topics. It is a cleanup command, not a reconnection command.

If a topic shows the entire Codex terminal, repeats your prompt with a `👤` prefix, or reports `SessionStart hook (failed)` with exit code `127`, run `./setup.sh update` followed by `./setup.sh agent <project> codex`. This updates CCGram's Herdr bridge, restores the shared native session hook, and starts a correctly identified session.

Inspect it with:

```bash
docker compose --profile telegram --env-file hub.env -f hub.compose.yml ps
docker compose --profile telegram --env-file hub.env -f hub.compose.yml logs -f telegram
```

The service validates the allowlist, group ID, token file, and `CCGRAM_MULTIPLEXER=herdr` before starting. It uses the central Herdr socket and long polling; it receives no Docker socket or inbound network port.
