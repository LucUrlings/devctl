variable "REGISTRY" { default = "ghcr.io" }
variable "OWNER" { default = "lucurlings" }
variable "VERSION" { default = "dev" }
variable "REVISION" { default = "unknown" }

target "versions" {
  args = {
    PYTHON_VERSION = "3.14.7"
    NODE_VERSION = "24.19.0"
    NPM_VERSION = "12.0.2"
    DOCKER_CLI_VERSION = "29.7.2"
    CODEX_VERSION = "0.149.1"
    CLAUDE_CODE_VERSION = "2.1.246"
    HERDR_VERSION = "0.8.2"
    CCGRAM_VERSION = "4.6.5"
    CODE_SERVER_VERSION = "4.134.0"
    GH_VERSION = "2.98.0"
    UV_VERSION = "0.12.5"
    PIPX_VERSION = "1.8.0"
    MSGPACK_VERSION = "1.2.1"
    SETUPTOOLS_VERSION = "84.0.0"
    BASH_PACKAGE_VERSION = "5.2.37-2+b9"
    BUILD_ESSENTIAL_PACKAGE_VERSION = "12.12"
    CA_CERTIFICATES_PACKAGE_VERSION = "20250419"
    CURL_PACKAGE_VERSION = "8.14.1-2+deb13u4"
    GIT_PACKAGE_VERSION = "1:2.47.3-0+deb13u1"
    JQ_PACKAGE_VERSION = "1.7.1-6+deb13u3"
    LESS_PACKAGE_VERSION = "668-1"
    NANO_PACKAGE_VERSION = "8.4-1+deb13u1"
    OPENSSH_PACKAGE_VERSION = "1:10.0p1-7+deb13u4"
    PROCPS_PACKAGE_VERSION = "2:4.0.4-9"
    RIPGREP_PACKAGE_VERSION = "14.1.1-1+b4"
    SUDO_PACKAGE_VERSION = "1.9.16p2-3+deb13u2"
    TINI_PACKAGE_VERSION = "0.19.0-3+b7"
    VIM_PACKAGE_VERSION = "2:9.1.1230-2"
    WGET_PACKAGE_VERSION = "1.25.0-2"
    UTIL_LINUX_PACKAGE_VERSION = "2.41.5-0+deb13u1"
    LOGIN_PACKAGE_VERSION = "1:4.16.0-2+really2.41.5-0+deb13u1"
    HERDR_AMD64_SHA256 = "976150a14d490c94b243ea2e1a7eb2dfb67f12e36b182db90936f6728e6aecf4"
    HERDR_ARM64_SHA256 = "f55610658e1c2e0d2aaef730b4b2ab885f7f8ba00285ab372bfb14f2e3d5b40d"
    CODE_SERVER_AMD64_SHA256 = "5674fd8f8d7919a2face58a730c2b46c45e93074dec8c19aff7c9497a7893990"
    CODE_SERVER_ARM64_SHA256 = "8ebce24861c4b7ad042c791a1f3262405a156892bb90b3931b9b3e97b5f0580e"
    GH_AMD64_SHA256 = "3b8ac6b30336802fc1a858d7c084e11cdf24ac1a761ca90b68022d7d729208de"
    GH_ARM64_SHA256 = "cf689084f3a3618f7eae4a2420d335d74626d65f5e594b9828d125d69f800d86"
    BUILD_VERSION = VERSION
    BUILD_REVISION = REVISION
  }
}

target "hub" {
  inherits = ["versions"]
  context = "."
  dockerfile = "images/hub/Dockerfile"
  platforms = ["linux/amd64", "linux/arm64"]
  tags = ["${REGISTRY}/${OWNER}/devctl-hub:${VERSION}"]
}

target "workspace" {
  inherits = ["versions"]
  context = "."
  dockerfile = "images/workspace/Dockerfile"
  platforms = ["linux/amd64", "linux/arm64"]
  tags = ["${REGISTRY}/${OWNER}/devctl-workspace:${VERSION}"]
}

group "default" { targets = ["hub", "workspace"] }
