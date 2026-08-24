# VS Code Remote SSH

Workspace SSH uses key authentication only, rejects root/password logins, allows forwarding needed by Remote SSH, and persists unique host keys under the project directory. Each port is allocated from `22000-22999` and bound to server loopback.

Create the jump-host entry locally:

```ssh-config
Host dev-server
    HostName server.example.com
    User server-user
    IdentityFile ~/.ssh/id_ed25519
```

Append `devctl ssh-config <project>` output to local `~/.ssh/config`. Test with `ssh dev-<project>`, install the VS Code Remote SSH extension, connect to that alias, and open `/workspace/project`.

Disconnecting SSH or closing VS Code does not stop the workspace. Reconnect with `ssh dev-<project>` or select the same Remote SSH host again. The project keeps its allocated port, repository bind mount, unique SSH host keys, and `/home/developer/.vscode-server` data across workspace restarts and server reboots. This preserves host-key verification and avoids reinstalling the VS Code server after container recreation.

The SSH server supplies fixed `CODEX_HOME`, `CLAUDE_CONFIG_DIR`, `GH_CONFIG_DIR`,
`HERDR_SOCKET_PATH`, `CCGRAM_DIR`, and `WORKSPACE_PATH` values, so tools launched from VS Code or a
plain SSH terminal use the same mounted state as tools launched by `dev-enter`. Clients cannot
override these paths through `PermitUserEnvironment`.

The `developer` account is enabled for public-key login, while password and keyboard-interactive authentication remain disabled in `sshd`. Never place the private identity file inside a workspace; it remains on the client and authenticates through the jump host.
