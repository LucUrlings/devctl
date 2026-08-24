#!/usr/bin/env bash
set -euo pipefail

validation_dir=$(mktemp -d)
trap 'rm -rf "$validation_dir"' EXIT
cp .env.example "$validation_dir/workspace.env"
docker compose --env-file "$validation_dir/workspace.env" \
  -f compose/workspace.compose.yml config --quiet
docker compose --env-file "$validation_dir/workspace.env" \
  -f compose/workspace.compose.yml -f compose/workspace.docker-host.override.yml config --quiet
docker compose --env-file "$validation_dir/workspace.env" \
  -f compose/workspace.compose.yml \
  -f compose/workspace.traefik-certresolver.override.yml config --quiet
docker compose --env-file "$validation_dir/workspace.env" \
  -f compose/hub.compose.yml config --quiet

rendered=$(docker compose --env-file "$validation_dir/workspace.env" \
  -f compose/workspace.compose.yml config --format json)
if jq -e '.services.workspace.labels | keys[] | contains("$")' <<<"$rendered" | grep -q true; then
  echo "unexpanded variable found in a Traefik label key" >&2
  exit 1
fi
jq -e '
  .services.workspace.ports == [{"mode":"ingress","host_ip":"127.0.0.1","target":22,"published":"22000","protocol":"tcp"}]
  and .services.workspace.labels["traefik.http.routers.devctl-project-code.middlewares"] == "google-oauth@docker"
  and .services.workspace.labels["traefik.http.routers.devctl-project-preview.middlewares"] == "google-oauth@docker"
  and .services.workspace.labels["traefik.http.services.devctl-project-code.loadbalancer.server.port"] == "8080"
  and .services.workspace.labels["traefik.http.services.devctl-project-preview.loadbalancer.server.port"] == "3000"
' <<<"$rendered" >/dev/null
