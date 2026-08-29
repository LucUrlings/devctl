# syntax=docker/dockerfile:1.12
ARG NODE_VERSION=24.19.0
ARG NPM_VERSION=12.0.2
ARG PYTHON_VERSION=3.14.7
ARG DOCKER_CLI_VERSION=29.7.2
ARG UV_VERSION=0.12.5

FROM node:${NODE_VERSION}-trixie-slim AS agents
ARG CODEX_VERSION=0.150.1
ARG CLAUDE_CODE_VERSION=2.1.248
ARG NPM_VERSION
ENV NPM_CONFIG_PREFIX=/opt/user-local \
    PATH=/opt/user-local/bin:${PATH}
RUN npm install --global --ignore-scripts=false \
      --allow-scripts=@anthropic-ai/claude-code \
      "@openai/codex@${CODEX_VERSION}" \
      "@anthropic-ai/claude-code@${CLAUDE_CODE_VERSION}" \
    && npm install --global "npm@${NPM_VERSION}" \
    && npm cache clean --force

FROM docker:${DOCKER_CLI_VERSION}-cli-alpine3.24 AS dockercli
FROM ghcr.io/astral-sh/uv:${UV_VERSION} AS uv
FROM python:${PYTHON_VERSION}-slim-trixie

# Login commands run as developer. Keep agent CLIs in its writable npm prefix;
# the central Herdr server itself remains an image-managed system binary.
ENV NPM_CONFIG_PREFIX=/home/developer/.local \
    UV_TOOL_BIN_DIR=/home/developer/.local/bin \
    UV_TOOL_DIR=/home/developer/.local/share/uv/tools \
    PATH=/home/developer/.local/bin:${PATH}

ARG TARGETARCH
ARG HERDR_VERSION=0.8.2
ARG CCGRAM_VERSION=4.6.8
ARG CODEX_VERSION=0.150.1
ARG CLAUDE_CODE_VERSION=2.1.248
ARG MSGPACK_VERSION=1.2.1
ARG SETUPTOOLS_VERSION=84.0.0
ARG GH_VERSION=2.98.0
ARG HERDR_AMD64_SHA256=976150a14d490c94b243ea2e1a7eb2dfb67f12e36b182db90936f6728e6aecf4
ARG HERDR_ARM64_SHA256=f55610658e1c2e0d2aaef730b4b2ab885f7f8ba00285ab372bfb14f2e3d5b40d
ARG GH_AMD64_SHA256=3b8ac6b30336802fc1a858d7c084e11cdf24ac1a761ca90b68022d7d729208de
ARG GH_ARM64_SHA256=cf689084f3a3618f7eae4a2420d335d74626d65f5e594b9828d125d69f800d86
ARG BUILD_REVISION=unknown
ARG BUILD_VERSION=dev
ARG BASH_PACKAGE_VERSION=5.2.37-2+b9
ARG CA_CERTIFICATES_PACKAGE_VERSION=20250419
ARG CURL_PACKAGE_VERSION=8.14.1-2+deb13u4
ARG GIT_PACKAGE_VERSION=1:2.47.3-0+deb13u1
ARG JQ_PACKAGE_VERSION=1.7.1-6+deb13u3
ARG OPENSSH_PACKAGE_VERSION=1:10.0p1-7+deb13u4
ARG OPENSSL_PACKAGE_VERSION=3.5.7-1~deb13u2
ARG PROCPS_PACKAGE_VERSION=2:4.0.4-9
ARG RIPGREP_PACKAGE_VERSION=14.1.1-1+b4
ARG TINI_PACKAGE_VERSION=0.19.0-3+b7
ARG UTIL_LINUX_PACKAGE_VERSION=2.41.5-0+deb13u1
ARG LOGIN_PACKAGE_VERSION=1:4.16.0-2+really2.41.5-0+deb13u1

