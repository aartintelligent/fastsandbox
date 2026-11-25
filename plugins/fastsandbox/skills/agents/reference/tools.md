# MCP tools for an agent

Full page: https://aartintelligent.github.io/fastsandbox/agents/tools/

The agent in a sandbox reaches MCP servers through the sandbox's MCP gateway,
at `http://mcp-gateway.docker.internal/mcp`. Servers are registered on the host
once, with the `sbx` CLI (`sbx mcp add`); a task loads into its sandbox's
gateway the ones its agent needs.

## API

- `await ctx.sandbox.load_mcp_server(server)`: loads a registered server into
  the gateway of the run's sandbox; raises `NotFoundError` when the server is
  not registered. Returns the loaded server.
- `await ctx.sandbox.unload_mcp_server(server)`: unloads it; `NotFoundError`
  when it is not loaded.
- `await ctx.sandbox.mcp_gateway()`: the gateway (`url`, `servers`, whether
  they are static, ...).
- `await client.mcp.check_registration(McpServerCheck.local(name, command))` or
  `McpServerCheck.remote(name, url)`: whether the MCP policy lets `sbx mcp add`
  register a server; nothing is registered.

## Example

```python
from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("docs-checks")


@app.agent("claude", timeout="20m")
async def check_docs(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Has Claude Code check a README against the docs, with the tools of an MCP server."""
    # Registered on the host beforehand, with `sbx mcp add docs-tools ...`.
    await ctx.sandbox.load_mcp_server("docs-tools")
    workdir = str(repo.resolve())
    await ctx.agent.prompt(
        "With the tools of the docs-tools MCP server, check that README.md matches "
        "the documentation, and write what differs to DIFFERENCES.md.",
        working_dir=workdir,
    )
    return await ctx.sandbox.read_text(f"{workdir}/DIFFERENCES.md")
```

## Gotchas

- Load the server before prompting, and name it in the prompt so the agent
  reaches for its tools; a missing registration fails before the agent costs
  anything.
- The gateway is dynamic by default: besides the loaded servers it offers
  `mcp-find` and `mcp-add`, so the agent can load any server registered on the
  host by itself. Loading from the task guarantees a server, it does not keep
  the others out. A static set of servers is created through the client
  (`request.with_static_mcp_servers(...)` on a kit package's request).
- Tool names are not prefixed by server: two servers with a tool of the same
  name cannot be loaded together.
- A remote server behind a token is registered with a placeholder in its
  header; the token is stored as the `sbx` secret
  `mcp:<server>:<placeholder>`, filled in by the gateway: the sandbox never
  holds it. Never put the token in the task or the prompt.
- Registering servers is done by the user with `sbx mcp add` (see the Docker
  documentation); a task only loads and unloads.
