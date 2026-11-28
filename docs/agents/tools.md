# Give it tools

An agent in a sandbox reaches MCP servers in one of two ways:

- **Given by a mixin**: a mixin of its kit registers the servers in the
  configuration of the agent, inside the sandbox, when the sandbox is created.
  Nothing is registered with the daemon or written on the host, and the `sbx`
  CLI is not needed. Claude Code only, for now.
- **Through the MCP gateway** of its sandbox: servers registered on the host
  with the `sbx` CLI, which a task loads into the gateway of its sandbox.

## A server given by a mixin

[`Mixin.mcp(agent, *servers)`][fastsandbox.Mixin.mcp] makes the mixin that
registers [`McpServer`][fastsandbox.McpServer]s in the agent, and a task
composes it with the kit of its agent:

```python title="docs_src/agents/mcp_mixin.py" hl_lines="8 9 16 17"
--8<-- "docs_src/agents/mcp_mixin.py"
```

- **Line 9**: [`McpServer.host(name, port)`][fastsandbox.McpServer.host] is a
  server that a program of the host serves on a port of its loopback, in any
  language. The sandbox reaches it at `http://host.docker.internal:<port>/mcp`,
  over streamable HTTP.
- **Line 16**: the mixin registers the server in Claude Code when the sandbox
  is created (`claude mcp add`, as the user `agent`), and allows its host.
  [`Mixin.mcp`][fastsandbox.Mixin.mcp] raises
  [`InvalidKitError`][fastsandbox.exceptions.InvalidKitError] for an agent
  other than `claude`, a name or a URL it cannot register, or two servers of
  the same name.
- **Lines 8 and 17**: the server takes a bearer token, which the creation
  request gives in the variable the server names,
  `DOCKER_SANDBOX_MCP_<NAME>_TOKEN`:
  [`tools.env(TOKEN)`][fastsandbox.McpServer.env] is that variable. The proxy
  rewrites no request to the host, so the sandbox holds the token: make it
  random, as here, and have the server refuse any other. The token is not part
  of the mixin, so one kit serves sandboxes with tokens of their own. The port
  is: a server on a free port, another at every run, makes each run forge a
  new mixin, whose images the daemon keeps beside those of the last; serve on
  the same port from one run to the next.

The proxy of the sandbox forwards the requests to the loopback of the host,
which names `localhost:<port>` in their `Host` header: a server bound to
`127.0.0.1` takes them as it takes those of the host, the protection of the
official MCP Python SDK against DNS rebinding included. Nothing in a request
tells the sandbox apart from another process of the host but its token, which
the server is therefore to check.

A remote server, which the agent calls itself, is
[`McpServer.remote(name, url)`][fastsandbox.McpServer.remote]; behind a token,
[`with_bearer_env(env)`][fastsandbox.McpServer.with_bearer_env] sends the
content of the variable `env` of the sandbox as its bearer. For a key the
sandbox must not hold, give the sandbox a
[`CustomSecret`][fastsandbox.models.CustomSecret] for the host of the server whose
`env_name` is that variable: the variable holds its placeholder, which the
proxy replaces with the key.

The client creates such a sandbox the same way:
`client.create(kit=Kit(base="claude", mixins=(Mixin.mcp("claude", tools),)), env=tools.env(token))`.
The mixin is one of the [mixins written in Python](../client/kits.md#mixins-written-in-python).

## A server of the MCP gateway

### 1. Register the server on the host

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

### 2. Load it for the agent

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

### What the agent sees

By default the gateway is **dynamic**: besides the tools of the servers loaded
into it, it offers `mcp-find`, which searches the servers registered on the
host, and `mcp-add`, which loads one, so the agent can load any of them by
itself. Loading the server from the task makes sure it is there; it does not
keep the others out. A server given by a mixin is registered beside the
gateway, which the kit of the agent registers too.

A sandbox created with a **static** set of servers offers only those: the
client creates one with `with_static_mcp_servers(...)` (see
[Static and dynamic gateways](../client/mcp.md#static-and-dynamic-gateways)).
Tool names are not prefixed by server, so two servers with a tool of the same
name cannot be loaded together.

## Examples

`agent-kit-forge` gives Claude Code, by a mixin, an MCP server it serves on
the host, and uses it from inside the sandbox as Claude Code would, at the URL
and with the token Claude Code registered: it lists the tools and calls one,
without starting the agent. Each agent has an `-mcp`
example, which serves an MCP server from the host through the gateway and has
the agent call it:

```sh
just example agent-kit-forge
just example agent-claude-mcp
```

See [Examples](../guides/examples.md#coding-agents).
