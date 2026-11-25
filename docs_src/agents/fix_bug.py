from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from fastsandbox import Context, FastSandbox, Network, WorkspaceDir

app = FastSandbox("agents")


class Report(BaseModel):
    passed: bool
    summary: str


@app.agent("claude", network=Network.deny("example.org"), timeout="20m")
async def fix_bug(
    ctx: Context,
    repo: Annotated[Path, WorkspaceDir()],
    issue: str,
    command: str = "make test",
) -> Report:
    """Has Claude Code fix an issue, then checks the fix with the tests."""
    await ctx.agent.prompt(f"{issue}\n\nFix it, then run `{command}` to confirm.")
    # The agent says the tests pass; the tests decide.
    check = await ctx.sandbox.exec(command, working_dir=str(repo.resolve()))
    return Report(passed=check.ok, summary=(check.stdout + check.stderr)[-500:])
