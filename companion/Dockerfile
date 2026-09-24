FROM docker:29.7.2-cli AS docker-cli
FROM node:24.21.0-bookworm-slim AS node
FROM mcr.microsoft.com/dotnet/sdk:10.0.401-noble@sha256:35d40304542c8689331f8cab17c65926cdf48fe711e289321d71924b230a7d29 AS dotnet

FROM ghcr.io/coder/code-server:4.135.0

# Root is required only while the entrypoint maps the host UID/GID and Docker
# socket group. It drops privileges before starting code-server.
# hadolint ignore=DL3002
USER root

COPY --from=node /usr/local /usr/local
COPY --from=docker-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
COPY --from=dotnet /usr/share/dotnet /usr/share/dotnet

# Debian package revisions are inherited from the pinned code-server image.
# hadolint ignore=DL3008
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        git \
        jq \
        less \
        libgssapi-krb5-2 \
        libicu76 \
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
    && rm -f /usr/local/bin/fixuid \
    && ln -s /usr/share/dotnet/dotnet /usr/local/bin/dotnet \
    && mkdir -p /projects /home/coder/.local/share/code-server /home/coder/.config/code-server

# No optional workloads are installed; the SDK's first-run check cannot update
# its system-wide state as the non-root coder user.
ENV DOTNET_ROOT=/usr/share/dotnet \
    DOTNET_CLI_TELEMETRY_OPTOUT=1 \
    DOTNET_NOLOGO=1 \
    DOTNET_SKIP_WORKLOAD_INTEGRITY_CHECK=true

WORKDIR /projects
EXPOSE 8080 3000

ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/companion-entrypoint"]
CMD ["code-server", "--bind-addr", "0.0.0.0:8080", "--auth", "none", "--disable-telemetry", "/projects"]
