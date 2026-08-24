# Traefik integration

Set these values in `/srv/devctl/config/devctl.env`:

```env
TRAEFIK_NETWORK=proxy
TRAEFIK_ENTRYPOINT=websecure
TRAEFIK_AUTH_MIDDLEWARE=google-oauth@docker
TRAEFIK_CERT_RESOLVER=letsencrypt
BASE_DOMAIN=example.com
CODE_SUBDOMAIN=code
PREVIEW_SUBDOMAIN=dev
```

The network must already exist and must be attached to the existing Traefik container. The middleware name must include its provider suffix when required. Devctl applies it to both project routers.

Configure DNS for `*.code.example.com` and `*.dev.example.com` (or explicit records per project) to resolve to Traefik. Your certificate resolver must be able to obtain certificates for these hosts; DNS-01 wildcard certificates are usually the cleanest option.

code-server listens internally on `0.0.0.0:8080` with `auth: none`. This is safe only because the service is not host-published and every Traefik route is protected by the existing OAuth middleware. Traefik forwards WebSockets automatically. Preview port traffic is likewise network-only.

Use `devctl urls <project>` and inspect Docker labels when diagnosing a route. Never bypass OAuth by publishing 8080 or the preview port on a public interface.
