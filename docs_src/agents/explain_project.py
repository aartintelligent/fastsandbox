from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("quickstart")


@app.agent("claude", timeout="15m")
async def explain(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Has Claude Code explain a project, working on a private clone of it."""
    workdir = str(repo.resolve())
    await ctx.agent.prompt(
        "Explain what this project does and how its code is laid out, "
        "in twenty lines at most, and write the explanation to EXPLAINED.md.",
        working_dir=workdir,
    )
    # The file is in the clone, inside the sandbox: the host is untouched.
    return await ctx.sandbox.read_text(f"{workdir}/EXPLAINED.md")
