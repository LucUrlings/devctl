# syntax=docker/dockerfile:1.12
ARG NODE_VERSION=24.19.0
ARG NPM_VERSION=12.0.2
ARG PYTHON_VERSION=3.14.7
ARG DOCKER_CLI_VERSION=29.7.2
ARG UV_VERSION=0.12.5
ARG PIPX_VERSION=1.8.0

FROM node:${NODE_VERSION}-trixie-slim AS agents
ARG CODEX_VERSION=0.149.1
ARG CLAUDE_CODE_VERSION=2.1.246
ARG NPM_VERSION
RUN npm install --global --ignore-scripts=false \
      --allow-scripts=@anthropic-ai/claude-code \
      "@openai/codex@${CODEX_VERSION}" \
      "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm install --global "npm@${NPM_VERSION}" \
    && npm cache clean --force

FROM docker:${DOCKER_CLI_VERSION}-cli-alpine3.24 AS dockercli
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:${PYTHON_VERSION}-slim-trixie

ARG TARGETARCH
ARG HERDR_VERSION=0.8.2
ARG GH_VERSION=2.98.0
ARG HERDR_AMD64_SHA256=976150a14d490c94b243ea2e1a7eb2dfb67f12e36b182db90936f6728e6aecf4
ARG HERDR_ARM64_SHA256=f55610658e1c2e0d2aaef730b4b2ab885f7f8ba00285ab372bfb14f2e3d5b40d
ARG GH_AMD64_SHA256=3b8ac6b30336802fc1a858d7c084e11cdf24ac1a761ca90b68022d7d729208de
ARG GH_ARM64_SHA256=cf689084f3a3618f7eae4a2420d335d74626d65f5e594b9828d125d69f800d86
ARG CODE_SERVER_VERSION=4.134.0
ARG CODE_SERVER_AMD64_SHA256=5674fd8f8d7919a2face58a730c2b46c45e93074dec8c19aff7c9497a7893990
ARG CODE_SERVER_ARM64_SHA256=8ebce24861c4b7ad042c791a1f3262405a156892bb90b3931b9b3e97b5f0580e
ARG CODEX_VERSION=0.149.1
ARG CLAUDE_CODE_VERSION=2.1.246
ARG CCGRAM_VERSION=4.6.5
ARG PIPX_VERSION=1.8.0
ARG MSGPACK_VERSION=1.2.1
ARG SETUPTOOLS_VERSION=84.0.0
ARG BUILD_REVISION=unknown
ARG BUILD_VERSION=dev
ARG BASH_PACKAGE_VERSION=5.2.37-2+b9
ARG BUILD_ESSENTIAL_PACKAGE_VERSION=12.12
ARG CA_CERTIFICATES_PACKAGE_VERSION=20250419
ARG CURL_PACKAGE_VERSION=8.14.1-2+deb13u4
ARG GIT_PACKAGE_VERSION=1:2.47.3-0+deb13u1
ARG JQ_PACKAGE_VERSION=1.7.1-6+deb13u3
ARG LESS_PACKAGE_VERSION=668-1
ARG NANO_PACKAGE_VERSION=8.4-1+deb13u1
ARG OPENSSH_PACKAGE_VERSION=1:10.0p1-7+deb13u4
ARG PROCPS_PACKAGE_VERSION=2:4.0.4-9
ARG RIPGREP_PACKAGE_VERSION=14.1.1-1+b4
ARG SUDO_PACKAGE_VERSION=1.9.16p2-3+deb13u2
ARG TINI_PACKAGE_VERSION=0.19.0-3+b7
ARG VIM_PACKAGE_VERSION=2:9.1.1230-2
ARG WGET_PACKAGE_VERSION=1.25.0-2
ARG UTIL_LINUX_PACKAGE_VERSION=2.41.5-0+deb13u1
ARG LOGIN_PACKAGE_VERSION=1:4.16.0-2+really2.41.5-0+deb13u1

