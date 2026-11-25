# MCP gateway

Full page: https://aartintelligent.github.io/fastsandbox/client/mcp/

Each sandbox has an MCP gateway: the agent inside reaches the servers it
serves at `http://mcp-gateway.docker.internal/mcp`. Servers are registered on
the host with the `sbx` CLI (`sbx mcp add`), then loaded into the gateway of a
sandbox.

## API

### `client.mcp` (`Mcp`), the settings of the daemon

| Call | Gives |
|---|---|
| `await gateway_mode() -> GatewayMode` | `decision` (e.g. `local`), `gateway_url`, `reason` |
| `await check_registration(server: McpServerCheck) -> RegistrationCheck` | `allowed`, `name`: whether the MCP policy lets `sbx mcp add` register it; nothing is registered |

`McpServerCheck.local(name, command: list[str])` and
`McpServerCheck.remote(name, url)` build the server to check.

### The gateway of a sandbox

| Call | Gives |
|---|---|
| `await sandbox.mcp_gateway() -> McpGateway` | `state`, `url` inside the sandbox, `port` on the host, `static_servers`, `servers` loaded |
| `await sandbox.load_mcp_server(server) -> LoadedServer` | loads a registered server (`sandbox`, `server`); `NotFoundError` when not registered |
| `await sandbox.unload_mcp_server(server)` | unloads it; `NotFoundError` when not loaded |

A static gateway is chosen at creation, from a kit package request:
`package.request(name).with_static_mcp_servers("docs-tools")`, then
`client.create(kit=package, request=request)`.

## Example

```python
import fastsandbox
from fastsandbox.models import McpServerCheck


async def main() -> None:
    client = await fastsandbox.connect()
    mode = await client.mcp.gateway_mode()
    print(f"gateway: {mode.decision}")
    check = await client.mcp.check_registration(
        McpServerCheck.remote("docs-tools", "https://mcp.example.com/mcp")
    )
    print(f"{check.name} may be registered: {check.allowed}")

    async with client.create(kit="shell") as sandbox, sandbox.running():
        await sandbox.load_mcp_server("docs-tools")  # registered with `sbx mcp add docs-tools ...`
        gateway = await sandbox.mcp_gateway()
        print(f"{gateway.url} serves {gateway.servers}")
        await sandbox.unload_mcp_server("docs-tools")


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- By default the gateway is dynamic: it also offers `mcp-find` and `mcp-add`,
  so the agent can load any registered server itself; a server added this way
  stays loaded until the program unloads it. A static gateway offers only its
  servers (plus `mcp-exec` and `code-mode`).
- Tool names are not prefixed by server: two servers with a tool of the same
  name cannot be loaded together.
- The gateway port on the host answers 401 to requests that do not come
  through the sandbox proxy.
- A remote server's token is stored as the `sbx` secret
  `mcp:<server>:<placeholder>`; the gateway fills the header, the sandbox never
  holds it. After the secret changes, unload and load the server again.
- Registering a server (`sbx mcp add`) changes global state: a program that
  registers one, or stores a dummy `mcp:` secret, removes it when done.
