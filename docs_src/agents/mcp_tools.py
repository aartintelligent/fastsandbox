from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("docs-checks")


@app.agent("claude", timeout="20m")
async def check_docs(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Has Claude Code check a README against the docs, with the tools of an MCP server."""
    # A server registered on the host beforehand, with `sbx mcp add docs-tools ...`.
    await ctx.sandbox.load_mcp_server("docs-tools")
    workdir = str(repo.resolve())
    await ctx.agent.prompt(
        "With the tools of the docs-tools MCP server, check that README.md matches "
        "the documentation, and write what differs to DIFFERENCES.md.",
        working_dir=workdir,
    )
    return await ctx.sandbox.read_text(f"{workdir}/DIFFERENCES.md")
