# Give it tools

An agent in a sandbox reaches MCP servers through the MCP gateway of its
sandbox, at one URL. The servers are registered on your machine once, with the
`sbx` CLI; a task then loads, into the gateway of its sandbox, the ones its
agent needs.

## 1. Register the server on the host

`sbx mcp add` registers a server: a local one, started from a command, or a
remote one, reached at a URL. The
[Docker documentation](https://docs.docker.com/ai/sandboxes/) gives its
options. Before registering, a program can ask whether the MCP policy allows
it, with [`client.mcp.check_registration(...)`][fastsandbox.Mcp.check_registration]
(see [MCP gateway](../client/mcp.md#the-settings-of-the-daemon)).

A remote server behind a token is registered with a placeholder in its header,
and the token is stored as the `sbx` secret `mcp:<server>:<placeholder>`: the
gateway fills the header when it connects, and the sandbox never holds the
token (see [MCP gateway](../client/mcp.md#credentials-of-remote-servers)).

## 2. Load it for the agent

```python title="docs_src/agents/mcp_tools.py" hl_lines="13 16 17"
--8<-- "docs_src/agents/mcp_tools.py"
```

- **Line 13**: [`load_mcp_server("docs-tools")`][fastsandbox.Sandbox.load_mcp_server]
  loads the server into the gateway of the sandbox of the run, before the agent
  starts. A server that is not registered raises
  [`NotFoundError`][fastsandbox.exceptions.NotFoundError], before the agent
  costs anything.
- **Lines 16 and 17**: the prompt names the server, so that the agent reaches
  for its tools.

## What the agent sees

By default the gateway is **dynamic**: besides the tools of the servers loaded
into it, it offers `mcp-find`, which searches the servers registered on the
host, and `mcp-add`, which loads one, so the agent can load any of them by
itself. Loading the server from the task makes sure it is there; it does not
keep the others out.

A sandbox created with a **static** set of servers offers only those: the
client creates one with `with_static_mcp_servers(...)` (see
[Static and dynamic gateways](../client/mcp.md#static-and-dynamic-gateways)).
Tool names are not prefixed by server, so two servers with a tool of the same
name cannot be loaded together.

## Examples

Each agent has an `-mcp` example in the repository, which serves an MCP server
from the host and has the agent call it:

```sh
just example agent-claude-mcp
```

See [Examples](../guides/examples.md#coding-agents).
