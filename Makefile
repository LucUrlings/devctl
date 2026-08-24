.PHONY: test lint compose-check bake-check check build smoke

test:
	python3 -m unittest discover -s tests -v

lint:
	shellcheck scripts/*.sh images/common/*.sh \
		images/hub/rootfs/usr/local/bin/ccgram-launch \
		images/hub/rootfs/usr/local/bin/dev-enter \
		images/hub/rootfs/usr/local/bin/herdr-server-launch \
		images/hub/rootfs/usr/local/bin/hub-entrypoint \
		images/hub/rootfs/usr/local/bin/hub-healthcheck \
		images/hub/rootfs/usr/local/bin/image-versions \
		images/workspace/rootfs/usr/local/bin/image-versions

compose-check:
	./scripts/validate-compose.sh

bake-check:
	docker buildx bake --print >/dev/null

check: test lint compose-check bake-check

build:
	docker buildx bake --load --set '*.platform=linux/amd64'

smoke:
	./scripts/smoke-test.sh