LABEL org.opencontainers.image.title="devctl-workspace" \
      org.opencontainers.image.description="Remote Docker development workspace" \
      org.opencontainers.image.source="https://github.com/lucurlings/devctl" \
      org.opencontainers.image.revision="${BUILD_REVISION}" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      devctl.codex.version="${CODEX_VERSION}" \
      devctl.claude-code.version="${CLAUDE_CODE_VERSION}" \
      devctl.ccgram.version="${CCGRAM_VERSION}" \
      devctl.herdr.version="${HERDR_VERSION}" \
      devctl.code-server.version="${CODE_SERVER_VERSION}"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      "bash=${BASH_PACKAGE_VERSION}" \
      "bsdutils=1:${UTIL_LINUX_PACKAGE_VERSION}" \
      "build-essential=${BUILD_ESSENTIAL_PACKAGE_VERSION}" \
      "ca-certificates=${CA_CERTIFICATES_PACKAGE_VERSION}" \
      "curl=${CURL_PACKAGE_VERSION}" \
      "git=${GIT_PACKAGE_VERSION}" \
      "jq=${JQ_PACKAGE_VERSION}" \
      "less=${LESS_PACKAGE_VERSION}" \
      "login=${LOGIN_PACKAGE_VERSION}" \
      "mount=${UTIL_LINUX_PACKAGE_VERSION}" \
      "nano=${NANO_PACKAGE_VERSION}" \
      "openssh-client=${OPENSSH_PACKAGE_VERSION}" \
      "openssh-server=${OPENSSH_PACKAGE_VERSION}" \
      "procps=${PROCPS_PACKAGE_VERSION}" \
      "ripgrep=${RIPGREP_PACKAGE_VERSION}" \
      "sudo=${SUDO_PACKAGE_VERSION}" \
      "tini=${TINI_PACKAGE_VERSION}" \
      "vim=${VIM_PACKAGE_VERSION}" \
      "wget=${WGET_PACKAGE_VERSION}" \
      "util-linux=${UTIL_LINUX_PACKAGE_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/ssh/ssh_host_* \
    && useradd --create-home --uid 1000 --shell /bin/bash developer \
    && passwd --delete developer \
    && echo 'developer ALL=(ALL) NOPASSWD:ALL' > /etc/sudoers.d/developer \
    && chmod 0440 /etc/sudoers.d/developer \
    && mkdir -p /workspace/project /etc/ssh/devctl-host-keys /run/sshd \
    && chown -R developer:developer /workspace /home/developer

COPY --from=agents /usr/local/ /usr/local/
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/ /usr/local/libexec/docker/cli-plugins/
COPY --from=uv /uv /uvx /usr/local/bin/
COPY images/common/install-release-tools.sh /tmp/install-release-tools.sh
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
RUN chmod +x /tmp/install-release-tools.sh \
    && /tmp/install-release-tools.sh \
    && rm /tmp/install-release-tools.sh \
    && uv pip install --system --no-cache \
      "ccgram==${CCGRAM_VERSION}" \
      "msgpack==${MSGPACK_VERSION}" \
      "pipx==${PIPX_VERSION}" \
      "setuptools==${SETUPTOOLS_VERSION}" \
    && case "$TARGETARCH" in \
         amd64) cs_arch=amd64; cs_sha="$CODE_SERVER_AMD64_SHA256" ;; \
         arm64) cs_arch=arm64; cs_sha="$CODE_SERVER_ARM64_SHA256" ;; \
         *) echo "unsupported architecture: $TARGETARCH" >&2; exit 2 ;; \
       esac \
    && curl --fail --location --silent --show-error \
       --output /tmp/code-server.tar.gz \
       "https://github.com/coder/code-server/releases/download/v${CODE_SERVER_VERSION}/code-server-${CODE_SERVER_VERSION}-linux-${cs_arch}.tar.gz" \
    && echo "${cs_sha}  /tmp/code-server.tar.gz" | sha256sum --check --status \
    && tar -xzf /tmp/code-server.tar.gz -C /opt \
    && ln -s "/opt/code-server-${CODE_SERVER_VERSION}-linux-${cs_arch}/bin/code-server" /usr/local/bin/code-server \
    && rm /tmp/code-server.tar.gz

COPY images/workspace/rootfs/ /
RUN chmod 0755 /usr/local/bin/workspace-entrypoint /usr/local/bin/workspace-supervisor \
      /usr/local/bin/workspace-healthcheck /usr/local/bin/image-versions \
    && chmod 0644 /etc/ssh/sshd_config.d/99-devctl.conf \
      /usr/local/lib/devctl_workspace.py

EXPOSE 22 8080 3000
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/workspace-entrypoint"]
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=12 CMD ["/usr/local/bin/workspace-healthcheck"]
