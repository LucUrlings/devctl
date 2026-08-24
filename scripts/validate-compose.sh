#!/usr/bin/env bash
set -euo pipefail

validation_dir=$(mktemp -d)
trap 'rm -rf -- "$validation_dir"' EXIT

printf '%s\n' \
  'PROJECT_NAME=project' \
  'PROJECT_DIR=/srv/devctl/projects/project' \
  'REPO_URL=https://github.com/owner/repository' \
  'REPO_BRANCH=' \
  'REPO_DEPTH=' \
  'SSH_PORT=22000' \
  'PREVIEW_PORT=3000' \
  'BASE_DOMAIN=example.test' \
  'TRAEFIK_NETWORK=proxy' \
  'TRAEFIK_ENTRYPOINT=websecure' \
  'TRAEFIK_AUTH_MIDDLEWARE=google-oauth@docker' \
  'TRAEFIK_CERT_RESOLVER=' \
  'WORKSPACE_IMAGE=devctl-workspace:dev' \
  'WORKSPACE_CPUS=4' \
  'WORKSPACE_MEMORY=8G' > "$validation_dir/workspace.env"

docker compose --env-file deploy/hub.env.example \
  -f deploy/hub.compose.yml config --quiet
default_services=$(docker compose --env-file deploy/hub.env.example \
  -f deploy/hub.compose.yml config --services)
[[ $default_services == herdr ]]

TELEGRAM_ALLOWED_USERS=12345 TELEGRAM_GROUP_ID=-10012345 \
  docker compose --profile telegram --env-file deploy/hub.env.example \
  -f deploy/hub.compose.yml config --quiet

docker compose --env-file "$validation_dir/workspace.env" \
  -f deploy/workspace.compose.yml config --quiet
docker compose --env-file "$validation_dir/workspace.env" \
  -f deploy/workspace.compose.yml \
  -f deploy/workspace.docker-host.override.yml config --quiet

rendered=$(docker compose --env-file "$validation_dir/workspace.env" \
  -f deploy/workspace.compose.yml config --format json)
jq -e '
  .services.workspace.ports == [{"mode":"ingress","host_ip":"127.0.0.1","target":22,"published":"22000","protocol":"tcp"}]
  and .services.workspace.labels["devctl.project"] == "project"
  and .services.workspace.labels["traefik.http.routers.devctl-project-code.middlewares"] == "google-oauth@docker"
  and .services.workspace.labels["traefik.http.routers.devctl-project-preview.middlewares"] == "google-oauth@docker"
  and .services.workspace.labels["traefik.http.services.devctl-project-code.loadbalancer.server.port"] == "8080"
  and .services.workspace.labels["traefik.http.services.devctl-project-preview.loadbalancer.server.port"] == "3000"
' <<< "$rendered" >/dev/null
