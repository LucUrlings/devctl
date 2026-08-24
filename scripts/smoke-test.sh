#!/usr/bin/env bash
set -euo pipefail

docker image inspect devctl-hub:dev >/dev/null
docker image inspect devctl-workspace:dev >/dev/null
docker run --rm --entrypoint image-versions devctl-hub:dev
docker run --rm --entrypoint image-versions devctl-workspace:dev
echo "Image smoke tests passed"
