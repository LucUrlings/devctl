# Security boundaries

- The hub's Docker socket is host-equivalent control. Protect hub access and use only trusted images.
- Browser access is privileged development access. Both code-server and preview routes must use the existing Traefik OAuth middleware.
- code-server deliberately has no internal authentication and is never published on a host port.
- SSH binds to server loopback, accepts mounted public keys only, and disables root/password login.
- Workspaces share GitHub, Codex, and Claude credentials. Run only trusted repositories.
- No repository setup script executes automatically. Repository URLs cannot contain credentials, and clone arguments are passed as an array after `--`.
- Workspaces have no Docker socket by default. The override grants effective root and is only for trusted projects.
- Telegram is privileged agent access. Keep the group private and the explicit user allowlist narrow.
- Never commit `hub.env`, project env files containing private values, bot tokens, private SSH keys, `/srv/devctl`, or repository checkouts.

Published images use immutable action SHAs, multi-architecture Buildx builds, SBOM, provenance, and Trivy scanning. Review `.trivyignore` entries before extending their expiry.
