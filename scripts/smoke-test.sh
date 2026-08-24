#!/usr/bin/env bash
set -euo pipefail

hub_image=${HUB_IMAGE:-ghcr.io/lucurlings/devctl-hub:dev}
workspace_image=${WORKSPACE_IMAGE:-ghcr.io/lucurlings/devctl-workspace:dev}

docker image inspect "$hub_image" >/dev/null
docker image inspect "$workspace_image" >/dev/null
docker run --rm --entrypoint image-versions "$hub_image"
docker run --rm --entrypoint image-versions "$workspace_image"
echo "Image smoke tests passed"
