.PHONY: format lint typecheck test check compose-check bake-check build smoke

format:
	python3 -m ruff format devctl
	python3 -m ruff check --fix devctl

lint:
	python3 -m ruff format --check devctl
	python3 -m ruff check devctl
	shellcheck scripts/*.sh scripts/devctl-host images/common/*.sh \
		images/hub/rootfs/usr/local/bin/ccgram-launch \
		images/hub/rootfs/usr/local/bin/dev-enter \
		images/hub/rootfs/usr/local/bin/devctl-versions \
		images/hub/rootfs/usr/local/bin/herdr-server-launch \
		images/hub/rootfs/usr/local/bin/hub-entrypoint \
		images/hub/rootfs/usr/local/bin/hub-healthcheck \
		images/workspace/rootfs/usr/local/bin/devctl-versions

typecheck:
	cd devctl && python3 -m mypy src

test:
	cd devctl && python3 -m pytest

compose-check:
	./scripts/validate-compose.sh

bake-check:
	docker buildx bake --print >/dev/null

check: lint typecheck test compose-check bake-check

build:
	docker buildx bake --load --set '*.platform=linux/amd64'

smoke:
	./scripts/smoke-test.sh
