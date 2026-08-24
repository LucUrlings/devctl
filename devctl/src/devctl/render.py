from __future__ import annotations

from collections.abc import Mapping


def hosts(slug: str, values: Mapping[str, str]) -> tuple[str, str]:
    base = values["BASE_DOMAIN"]
    return (
        f"{slug}.{values['CODE_SUBDOMAIN']}.{base}",
        f"{slug}.{values['PREVIEW_SUBDOMAIN']}.{base}",
    )


def traefik_labels(slug: str, values: Mapping[str, str], preview_port: int) -> dict[str, str]:
    code_host, preview_host = hosts(slug, values)
    code_router = f"devctl-{slug}-code"
    preview_router = f"devctl-{slug}-preview"
    labels = {
        "traefik.enable": "true",
        "traefik.docker.network": values["TRAEFIK_NETWORK"],
        f"traefik.http.routers.{code_router}.rule": f"Host(`{code_host}`)",
        f"traefik.http.routers.{code_router}.entrypoints": values["TRAEFIK_ENTRYPOINT"],
        f"traefik.http.routers.{code_router}.tls": "true",
        f"traefik.http.routers.{code_router}.middlewares": values["TRAEFIK_AUTH_MIDDLEWARE"],
        f"traefik.http.routers.{code_router}.service": code_router,
        f"traefik.http.services.{code_router}.loadbalancer.server.port": "8080",
        f"traefik.http.routers.{preview_router}.rule": f"Host(`{preview_host}`)",
        f"traefik.http.routers.{preview_router}.entrypoints": values["TRAEFIK_ENTRYPOINT"],
        f"traefik.http.routers.{preview_router}.tls": "true",
        f"traefik.http.routers.{preview_router}.middlewares": values["TRAEFIK_AUTH_MIDDLEWARE"],
        f"traefik.http.routers.{preview_router}.service": preview_router,
        f"traefik.http.services.{preview_router}.loadbalancer.server.port": str(preview_port),
    }
    resolver = values.get("TRAEFIK_CERT_RESOLVER", "")
    if resolver:
        labels[f"traefik.http.routers.{code_router}.tls.certresolver"] = resolver
        labels[f"traefik.http.routers.{preview_router}.tls.certresolver"] = resolver
    return labels


def ssh_config(slug: str, port: int, values: Mapping[str, str]) -> str:
    return (
        f"Host dev-{slug}\n"
        "    HostName 127.0.0.1\n"
        f"    Port {port}\n"
        "    User developer\n"
        f"    ProxyJump {values['SSH_JUMP_HOST']}\n"
        f"    IdentityFile {values['SSH_IDENTITY_FILE']}\n"
    )
