# Connecting

Full page: https://aartintelligent.github.io/fastsandbox/client/

## API

```text
async fastsandbox.connect(
    socket: str | os.PathLike[str] | None = None,
    *,
    timeout: float | None = None,                # ordinary requests; 30 s by default
    long_operation_timeout: float | None = None, # creations, pulls, commands; 15 min by default
    version_policy: VersionPolicy = "strict",
) -> Client
```

Raises `DaemonUnavailableError` (a `ConnectionError`, with `path`) when the
daemon cannot be reached, and `UnsupportedVersionError` (with `found` and
`supported`) when its API version is outside the supported range and
`version_policy` is `"strict"`. It checks the health of the daemon on the way.

| Name | What it is |
|---|---|
| `SOCKET_ENV` | `"DOCKER_SANDBOXES_API"`, the environment variable that names the socket |
| `default_socket_path() -> Path \| None` | the socket `connect()` uses without `socket`: `$DOCKER_SANDBOXES_API`, else `$XDG_STATE_HOME/sandboxes/sandboxes/sandboxd/sandboxd.sock`, else the same path under `$HOME/.local/state`; `None` when none of these variables is set |
| `SUPPORTED_API` | `(minimum, maximum)` API versions this release was checked against, maximum excluded |
| `VersionPolicy` | `Literal["strict", "warn", "ignore"]` (a type alias of the `types` module of the package, `fastsandbox/types.py`): refuse, log a warning and connect, or connect silently |

### `Client`

| Member | Gives |
|---|---|
| `socket_path: Path` | the socket the client talks to |
| `health: Health` | the health reported when the client connected (`status`, `version`, `api_version`, `is_healthy`); `client.daemon.health()` asks again |
| `kits: KitCache` | the kit cache `create()` takes packages from; `KitCache.default()`, the one of the process, by default |
| `daemon: Daemon` | health, settings, log levels, disk usage |
| `sandboxes: Sandboxes` | list, get, find, create from a request |
| `sandbox(name) -> Sandbox` | the handle of one sandbox; nothing checked until used |
| `images: Images` | the images of the daemon |
| `events: Events`, `prompts: Prompts` | the event and prompt streams |
| `policy: Policy` | the network policy |
| `mcp: Mcp` | the MCP gateway settings |
| `async package(kit) -> KitPackage` | the package of a kit, forged without the `sbx` CLI on first use |
| `create(...) -> Creation` | a new sandbox (see [sandboxes](sandboxes.md)) |

Each property access builds a new, cheap handle. A `Client` can be used as an
async context manager, which releases nothing: connections are opened per
request.

## Example

```python
import fastsandbox
from fastsandbox.exceptions import DaemonUnavailableError, UnsupportedVersionError


async def main() -> None:
    try:
        client = await fastsandbox.connect(timeout=10, version_policy="warn")
    except DaemonUnavailableError as error:
        raise SystemExit(f"Docker Sandboxes is not reachable at {error.path}: run `sbx version`")
    except UnsupportedVersionError as error:
        raise SystemExit(f"daemon API {error.found}, supported {error.supported}")
    print(client.socket_path, client.health.version, fastsandbox.SUPPORTED_API)


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- Docker Sandboxes must be installed and running for the same user: the
  socket lives in that user's state directory.
- `fastsandbox info` prints the socket, the `sbx` version, the API version and
  the supported range; it connects with `"warn"`, so it reports an
  unsupported daemon instead of failing.
- `"warn"` and `"ignore"` connect to a daemon the release was not checked
  against: routes or fields may differ.
- A command can have a deadline of its own, shorter or longer than the
  client's: `await sandbox.exec("make test", timeout=600)`.
- `fastsandbox.run(coro)` runs a coroutine from synchronous code (a script, a
  notebook cell); it cannot be called from a running event loop.
