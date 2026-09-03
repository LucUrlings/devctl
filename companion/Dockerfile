FROM docker:29.7.2-cli AS docker-cli

FROM ghcr.io/coder/code-server:4.135.0

# Root is required only while the entrypoint maps the host UID/GID and Docker
# socket group. It drops privileges before starting code-server.
# hadolint ignore=DL3002
USER root

COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins

# Debian package revisions are inherited from the pinned code-server image.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
        less \
        nano \
        procps \
        python3 \
        python3-pip \
        python3-venv \
        ripgrep \
        tini \
        wget \
    && rm -rf /var/lib/apt/lists/*

COPY companion/entrypoint.sh /usr/local/bin/companion-entrypoint

RUN chmod 0755 /usr/local/bin/companion-entrypoint \
    && mkdir -p /projects /home/coder/.local/share/code-server /home/coder/.config/code-server

WORKDIR /projects
EXPOSE 8080 3000

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/companion-entrypoint"]
CMD ["code-server", "--bind-addr", "0.0.0.0:8080", "--auth", "none", "--disable-telemetry", "/projects"]
