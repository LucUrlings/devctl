# Troubleshooting and recovery

Run `devctl doctor` first. It checks Docker/Compose, configuration, the Traefik network, writable state, authorized keys, Herdr, CCGram, shared authentication, and port availability.

## Hub container restart

Compose restarts the supervised Herdr and CCGram processes against persisted state. Confirm `herdr status server`, the socket, and `ccgram status`. A normal client detach does not stop pane processes; a full server stop may.

## Workspace restart or server reboot

The entrypoint sees `.git`, verifies `origin`, and skips cloning. SSH host keys, VS Code server data, checkout, and shared authentication survive. After a full reboot, Docker's `unless-stopped` policy brings the hub and running workspaces back. Confirm Traefik and its external network independently.

## Image upgrade

Back up `/srv/devctl`, pull the new images, recreate the hub, and restart one workspace as a canary. Run `devctl-versions` inside each image and `devctl doctor` after the upgrade.

## Clone failure

Read workspace logs. Fix network, URL, branch, or GitHub authentication; do not add files to the checkout directory. If a failed clone left partial data, inspect it manually and move it aside only after confirming the exact project directory. Devctl will not delete it automatically.

## Agent authentication expiry

Run `devctl auth status`, then repeat `devctl auth codex`, `devctl auth claude`, or `devctl auth github`. Shared files are refreshed for every workspace.

## SSH host key mismatch

First verify the server and project were intentionally purged/recreated. Remove only the stale key for the generated alias/port, for example with `ssh-keygen -R '[127.0.0.1]:<port>'`, then reconnect through the jump host. An unexpected change can indicate interception and must be investigated.

## Herdr restoration

Reattach after a normal detach with `devctl herdr attach`. After a complete server stop, topology can be restored from Herdr state, but container-wrapped Codex/Claude native sessions are not guaranteed to resume automatically. Start a new agent tab and use the provider's supported session resume flow.
