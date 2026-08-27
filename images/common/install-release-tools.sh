#!/usr/bin/env bash
set -euo pipefail

: "${TARGETARCH:?TARGETARCH is required}"
: "${HERDR_VERSION:?}"
: "${GH_VERSION:?}"

herdr_install_dir=${HERDR_INSTALL_DIR:-/usr/local/bin}
gh_install_dir=${GH_INSTALL_DIR:-/usr/local/bin}
install -d -m 0755 "$herdr_install_dir" "$gh_install_dir"

case "$TARGETARCH" in
  amd64)
    herdr_arch=x86_64
    herdr_sha=$HERDR_AMD64_SHA256
    gh_arch=amd64
    gh_sha=$GH_AMD64_SHA256
    ;;
  arm64)
    herdr_arch=aarch64
    herdr_sha=$HERDR_ARM64_SHA256
    gh_arch=arm64
    gh_sha=$GH_ARM64_SHA256
    ;;
  *)
    echo "unsupported architecture: $TARGETARCH" >&2
    exit 2
    ;;
esac

curl --fail --location --silent --show-error \
  --output /tmp/herdr "https://github.com/herdrdev/herdr/releases/download/v${HERDR_VERSION}/herdr-linux-${herdr_arch}"
echo "${herdr_sha}  /tmp/herdr" | sha256sum --check --status
install -m 0755 /tmp/herdr "$herdr_install_dir/herdr"

curl --fail --location --silent --show-error \
  --output /tmp/gh.tar.gz "https://github.com/cli/cli/releases/download/v${GH_VERSION}/gh_${GH_VERSION}_linux_${gh_arch}.tar.gz"
echo "${gh_sha}  /tmp/gh.tar.gz" | sha256sum --check --status
tar -xzf /tmp/gh.tar.gz -C /tmp
install -m 0755 "/tmp/gh_${GH_VERSION}_linux_${gh_arch}/bin/gh" "$gh_install_dir/gh"
rm -rf /tmp/herdr /tmp/gh.tar.gz "/tmp/gh_${GH_VERSION}_linux_${gh_arch}"
