#!/usr/bin/env bash
set -euo pipefail

echo "Review official release notes before updating versions.env, Dockerfiles, and docker-bake.hcl."
for repository in openai/codex anthropics/claude-code herdrdev/herdr alexei-led/ccgram coder/code-server cli/cli; do
  printf '%-32s ' "$repository"
  gh api "repos/$repository/releases/latest" --jq .tag_name
done
echo "After updating checksums, run: make check && make build"
