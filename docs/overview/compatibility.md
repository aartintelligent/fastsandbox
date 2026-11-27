# Compatibility

## Docker Sandboxes

fastsandbox is a client of [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/)
and needs it on the machine it runs on: it connects to the Unix socket of its
daemon, `sandboxd`, and does nothing without it.

| | |
|---|---|
| Platforms | Linux and macOS, where Docker Sandboxes runs |
| The daemon | Installed and running for the current user: `sbx version` answers |
| The `sbx` CLI | Only to compile a [kit](../client/kits.md) the forge cannot make, when asked |
| The socket API | The range of versions in [`SUPPORTED_API`][fastsandbox.SUPPORTED_API] |

The `sandboxd` socket API is private and changes with `sbx` releases. Each
release of fastsandbox is checked against a range of API versions, and
`connect()` refuses a daemon outside it unless told otherwise;
[The API version](../client/index.md#the-api-version) explains the policy, and
`fastsandbox info` prints the version of the daemon next to the supported
range.

## Python

| | |
|---|---|
| Python | 3.12 or newer: CPython 3.12, 3.13 and 3.14 |
| Wheels | CPython 3.12 and later (abi3), Linux x86_64 and aarch64, macOS x86_64 and arm64 |
| Dependencies | Pydantic 2 |
| Typing | Typed (`py.typed`), checked with mypy in strict mode against Python 3.12 |
| Tested | Python 3.12, 3.13 and 3.14 on Linux on every change, and 3.12 and 3.14 on macOS when the package or the extension changes; the wheel is installed and imported on each version |
| Not supported | The free-threaded builds of CPython (`3.13t`, `3.14t`): abi3 wheels do not install on them |

The wheels hold the native extension, so nothing is compiled on installation.
Building from source needs a Rust toolchain (1.88 or newer) and
[uv](https://docs.astral.sh/uv/); see [Installation](../get-started/installation.md).

## Agents

The agents of `@app.agent` are those `sbx` knows, by the name of their kit:
`claude`, `codex`, `copilot`, `cursor`, `devin`, `docker-agent`, `droid`,
`kiro` and `opencode`. The credentials each one reads from the environment
are listed on the [agents page](../framework/agents.md#the-agents).

## Versioning

fastsandbox is in alpha, published on [PyPI](https://pypi.org/project/fastsandbox/).
Its versions are derived from the Conventional Commits since the last release:
before 1.0, a breaking change bumps the minor version and a feature the patch
version. The changelog is generated from the same commits.
