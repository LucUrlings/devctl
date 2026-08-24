#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ $(id -u) -ne 0 ]]; then
  echo "Run this local-development installer with sudo." >&2
  exit 2
fi
install -m 0755 "$script_dir/devctl-host" /usr/local/bin/devctl
exec /usr/local/bin/devctl init
