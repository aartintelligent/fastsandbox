from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("patches")


@app.agent("claude", timeout="20m")
async def propose_patch(
    ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)], issue: str
) -> str:
    """Has Claude Code fix an issue in a private clone, and returns its commits as a patch."""
    workdir = str(repo.resolve())
    head = await ctx.sandbox.exec(["git", "rev-parse", "HEAD"], working_dir=workdir, check=True)
    await ctx.agent.prompt(f"{issue}\n\nFix it and commit the fix.", working_dir=workdir)
    # The clone goes with the sandbox: its new commits leave as a patch.
    patch = await ctx.sandbox.exec(
        ["git", "format-patch", "--stdout", f"{head.stdout.strip()}..HEAD"],
        working_dir=workdir,
        check=True,
    )
    return patch.stdout
