#!/usr/bin/env bash
set -euo pipefail
umask 077

DEPLOY_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
readonly DEPLOY_DIR
readonly STATE_ROOT=/srv/devctl
readonly PUBLIC_KEY_REGEX='(^|[[:space:]])(ssh-ed25519|ssh-rsa|ecdsa-sha2-nistp(256|384|521)|sk-ssh-ed25519@openssh.com|sk-ecdsa-sha2-nistp256@openssh.com)[[:space:]][A-Za-z0-9+/=]+'

usage() {
  cat <<'EOF'
Usage:
  ./setup.sh hub [--authorized-key PATH] [--no-start]
  ./setup.sh workspace --name NAME --repo URL --ssh-port PORT \
    --base-domain DOMAIN --traefik-network NETWORK --auth-middleware MIDDLEWARE \
    [--branch BRANCH] [--depth N] [--preview-port PORT] \
    [--entrypoint NAME] [--cert-resolver NAME] [--image IMAGE] [--no-start]
  ./setup.sh auth github|codex|claude
  ./setup.sh telegram --allowed-users IDS --group-id ID --token-file PATH

The helper writes env files beside itself and persistent data under /srv/devctl.
It never stores repository credentials in generated files.
EOF
}

die() {
  echo "setup.sh: $*" >&2
  exit 2
}

as_root() {
  if [[ $(id -u) == 0 ]]; then
    "$@"
  else
    command -v sudo >/dev/null 2>&1 || die "sudo is required to write $STATE_ROOT"
    sudo "$@"
  fi
}

require_compose() {
  command -v docker >/dev/null 2>&1 || die "docker is required"
  docker compose version >/dev/null 2>&1 || die "Docker Compose is required"
}

validate_slug() {
  [[ $1 =~ ^[a-z0-9][a-z0-9-]{0,40}$ ]] || \
    die "project name must match [a-z0-9][a-z0-9-]{0,40}"
}

