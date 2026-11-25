import asyncio
import sys
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

import fastsandbox
from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("contest", max_concurrency=2)

Clone = Annotated[Path, WorkspaceDir(clone=True)]


class Attempt(BaseModel):
    agent: str
    passed: bool
    patch: str


async def attempt(ctx: Context, workdir: str, issue: str, command: str) -> Attempt:
    """Has the agent of the task fix the issue on its clone, then runs the tests."""
    head = await ctx.sandbox.exec(["git", "rev-parse", "HEAD"], working_dir=workdir, check=True)
    await ctx.agent.prompt(f"{issue}\n\nFix it and commit the fix.", working_dir=workdir)
    tests = await ctx.sandbox.exec(command, working_dir=workdir)
    patch = await ctx.sandbox.exec(
        ["git", "format-patch", "--stdout", f"{head.stdout.strip()}..HEAD"],
        working_dir=workdir,
        check=True,
    )
    return Attempt(agent=ctx.agent.name, passed=tests.ok, patch=patch.stdout)


@app.agent("claude", timeout="20m")
async def fix_with_claude(
    ctx: Context, repo: Clone, issue: str, command: str = "make test"
) -> Attempt:
    """Has Claude Code fix an issue."""
    return await attempt(ctx, str(repo.resolve()), issue, command)


@app.agent("codex", timeout="20m")
async def fix_with_codex(
    ctx: Context, repo: Clone, issue: str, command: str = "make test"
) -> Attempt:
    """Has Codex fix the same issue."""
    return await attempt(ctx, str(repo.resolve()), issue, command)


async def main(repo: str, issue: str) -> None:
    async with app:  # One client for every run.
        attempts = await asyncio.gather(
            fix_with_claude(repo=repo, issue=issue),
            fix_with_codex(repo=repo, issue=issue),
        )
    for result in attempts:
        print(f"{result.agent}: {'passed' if result.passed else 'failed'}")


if __name__ == "__main__":
    fastsandbox.run(main(sys.argv[1], sys.argv[2]))
