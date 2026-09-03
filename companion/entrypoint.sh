#!/bin/sh
set -eu

case "${PUID:-}:${PGID:-}" in
  *[!0-9:]*|:|:*|*:) echo "PUID and PGID must be numeric" >&2; exit 1 ;;
esac

projects_path=${PROJECTS_PATH:-/projects}
case "$projects_path" in
  /*) ;;
  *) echo "PROJECTS_PATH must be absolute" >&2; exit 1 ;;
esac

if owner=$(getent passwd "$PUID" | cut -d: -f1) && [ -n "$owner" ] && [ "$owner" != coder ]; then
  echo "PUID $PUID already belongs to $owner" >&2
  exit 1
fi

if ! getent group "$PGID" >/dev/null; then
  groupmod --gid "$PGID" coder
fi
usermod --uid "$PUID" --gid "$PGID" coder

if [ -S /var/run/docker.sock ]; then
  socket_gid=$(stat -c '%g' /var/run/docker.sock)
  if ! getent group "$socket_gid" >/dev/null; then
    groupadd --gid "$socket_gid" docker-host
  fi
  socket_group=$(getent group "$socket_gid" | cut -d: -f1)
  usermod --append --groups "$socket_group" coder
fi

mkdir -p "$projects_path" /home/coder/.local/share/code-server /home/coder/.config/code-server
chown "$PUID:$PGID" "$projects_path"
chown -R "$PUID:$PGID" /home/coder

export HOME=/home/coder
export USER=coder
umask 002

exec setpriv --reuid="$PUID" --regid="$PGID" --init-groups "$@"
