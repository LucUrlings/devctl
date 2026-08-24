# Installation

## Verify the target

Point the generic `dev-server` SSH alias at the intended host, then verify the target and Docker context:

```bash
ssh dev-server 'hostname -f; uname -m; docker info --format "{{.ServerVersion}}"; docker compose version'
```

The architecture must map to `linux/amd64` or `linux/arm64`. Confirm `/srv/devctl` is the intended persistent location and that no unrelated data will be replaced.

## Install the packaged command

The server does not need this repository. A release contains one architecture-independent launcher as a Debian package and a portable tarball.

For Debian or Ubuntu, download the release package with an authenticated GitHub CLI, then install it through APT:

```bash
gh release download --repo LucUrlings/devctl --pattern 'devctl_*_all.deb'
sudo apt install ./devctl_*_all.deb
```

Alternatively, download the package on a trusted workstation, verify it against `SHA256SUMS`, copy it to the server, and run the same `apt install` command. For another Linux distribution, extract `devctl-<version>-linux-all.tar.gz`, verify its checksum, and install the executable:

```bash
sudo install -m 0755 devctl /usr/local/bin/devctl
```

Authenticate Docker to the private GHCR packages with a token that can read packages, then bootstrap the hub:

```bash
sudo devctl init
sudo editor /srv/devctl/config/devctl.env
sudo editor /srv/devctl/ssh/authorized_keys
devctl doctor
```

Set `BASE_DOMAIN`, `TRAEFIK_NETWORK`, and `TRAEFIK_AUTH_MIDDLEWARE` before creating a project. Put public SSH keys only in `authorized_keys`. The launcher generates `/srv/devctl/state/hub.compose.yml`; do not edit it because `sudo devctl init` regenerates it.

The server now contains only the launcher and runtime data:

```text
/usr/bin/devctl
/srv/devctl/
├── config/
├── secrets/
├── shared/
├── herdr/
├── ccgram/
├── projects/
├── ssh/
└── state/
```

No Git checkout, Dockerfile, test suite, or documentation tree is installed. Initialization does not touch Traefik or any unrelated container or network.

## Images and upgrades

Both images support amd64 and arm64. Tags on `main` are `latest`, `main`, and `sha-<short-sha>`. After a successful build, CI automatically increments the patch version, creates the Git tag and GitHub release, publishes the CLI packages, and adds the matching `1.2.3`, `1.2`, and `1` image tags. `DEVCTL_VERSION` is only the minimum used for an intentional minor or major jump. Builds attach SBOM and max-mode provenance.

Install the new launcher package, back up `/srv/devctl`, and upgrade the hub:

```bash
sudo apt install ./devctl_<version>_all.deb
sudo devctl upgrade
```

Pull the configured workspace image and recreate one workspace as a canary with `devctl stop <project>` followed by `devctl start <project>`. A plain `devctl restart` only restarts the existing container. The checkout, shared credentials, host keys, and VS Code server directory remain bind-mounted.
