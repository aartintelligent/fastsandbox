# MCP tools for an agent

Full page: https://aartintelligent.github.io/fastsandbox/agents/tools/

An agent reaches MCP servers in one of two ways:

- **Given by a mixin** (Claude Code only, for now): `Mixin.mcp("claude", *servers)`
  registers the servers in the configuration of the agent when the sandbox is
  created (`claude mcp add`, inside the sandbox) and allows their hosts.
  Nothing is registered with the daemon or written on the host; the `sbx` CLI
  is not needed. Prefer it.
- **Through the MCP gateway** of the sandbox, at
  `http://mcp-gateway.docker.internal/mcp`: servers registered on the host with
  `sbx mcp add`, which a task loads into the gateway of its sandbox.

## API

- `McpServer.host(name, port)`: a server a program of the host serves on
  `127.0.0.1:<port>`, in any language, over streamable HTTP; the sandbox
  reaches it at `http://host.docker.internal:<port>/mcp`. Its bearer token is
  read from the variable `token_env`, `DOCKER_SANDBOX_MCP_<NAME>_TOKEN`.
- `McpServer.remote(name, url)`: a remote server the agent calls itself;
  `.with_bearer_env(env)` sends the content of the variable `env` of the
  sandbox as its bearer.
- `server.env(token) -> dict[str, str]`: the variable of the creation request
  that gives the server its token; `ValueError` for a server without one.
- `Mixin.mcp(agent, *servers) -> Mixin`: the mixin, built by the crate;
  `InvalidKitError` for an agent other than `claude`, no server, two of the
  same name, a name, URL or variable it cannot register. Compose it with the
  kit of the agent: `kit=Kit(base="claude", mixins=(Mixin.mcp("claude", tools),))`.
- `await ctx.sandbox.load_mcp_server(server)`: loads a server registered with
  `sbx mcp add` into the gateway of the run's sandbox; raises `NotFoundError`
  when the server is not registered. Returns the loaded server.
- `await ctx.sandbox.unload_mcp_server(server)`: unloads it; `NotFoundError`
  when it is not loaded.
- `await ctx.sandbox.mcp_gateway()`: the gateway (`url`, `servers`, whether
  they are static, ...).
- `await client.mcp.check_registration(McpServerCheck.local(name, command))` or
  `McpServerCheck.remote(name, url)`: whether the MCP policy lets `sbx mcp add`
  register a server; nothing is registered.

## Example

```python
import secrets
from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, Kit, McpServer, Mixin, WorkspaceDir

# Served by a program of the host on 127.0.0.1:47813, which checks this token.
TOKEN = secrets.token_urlsafe(32)
tools = McpServer.host("docs-tools", 47813)

app = FastSandbox("docs-checks")


@app.agent(
    "claude",
    kit=Kit(base="claude", mixins=(Mixin.mcp("claude", tools),)),
    env=tools.env(TOKEN),
    timeout="20m",
)
async def check_docs(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Has Claude Code check a README against the docs, with the tools of an MCP server."""
    workdir = str(repo.resolve())
    await ctx.agent.prompt(
        "With the tools of the docs-tools MCP server, check that README.md matches "
        "the documentation, and write what differs to DIFFERENCES.md.",
        working_dir=workdir,
    )
    return await ctx.sandbox.read_text(f"{workdir}/DIFFERENCES.md")
```

Through the gateway instead, for a server registered with
`sbx mcp add docs-tools ...`: keep the agent's own kit and call
`await ctx.sandbox.load_mcp_server("docs-tools")` before prompting.

## Gotchas

- A server of the host listens on `127.0.0.1:<port>`: the proxy forwards the
  requests of the sandbox there as `localhost:<port>`, which the MCP Python
  SDK, guarded against DNS rebinding, accepts as it is.
- The proxy writes no secret into requests to the host: the sandbox holds the
  token of a server of the host, and only that token tells it apart from the
  other processes of the host. Make it random (`secrets.token_urlsafe(32)`)
  and have the server refuse any other. Never put a real key in `env`: for a remote server
  behind a key, give the sandbox a `CustomSecret` for its host whose `env_name`
  is the variable of `with_bearer_env`, so that the sandbox sees a placeholder.
- The token is not part of the mixin: one forged package serves sandboxes with
  tokens of their own. A new port is a new mixin, and a new composition.
- Name the server in the prompt so the agent reaches for its tools.
- The gateway is dynamic by default: besides the loaded servers it offers
  `mcp-find` and `mcp-add`, so the agent can load any server registered on the
  host by itself. Loading from the task guarantees a server, it does not keep
  the others out. A static set of servers is created through the client
  (`request.with_static_mcp_servers(...)` on a kit package's request).
- Tool names are not prefixed by server: two servers with a tool of the same
  name cannot be loaded together.
- A remote server of the gateway behind a token is registered with a
  placeholder in its header; the token is stored as the `sbx` secret
  `mcp:<server>:<placeholder>`, filled in by the gateway: the sandbox never
  holds it. Never put the token in the task or the prompt.
