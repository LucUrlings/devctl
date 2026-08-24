from devctl.render import ssh_config, traefik_labels

VALUES = {
    "BASE_DOMAIN": "example.test",
    "CODE_SUBDOMAIN": "code",
    "PREVIEW_SUBDOMAIN": "dev",
    "TRAEFIK_NETWORK": "proxy",
    "TRAEFIK_ENTRYPOINT": "websecure",
    "TRAEFIK_AUTH_MIDDLEWARE": "google-oauth@docker",
    "TRAEFIK_CERT_RESOLVER": "letsencrypt",
    "SSH_JUMP_HOST": "dev-server",
    "SSH_IDENTITY_FILE": "~/.ssh/id_ed25519",
}


def test_generated_traefik_labels_are_unique_and_protected() -> None:
    labels = traefik_labels("project-one", VALUES, 4173)
    assert (
        labels["traefik.http.routers.devctl-project-one-code.rule"]
        == "Host(`project-one.code.example.test`)"
    )
    assert (
        labels["traefik.http.routers.devctl-project-one-preview.rule"]
        == "Host(`project-one.dev.example.test`)"
    )
    assert (
        labels["traefik.http.routers.devctl-project-one-code.middlewares"] == "google-oauth@docker"
    )
    assert (
        labels["traefik.http.routers.devctl-project-one-preview.middlewares"]
        == "google-oauth@docker"
    )
    assert (
        labels["traefik.http.services.devctl-project-one-code.loadbalancer.server.port"] == "8080"
    )
    assert (
        labels["traefik.http.services.devctl-project-one-preview.loadbalancer.server.port"]
        == "4173"
    )


def test_generated_ssh_config_uses_proxyjump() -> None:
    value = ssh_config("project-one", 22101, VALUES)
    assert "Host dev-project-one" in value
    assert "Port 22101" in value
    assert "ProxyJump dev-server" in value
    assert "User developer" in value