validate_repo() {
  local value=$1
  [[ $value =~ ^https://[A-Za-z0-9.-]+/[A-Za-z0-9._~/%+-]+$ ]] || \
    die "repository must be a credential-free HTTPS URL"
}

validate_branch() {
  local value=$1
  [[ -z $value ]] && return
  [[ $value =~ ^[A-Za-z0-9][A-Za-z0-9._/-]{0,254}$ ]] || die "invalid branch"
  [[ $value != *..* && $value != *//* ]] || die "invalid branch"
}

validate_integer() {
  local label=$1 value=$2 minimum=$3 maximum=$4
  [[ $value =~ ^[0-9]+$ && ${#value} -le 10 ]] || die "$label must be an integer"
  local number=$((10#$value))
  (( number >= minimum && number <= maximum )) || \
    die "$label must be between $minimum and $maximum"
}

validate_name() {
  local label=$1 value=$2
  [[ $value =~ ^[A-Za-z0-9_.@-]+$ ]] || die "$label contains unsupported characters"
}

validate_domain() {
  local domain=$1 label
  local -a labels
  ((${#domain} <= 253)) || die "BASE_DOMAIN is invalid"
  [[ $domain != .* && $domain != *. && $domain != *..* ]] || die "BASE_DOMAIN is invalid"
  IFS=. read -r -a labels <<< "$domain"
  ((${#labels[@]} >= 2)) || die "BASE_DOMAIN is invalid"
  for label in "${labels[@]}"; do
    ((${#label} <= 63)) || die "BASE_DOMAIN is invalid"
    [[ $label =~ ^[A-Za-z0-9]([A-Za-z0-9-]*[A-Za-z0-9])?$ ]] || \
      die "BASE_DOMAIN is invalid"
  done
}

validate_image() {
  [[ $1 =~ ^[A-Za-z0-9._/@:-]+$ ]] || die "container image contains unsupported characters"
}

ensure_hub_env() {
  if [[ ! -e $DEPLOY_DIR/hub.env ]]; then
    cp -- "$DEPLOY_DIR/hub.env.example" "$DEPLOY_DIR/hub.env"
  fi
  chmod 0600 "$DEPLOY_DIR/hub.env"
}

wait_for_hub() {
  local container health
  local -a compose=(docker compose --env-file "$DEPLOY_DIR/hub.env" \
    -f "$DEPLOY_DIR/hub.compose.yml")
  for _attempt in {1..60}; do
    container=$("${compose[@]}" ps --all --quiet herdr)
    if [[ -n $container ]]; then
      health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")
      [[ $health == healthy ]] && return
      [[ $health == unhealthy || $health == exited ]] && die "hub became $health; run Compose logs"
    fi
    sleep 2
  done
  die "hub did not become healthy within 120 seconds"
}

wait_for_telegram() {
  local container health
  local -a compose=(docker compose --profile telegram \
    --env-file "$DEPLOY_DIR/hub.env" -f "$DEPLOY_DIR/hub.compose.yml")
  for _attempt in {1..60}; do
    container=$("${compose[@]}" ps --all --quiet telegram)
    if [[ -n $container ]]; then
      health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")
      [[ $health == healthy ]] && return
      [[ $health == unhealthy || $health == exited ]] && die "Telegram became $health; run Compose logs"
    fi
    sleep 2
  done
  die "Telegram did not become healthy within 120 seconds"
}

authorized_keys_configured() {
  # shellcheck disable=SC2016 # $0 is evaluated by awk, not by Bash.
  as_root awk -v pattern="$PUBLIC_KEY_REGEX" '
    $0 !~ /^[[:space:]]*#/ && $0 ~ pattern { found = 1 }
    END { exit !found }
  ' "$STATE_ROOT/ssh/authorized_keys"
}

install_public_key() {
  local key_file=$1 line
  [[ -f $key_file && -s $key_file ]] || die "authorized key file is missing or empty"
  while IFS= read -r line || [[ -n $line ]]; do
    [[ -z ${line//[[:space:]]/} || $line =~ ^[[:space:]]*# ]] && continue
    [[ $line =~ $PUBLIC_KEY_REGEX ]] || \
      die "--authorized-key must contain public SSH keys only"
    if ! as_root grep -Fqx -- "$line" "$STATE_ROOT/ssh/authorized_keys"; then
      printf '%s\n' "$line" | as_root tee -a "$STATE_ROOT/ssh/authorized_keys" >/dev/null
    fi
  done < "$key_file"
}

hub_command() {
  local authorized_key='' no_start=false
  while (($#)); do
    case $1 in
      --authorized-key) (($# >= 2)) || die "--authorized-key needs a path"; authorized_key=$2; shift 2 ;;
      --no-start) no_start=true; shift ;;
      -h|--help) usage; return ;;
      *) die "unknown hub argument: $1" ;;
    esac
  done

  as_root install -d -m 0755 \
    "$STATE_ROOT/herdr" "$STATE_ROOT/herdr/run" "$STATE_ROOT/ccgram" \
    "$STATE_ROOT/projects" "$STATE_ROOT/ssh"
  as_root install -d -m 0700 \
    "$STATE_ROOT/secrets" "$STATE_ROOT/shared/codex" \
    "$STATE_ROOT/shared/claude" "$STATE_ROOT/shared/gh"
  as_root touch "$STATE_ROOT/ssh/authorized_keys"
  as_root chmod 0600 "$STATE_ROOT/ssh/authorized_keys"
  if [[ -n $authorized_key ]]; then
    install_public_key "$authorized_key"
  fi
  if ! authorized_keys_configured; then
    die "provide --authorized-key PATH on the first run"
  fi

  ensure_hub_env
  if [[ $no_start == false ]]; then
    require_compose
    docker compose --env-file "$DEPLOY_DIR/hub.env" \
      -f "$DEPLOY_DIR/hub.compose.yml" up -d
    wait_for_hub
  fi
  echo "Hub configured. Env: $DEPLOY_DIR/hub.env"
}

port_is_already_configured() {
  local wanted=$1 env_file configured
  shopt -s nullglob
  for env_file in "$DEPLOY_DIR"/projects/*.env; do
    configured=$(sed -n 's/^SSH_PORT=//p' "$env_file")
    [[ $configured == "$wanted" ]] && return 0
  done
  return 1
}

port_is_listening() {
  command -v ss >/dev/null 2>&1 || return 1
  ss -H -ltn | awk -v wanted="$1" '
    { address = $4; sub(/^.*:/, "", address) }
    address == wanted { found = 1 }
    END { exit !found }
  '
}

wait_for_workspace() {
  local name=$1 env_file=$2 container health
  local -a compose=(docker compose --project-name "devctl-$name" \
    --env-file "$env_file" -f "$DEPLOY_DIR/workspace.compose.yml")
  for _attempt in {1..150}; do
    container=$("${compose[@]}" ps --all --quiet workspace)
    if [[ -n $container ]]; then
      health=$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container")
      [[ $health == healthy ]] && return
      [[ $health == unhealthy || $health == exited ]] && die "workspace became $health; run Compose logs"
    fi
    sleep 2
  done
  die "workspace did not become healthy within 300 seconds"
}

workspace_command() {
  local name='' repo='' ssh_port='' base_domain='' traefik_network='' auth_middleware=''
  local branch='' depth='' preview_port=3000 entrypoint=websecure cert_resolver=''
  local image=ghcr.io/lucurlings/devctl-workspace:latest no_start=false
  while (($#)); do
    case $1 in
      --name) (($# >= 2)) || die "--name needs a value"; name=$2; shift 2 ;;
      --repo) (($# >= 2)) || die "--repo needs a value"; repo=$2; shift 2 ;;
      --ssh-port) (($# >= 2)) || die "--ssh-port needs a value"; ssh_port=$2; shift 2 ;;
      --base-domain) (($# >= 2)) || die "--base-domain needs a value"; base_domain=$2; shift 2 ;;
      --traefik-network) (($# >= 2)) || die "--traefik-network needs a value"; traefik_network=$2; shift 2 ;;
      --auth-middleware) (($# >= 2)) || die "--auth-middleware needs a value"; auth_middleware=$2; shift 2 ;;
      --branch) (($# >= 2)) || die "--branch needs a value"; branch=$2; shift 2 ;;
      --depth) (($# >= 2)) || die "--depth needs a value"; depth=$2; shift 2 ;;
      --preview-port) (($# >= 2)) || die "--preview-port needs a value"; preview_port=$2; shift 2 ;;
      --entrypoint) (($# >= 2)) || die "--entrypoint needs a value"; entrypoint=$2; shift 2 ;;
      --cert-resolver) (($# >= 2)) || die "--cert-resolver needs a value"; cert_resolver=$2; shift 2 ;;
      --image) (($# >= 2)) || die "--image needs a value"; image=$2; shift 2 ;;
      --no-start) no_start=true; shift ;;
      -h|--help) usage; return ;;
      *) die "unknown workspace argument: $1" ;;
    esac
  done

  [[ -n $name && -n $repo && -n $ssh_port && -n $base_domain && \
     -n $traefik_network && -n $auth_middleware ]] || die "missing required workspace arguments"
  validate_slug "$name"
  validate_repo "$repo"
  validate_branch "$branch"
  validate_integer SSH_PORT "$ssh_port" 22000 22999
  validate_integer PREVIEW_PORT "$preview_port" 1 65535
  [[ -z $depth ]] || validate_integer REPO_DEPTH "$depth" 1 2147483647
  validate_domain "$base_domain"
  validate_name TRAEFIK_NETWORK "$traefik_network"
  validate_name TRAEFIK_AUTH_MIDDLEWARE "$auth_middleware"
  validate_name TRAEFIK_ENTRYPOINT "$entrypoint"
  [[ -z $cert_resolver ]] || validate_name TRAEFIK_CERT_RESOLVER "$cert_resolver"
  validate_image "$image"
  [[ -f $DEPLOY_DIR/hub.env ]] || die "run './setup.sh hub' first"
  authorized_keys_configured || die "run './setup.sh hub' with an authorized key first"

  mkdir -p "$DEPLOY_DIR/projects"
  local env_file=$DEPLOY_DIR/projects/$name.env
  [[ ! -e $env_file ]] || die "$env_file already exists"
  port_is_already_configured "$ssh_port" && die "SSH port $ssh_port is already used by another project env file"
  port_is_listening "$ssh_port" && die "SSH port $ssh_port is already listening on this server"

  local project_dir=$STATE_ROOT/projects/$name temporary
  as_root install -d -m 0755 "$project_dir"
  as_root install -d -m 0700 \
    "$project_dir/repo" "$project_dir/ssh-host-keys" "$project_dir/vscode-server"
  temporary=$(mktemp "$DEPLOY_DIR/projects/.$name.env.XXXXXX")
  printf '%s\n' \
    "PROJECT_NAME=$name" "PROJECT_DIR=$project_dir" "REPO_URL=$repo" \
    "REPO_BRANCH=$branch" "REPO_DEPTH=$depth" "SSH_PORT=$ssh_port" \
    "PREVIEW_PORT=$preview_port" "BASE_DOMAIN=$base_domain" \
    "TRAEFIK_NETWORK=$traefik_network" "TRAEFIK_ENTRYPOINT=$entrypoint" \
    "TRAEFIK_AUTH_MIDDLEWARE=$auth_middleware" \
    "TRAEFIK_CERT_RESOLVER=$cert_resolver" "WORKSPACE_IMAGE=$image" \
    'WORKSPACE_CPUS=4' 'WORKSPACE_MEMORY=8G' > "$temporary"
  chmod 0600 "$temporary"
  mv -- "$temporary" "$env_file"

  if [[ $no_start == false ]]; then
    require_compose
    docker compose --project-name "devctl-$name" --env-file "$env_file" \
      -f "$DEPLOY_DIR/workspace.compose.yml" up -d
    wait_for_workspace "$name" "$env_file"
  fi

  cat <<EOF
Workspace configured: $name
Env: $env_file
Code: https://$name.code.$base_domain
Preview: https://$name.dev.$base_domain

Host dev-$name
    HostName 127.0.0.1
    Port $ssh_port
    User developer
    ProxyJump dev-server
    IdentityFile ~/.ssh/id_ed25519
EOF
}

auth_command() {
  (($# == 1)) || die "auth requires github, codex, or claude"
  as_root test -d "$STATE_ROOT/herdr" || die "run './setup.sh hub' first"
  ensure_hub_env
  require_compose
  local -a compose=(docker compose --env-file "$DEPLOY_DIR/hub.env" -f "$DEPLOY_DIR/hub.compose.yml")
  case $1 in
    github) "${compose[@]}" exec --user developer -e HOME=/home/developer herdr gh auth login --hostname github.com --git-protocol https --web ;;
    codex) "${compose[@]}" exec --user developer -e HOME=/home/developer herdr codex login --device-auth ;;
    claude) "${compose[@]}" exec --user developer -e HOME=/home/developer herdr claude auth login ;;
    *) die "auth requires github, codex, or claude" ;;
  esac
}

telegram_command() {
  local allowed_users='' group_id='' token_file=''
  while (($#)); do
    case $1 in
      --allowed-users) (($# >= 2)) || die "--allowed-users needs a value"; allowed_users=$2; shift 2 ;;
      --group-id) (($# >= 2)) || die "--group-id needs a value"; group_id=$2; shift 2 ;;
      --token-file) (($# >= 2)) || die "--token-file needs a path"; token_file=$2; shift 2 ;;
      -h|--help) usage; return ;;
      *) die "unknown telegram argument: $1" ;;
    esac
  done
  [[ $allowed_users =~ ^[0-9]+(,[0-9]+)*$ ]] || die "allowed users must be comma-separated numeric IDs"
  [[ $group_id =~ ^-100[0-9]+$ ]] || die "group ID must begin with -100"
  [[ -f $token_file && -s $token_file ]] || die "token file is missing or empty"
  [[ $(stat -c '%a' -- "$token_file") == 600 ]] || die "token file must have mode 0600"
  [[ $(wc -l < "$token_file") -le 1 && $(<"$token_file") != *[[:space:]]* ]] || \
    die "token file must contain only the BotFather token"
  as_root test -d "$STATE_ROOT/herdr" || die "run './setup.sh hub' first"

  ensure_hub_env
  local hub_image
  hub_image=$(sed -n 's/^HUB_IMAGE=//p' "$DEPLOY_DIR/hub.env")
  [[ -n $hub_image ]] || hub_image=ghcr.io/lucurlings/devctl-hub:latest
  validate_image "$hub_image"
  local temporary
  temporary=$(mktemp "$DEPLOY_DIR/.hub.env.XXXXXX")
  printf '%s\n' "HUB_IMAGE=$hub_image" "TELEGRAM_ALLOWED_USERS=$allowed_users" \
    "TELEGRAM_GROUP_ID=$group_id" > "$temporary"
  chmod 0600 "$temporary"
  mv -- "$temporary" "$DEPLOY_DIR/hub.env"
  as_root install -m 0600 -- "$token_file" "$STATE_ROOT/secrets/telegram-bot-token"
  require_compose
  docker compose --profile telegram --env-file "$DEPLOY_DIR/hub.env" \
    -f "$DEPLOY_DIR/hub.compose.yml" up -d
  wait_for_telegram
  echo "Telegram configured for group $group_id. The bot token was not printed."
}

main() {
  (($#)) || { usage; exit 2; }
  local command=$1
  shift
  case $command in
    hub) hub_command "$@" ;;
    workspace) workspace_command "$@" ;;
    auth) auth_command "$@" ;;
    telegram) telegram_command "$@" ;;
    -h|--help|help) usage ;;
    *) die "unknown command: $command" ;;
  esac
}

if [[ ${BASH_SOURCE[0]} == "$0" ]]; then
  main "$@"
fi
