#!/usr/bin/env bash
set -euo pipefail

hub_image=${HUB_IMAGE:-ghcr.io/lucurlings/devctl-hub:dev}
workspace_image=${WORKSPACE_IMAGE:-ghcr.io/lucurlings/devctl-workspace:dev}

docker image inspect "$hub_image" >/dev/null
docker image inspect "$workspace_image" >/dev/null
docker run --rm --entrypoint image-versions "$hub_image"
docker run --rm --entrypoint image-versions "$workspace_image"
for image in "$hub_image" "$workspace_image"; do
  docker run --rm --entrypoint sh "$image" -c '
    test ! -e /usr/local/lib/node_modules/npm
    test "$(command -v npm)" = /home/developer/.local/bin/npm
    test "$(command -v ccgram)" = /home/developer/.local/bin/ccgram
    test -x /home/developer/.local/share/uv/tools/ccgram/bin/python
    ! grep -q "^constraints = " /home/developer/.local/share/uv/tools/ccgram/uv-receipt.toml
    /home/developer/.local/share/uv/tools/ccgram/bin/python -c "import ccgram, msgpack"
  '
done
docker run --rm --entrypoint bash "$hub_image" -c '
  install -d -o developer -g developer /srv/devctl/shared/codex /srv/devctl/ccgram
  jq -n '\''
    {hooks: {
      SessionStart: [
        {hooks: [{type: "command", name: "ccgram-session-tracker",
                  command: "/usr/local/bin/python -m ccgram.main hook --provider codex",
                  timeout: 5}]},
        {hooks: [{type: "command", command: "bash /srv/devctl/shared/codex/herdr-agent-state.sh session",
                  timeout: 10}]}
      ],
      Stop: [{hooks: [{type: "command", name: "ccgram-session-tracker",
                       command: "/usr/local/bin/python -m ccgram.main hook --provider codex",
                       timeout: 5}]}]
    }}
  '\'' > /srv/devctl/shared/codex/hooks.json
  chown developer:developer /srv/devctl/shared/codex/hooks.json
  runuser --user developer -- env HOME=/home/developer CCGRAM_DIR=/srv/devctl/ccgram \
    ccgram hook --provider codex --uninstall >/dev/null
  runuser --user developer -- env HOME=/home/developer CCGRAM_DIR=/srv/devctl/ccgram \
    ccgram hook --provider codex --install >/dev/null
  ! grep -q "/usr/local/bin/python -m ccgram.main hook" /srv/devctl/shared/codex/hooks.json
  grep -q "/home/developer/.local/share/uv/tools/ccgram/bin/python -m ccgram.main hook --provider codex" \
    /srv/devctl/shared/codex/hooks.json
  grep -q "herdr-agent-state.sh" /srv/devctl/shared/codex/hooks.json
'
docker run --rm --entrypoint sh "$workspace_image" -c '
  test "$(npm prefix --global)" = /home/developer/.local
  runuser --user developer -- sh -c '\''
    for tool in codex claude gh herdr; do
      path=$(command -v "$tool")
      test -n "$path"
      test -w "$(dirname "$path")"
    done
  '\''
'
echo "Image smoke tests passed"
