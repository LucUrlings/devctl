# Security boundaries

- The Docker socket in the hub and every workspace is host-equivalent control. Protect access and use only trusted images, repositories, and agents.
- Browser access is privileged development access. Both code-server and preview routes must use the existing Traefik OAuth middleware.
- code-server deliberately has no internal authentication and is never published on a host port.
- SSH binds to server loopback, accepts mounted public keys only, and disables root/password login.
- SSH agent forwarding is supported but not enabled in the generated client configuration. Enable it only for trusted workspaces; the forwarded agent can authorize operations while the connection is open.
- Workspaces share GitHub, Codex, and Claude credentials. Run only trusted repositories.
- No repository setup script executes automatically. Repository URLs cannot contain credentials, and clone arguments are passed as an array after `--`.
- A workspace agent can create, inspect, or remove any host container through the Docker socket. Workspace isolation is not a security boundary against the host.
- Telegram is privileged agent access. Keep the group private and the explicit user allowlist narrow.
- Never commit `hub.env`, project env files containing private values, bot tokens, private SSH keys, `/srv/devctl`, or repository checkouts.

Published images use immutable action SHAs, multi-architecture Buildx builds, SBOM, provenance, and Trivy scanning. Review `.trivyignore` entries before extending their expiry.
