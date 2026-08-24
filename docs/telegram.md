# Telegram and CCGram

CCGram is optional and `CCGRAM_ENABLED=false` by default. Without configuration its supervised slot remains idle, no agent hooks are installed, and the hub remains healthy.

1. Create a bot with BotFather.
2. Disable group privacy if required by the current CCGram guide.
3. Create or choose a Telegram supergroup with forum topics enabled.
4. Add the bot as an administrator with topic creation and pin permissions.
5. Obtain your numeric user ID and the `-100...` group ID.
6. Run `sudo devctl telegram configure` in a private interactive terminal. Enter numeric comma-separated user IDs, the forum supergroup ID beginning with `-100`, and the BotFather token when prompted.
7. The installed host launcher recreates the hub automatically. Run `devctl telegram status`.

Configuration enforces `CCGRAM_MULTIPLEXER=herdr`, a non-empty numeric `ALLOWED_USERS`, and one `CCGRAM_GROUP_ID`. Non-secret settings live in `/srv/devctl/config/ccgram.env`. The token lives only in `/srv/devctl/secrets/telegram-bot-token` with mode `0600`; the launch wrapper reads it into the CCGram process environment without logging it.

To disable Telegram, set `CCGRAM_ENABLED=false` in `/srv/devctl/config/devctl.env` and run `sudo devctl init`. Existing bot state is preserved but no Telegram process runs.

CCGram long polls Telegram. No webhook, inbound port, or public hub route is created. One active Herdr agent tab maps to one forum topic. CCGram supports reading output, prompts, interrupts, and approval interaction to the extent exposed by the current provider UI and Herdr terminal backend.

Telegram is privileged development access. Keep the allowlist narrow, protect the group membership, rotate a leaked bot token immediately, and inspect `devctl telegram logs` without sharing sensitive agent output.
