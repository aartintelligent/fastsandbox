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
