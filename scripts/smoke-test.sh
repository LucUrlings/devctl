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
  '
done
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
