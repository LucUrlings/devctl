#!/usr/bin/env bash
set -euo pipefail

version=${1:?usage: package-release.sh <version> [output-directory]}
output=${2:-dist}
[[ $version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || {
  echo "version must have the form 1.2.3" >&2
  exit 2
}

script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
stage=$(mktemp -d)
trap 'rm -rf -- "$stage"' EXIT
mkdir -p "$output" "$stage/tar" "$stage/deb/DEBIAN" "$stage/deb/usr/bin"

install -m 0755 "$script_dir/devctl-host" "$stage/tar/devctl"
sed -i "s/^readonly DEVCTL_LAUNCHER_VERSION=.*/readonly DEVCTL_LAUNCHER_VERSION=$version/" \
  "$stage/tar/devctl"
tar -C "$stage/tar" -czf "$output/devctl-$version-linux-all.tar.gz" devctl

install -m 0755 "$stage/tar/devctl" "$stage/deb/usr/bin/devctl"
printf '%s\n' \
  'Package: devctl' \
  "Version: $version" \
  'Architecture: all' \
  'Maintainer: LucUrlings' \
  'Section: admin' \
  'Priority: optional' \
  'Description: Manage persistent remote Docker development workspaces' \
  > "$stage/deb/DEBIAN/control"
dpkg-deb --root-owner-group --build "$stage/deb" "$output/devctl_${version}_all.deb" >/dev/null

if command -v sha256sum >/dev/null; then
  (cd "$output" && sha256sum devctl* > SHA256SUMS)
else
  (cd "$output" && shasum -a 256 devctl* > SHA256SUMS)
fi
