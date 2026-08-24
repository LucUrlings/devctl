# Manual Herdr workflow

These commands match Herdr `0.8.2`. Run them from the directory containing `hub.compose.yml` and `hub.env`. Use a project slug matching `[a-z0-9][a-z0-9-]{0,40}`.

Create a Herdr workspace. Herdr returns the workspace, first tab, and root pane IDs as JSON:

```bash
project=<project>
created=$(docker compose --env-file hub.env -f hub.compose.yml exec -T herdr \
  herdr workspace create --cwd /srv/devctl/herdr --label "$project" --no-focus)
workspace_id=$(printf '%s\n' "$created" | jq -r '.result.workspace.workspace_id')
shell_pane=$(printf '%s\n' "$created" | jq -r '.result.root_pane.pane_id')
docker compose --env-file hub.env -f hub.compose.yml exec -T herdr \
  herdr pane run "$shell_pane" "dev-enter $project shell"
```

Create Codex and Claude tabs. `tab create` returns each root pane ID; do not predict IDs:

```bash
codex_tab=$(docker compose --env-file hub.env -f hub.compose.yml exec -T herdr \
  herdr tab create --workspace "$workspace_id" --cwd /srv/devctl/herdr --label Codex --no-focus)
codex_pane=$(printf '%s\n' "$codex_tab" | jq -r '.result.root_pane.pane_id')
docker compose --env-file hub.env -f hub.compose.yml exec -T herdr \
  herdr pane run "$codex_pane" "HERDR_AGENT=codex dev-enter $project codex"

claude_tab=$(docker compose --env-file hub.env -f hub.compose.yml exec -T herdr \
  herdr tab create --workspace "$workspace_id" --cwd /srv/devctl/herdr --label Claude --no-focus)
claude_pane=$(printf '%s\n' "$claude_tab" | jq -r '.result.root_pane.pane_id')
docker compose --env-file hub.env -f hub.compose.yml exec -T herdr \
  herdr pane run "$claude_pane" "HERDR_AGENT=claude dev-enter $project claude"
```

`dev-enter` validates the slug, finds exactly one running container from `devctl.managed=true` and `devctl.project=<project>`, enters as `developer` in `/workspace/project`, and forwards only Herdr pane/tab/workspace context. It also sets the host-visible `HERDR_AGENT` hint.

Attach and detach:

```bash
docker compose --env-file hub.env -f hub.compose.yml exec herdr herdr
```

Detach with `Ctrl+B`, then `Q`. The background Herdr server and panes continue running. Run the same command to reattach. A full hub stop is different: Herdr restores its persisted topology, but container-wrapped Codex or Claude native sessions may need their own resume flow.

Official references: [CLI reference](https://herdr.dev/docs/cli-reference/) and [agent automation](https://herdr.dev/docs/agent-automation/).
