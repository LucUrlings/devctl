# Shared authentication

Devctl stores authentication once under `/srv/devctl/shared` and mounts it into trusted workspaces:

- GitHub CLI: `/srv/devctl/shared/gh` -> `GH_CONFIG_DIR`
- Codex: `/srv/devctl/shared/codex` -> `CODEX_HOME` / `~/.codex`
- Claude: `/srv/devctl/shared/claude` -> `CLAUDE_CONFIG_DIR` / `~/.claude`

Run `devctl auth github`, `devctl auth codex`, and `devctl auth claude` from an interactive hub terminal. `devctl auth status` reports only authenticated/not authenticated and never prints tokens.

Codex follows the official headless device-code command `codex login --device-auth`. Device login may need enabling in ChatGPT security/workspace settings. Its file credential cache is sensitive and must never be copied into Git or chat.

Claude runs `claude auth login` with its config directory redirected into the shared mount. Complete the browser or code-paste flow shown by Claude Code. GitHub uses its browser flow and configures HTTPS credential lookup without putting a token in a remote URL.

All trusted workspaces can read and refresh these credentials. Separate users with different trust requirements need separate Devctl deployments or a future per-project credential mode.

SSH Git URLs remain disabled until `ALLOW_SSH_GIT=true`; even then, configure
`GIT_SSH_AUTH_SOCK_HOST_PATH` as an explicit forwarded SSH-agent socket on the Docker server.
Devctl mounts that socket at `/run/devctl-ssh-agent` and exposes only that fixed path to SSH
sessions. It never includes or mounts private SSH key files by default.
