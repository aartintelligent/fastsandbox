# Ports

Full page: https://aartintelligent.github.io/fastsandbox/client/ports/

## API

`PortBinding(sandbox_port: int, host_port: int, host_ip: str | None = None,
protocol: str | None = None)`; `PortBinding.tcp(sandbox_port, host_port,
host_ip=None)` and `PortBinding.udp(...)` build one. The host port binds on
`127.0.0.1` unless `host_ip` says otherwise.

| Call | What it does |
|---|---|
| `client.create(..., ports=[...])` | the *desired* ports, published at every start |
| `await sandbox.replace_desired_port(old, new)` | changes one desired port for the next start; `NotFoundError` when `old` is not desired |
| `await sandbox.publish(*ports) -> list[PortBinding]` | publishes on the running sandbox, returns what the daemon applied; `ConflictError` when stopped or the host port is taken |
| `await sandbox.unpublish(*ports)` | takes them back; an unpublished port is ignored |
| `await sandbox.ports() -> list[PortBinding]` | the ports published now |

## Example

```python
import asyncio

import fastsandbox
from fastsandbox.models import PortBinding


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        # A server runs as an interactive session: exec() would wait for its end.
        server = await sandbox.attach(["python3", "-u", "-m", "http.server", "8000"])
        published = await sandbox.publish(PortBinding.tcp(8000, 48000))
        for port in published:
            print(f"{port.host_ip or '127.0.0.1'}:{port.host_port} -> {port.sandbox_port}")
        await asyncio.sleep(2)  # retry connections for a few seconds after publishing
        await sandbox.unpublish(*published)
        print(f"server session {server.id}: it ends with the sandbox")


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- Right after a publication, a connection to the host port may be refused or
  reset: retry it for a few seconds.
- `ports` given at creation come back at every start; `publish()` lasts until
  unpublished or the sandbox stops.
- `SandboxInfo.ports` is filled in single-sandbox answers (`inspect()`), not
  in `sandboxes.list()`.
- Port events (`EventKind.SANDBOX_PORTS`) show publications on the event
  stream (see [events](events.md)).