LABEL org.opencontainers.image.title="devctl-hub" \
      org.opencontainers.image.description="Devctl central Herdr and CCGram control plane" \
      org.opencontainers.image.source="https://github.com/lucurlings/devctl" \
      org.opencontainers.image.revision="${BUILD_REVISION}" \
      org.opencontainers.image.version="${BUILD_VERSION}" \
      org.opencontainers.image.licenses="Apache-2.0" \
      devctl.herdr.version="${HERDR_VERSION}" \
      devctl.ccgram.version="${CCGRAM_VERSION}" \
      devctl.codex.version="${CODEX_VERSION}" \
      devctl.claude-code.version="${CLAUDE_CODE_VERSION}"

RUN apt-get update \
    && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      "bash=${BASH_PACKAGE_VERSION}" \
      "bsdutils=1:${UTIL_LINUX_PACKAGE_VERSION}" \
      "ca-certificates=${CA_CERTIFICATES_PACKAGE_VERSION}" \
      "curl=${CURL_PACKAGE_VERSION}" \
      "git=${GIT_PACKAGE_VERSION}" \
      "jq=${JQ_PACKAGE_VERSION}" \
      "login=${LOGIN_PACKAGE_VERSION}" \
      "mount=${UTIL_LINUX_PACKAGE_VERSION}" \
      "openssh-client=${OPENSSH_PACKAGE_VERSION}" \
      "openssl=${OPENSSL_PACKAGE_VERSION}" \
      "procps=${PROCPS_PACKAGE_VERSION}" \
      "ripgrep=${RIPGREP_PACKAGE_VERSION}" \
      "tini=${TINI_PACKAGE_VERSION}" \
      "util-linux=${UTIL_LINUX_PACKAGE_VERSION}" \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 1000 --shell /bin/bash developer \
    && ln -s /srv/devctl/shared/codex /home/developer/.codex

COPY --from=agents /usr/local/ /usr/local/
COPY --from=agents --chown=developer:developer /opt/user-local/ /home/developer/.local/
COPY --from=dockercli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=dockercli /usr/local/libexec/docker/cli-plugins/ /usr/local/libexec/docker/cli-plugins/
COPY --from=uv /uv /uvx /usr/local/bin/
COPY images/common/install-release-tools.sh /tmp/install-release-tools.sh
RUN rm -rf /usr/local/lib/node_modules/npm \
    && rm -f /usr/local/bin/npm /usr/local/bin/npx \
    && chmod +x /tmp/install-release-tools.sh \
    && GH_INSTALL_DIR=/home/developer/.local/bin /tmp/install-release-tools.sh \
    && rm /tmp/install-release-tools.sh \
    && chown -R developer:developer /home/developer/.local \
    && printf 'ccgram==%s\n' "${CCGRAM_VERSION}" > /tmp/ccgram-constraint.txt \
    && runuser --user developer -- env HOME=/home/developer \
      uv tool install --python /usr/local/bin/python3 --no-python-downloads \
      --constraint /tmp/ccgram-constraint.txt \
      --with "msgpack==${MSGPACK_VERSION}" \
      --with "setuptools==${SETUPTOOLS_VERSION}" \
      ccgram \
    # Keep the deterministic initial version while allowing CCGram's supported
    # `uv tool upgrade ccgram` command to select a newer release at runtime.
    && sed -i '/^constraints = /d' "${UV_TOOL_DIR}/ccgram/uv-receipt.toml" \
    && rm /tmp/ccgram-constraint.txt

COPY images/hub/rootfs/ /
RUN chmod 0755 /usr/local/bin/dev-enter /usr/local/bin/dev-session \
      /usr/local/bin/hub-reconcile \
      /usr/local/bin/hub-entrypoint \
      /usr/local/bin/herdr-server-launch /usr/local/bin/ccgram-launch \
      /usr/local/bin/ccgram-runtime /usr/local/bin/ccgram-runtime-launch \
      /usr/local/bin/hub-healthcheck /usr/local/bin/image-versions

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/hub-entrypoint"]
CMD ["herdr"]
