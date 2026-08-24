# Security

Devctl assumes a single trusted operator/security domain. Repositories and agents can read project files and the shared GitHub, Codex, and Claude credential stores. Review repository trust before creating a workspace.

Required boundaries:

- All HTTP routes use the existing Google OAuth Traefik middleware.
- Telegram requires explicit user and group allowlists.
- SSH uses mounted public keys only, disables root/password login, and binds host ports to `127.0.0.1`.
- No private SSH key is baked into or mounted by the default images.
- Only the hub gets the Docker socket by default.
- Host Docker socket mode requires an explicit project option and grants effective host root.
- Repository URLs cannot include credentials. Tokens are not logged or stored in labels/config examples.
- Repository clone commands use argument arrays and `--` before URL/path operands.
- Existing data is never overwritten when a checkout is non-empty or has a different origin.
- Repository-provided setup files are never auto-executed.
- Project names are strict slugs used only after validation.
- Project state and metadata are written atomically with restrictive permissions.
- Purge validates a direct child path and requires exact confirmation (or explicit `--yes`).

The hub socket mount is the largest trust decision: `/var/run/docker.sock` permits starting privileged containers and mounting arbitrary host paths. Protect hub shell access, image provenance, GHCR permissions, and Telegram access accordingly.

The Trivy workflow fails on fixed high/critical image vulnerabilities. `.trivyignore` exceptions require an adjacent owner, justification, and expiry comment. Current short-lived exceptions cover only vulnerabilities in the latest stable upstream Docker, GitHub CLI, npm, code-server, and setuptools bundles, plus stale base-image SBOM records whose active installed versions were verified as fixed. They expire on 2026-09-30 and must be removed when upstream releases become available; the security workflow will then enforce the new result. GitHub Actions use immutable commit SHAs, and published images include OCI source/revision labels, SBOM, provenance, and GitHub artifact attestations.
