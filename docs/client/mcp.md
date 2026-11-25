# MCP gateway

Each sandbox has an MCP gateway: the agent in the sandbox reaches the MCP
servers the gateway serves at one URL,
`http://mcp-gateway.docker.internal/mcp`. The servers are registered on the
host with the `sbx` CLI (`sbx mcp add`), then loaded into the gateway of a
sandbox on demand. This page covers the settings of the daemon, the gateway of
a sandbox, and the static and dynamic gateways.

```python title="docs_src/client/mcp.py" hl_lines="7 12 17 18 20"
--8<-- "docs_src/client/mcp.py"
```

## The settings of the daemon

[`client.mcp`][fastsandbox.Mcp] reaches what the daemon decides for every
sandbox:

- [`gateway_mode()`][fastsandbox.Mcp.gateway_mode] says which gateway runs the
  servers, a [`GatewayMode`][fastsandbox.models.GatewayMode]: its `decision`,
  `local` for instance, and why;
- [`check_registration(server)`][fastsandbox.Mcp.check_registration] says
  whether the MCP policy lets a server be registered, before `sbx mcp add`
  does it: a local server, `McpServerCheck.local(name, command)`, or a remote
  one, `McpServerCheck.remote(name, url)`. Nothing is registered.

## The gateway of a sandbox

| Call | What it does |
|---|---|
| [`mcp_gateway()`][fastsandbox.Sandbox.mcp_gateway] | the gateway, a [`McpGateway`][fastsandbox.models.McpGateway]: its state, its `url` inside the sandbox, its port on the host, whether its servers are static, and the `servers` loaded |
| [`load_mcp_server(server)`][fastsandbox.Sandbox.load_mcp_server] | loads a registered server into the gateway; [`NotFoundError`][fastsandbox.exceptions.NotFoundError] when it is not registered |
| [`unload_mcp_server(server)`][fastsandbox.Sandbox.unload_mcp_server] | unloads it; [`NotFoundError`][fastsandbox.exceptions.NotFoundError] when it is not loaded |

The gateway answers inside the sandbox only: its port on the host answers
`401 Unauthorized` to a request that does not come through the proxy of the
sandbox, which adds the credential of the gateway.

## Static and dynamic gateways

Besides the tools of its servers, a gateway offers tools of its own. By
default it is **dynamic**: `mcp-find` searches the servers registered on the
host and `mcp-add` loads one, so the agent in the sandbox can load any of them
by itself; a server added this way stays loaded, in later sessions too, until
the program unloads it.

A sandbox created with a **static** set of servers, as `sbx create
--static-mcp` does, offers neither `mcp-find` nor `mcp-add`: only its servers,
and `mcp-exec` and `code-mode`. The program keeps the power to load and unload
servers through the socket.

```python
package = await client.package("shell")
request = package.request("my-sandbox").with_static_mcp_servers("docs-tools")
sandbox = await client.create(kit=package, request=request)
```

Tool names are not prefixed by server: `mcp-add` refuses a server whose tool
names are already taken. These behaviors were measured on `sbx` v0.54.0 by the
MCP examples (see [Examples](../guides/examples.md)).

## Credentials of remote servers

A remote server that needs a header, a bearer token for instance, is
registered with a placeholder in that header, and the value is stored as the
`sbx` secret `mcp:<server>:<placeholder>`. The gateway fills the header when it
connects to the server: the server sees the token, the sandbox never holds
it. A gateway keeps its connection: after the secret changes, unload the
server and load it again for the gateway to use the new value.
