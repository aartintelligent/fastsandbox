"""The agent tasks of my-agents: a coding agent at work in a throw-away sandbox.

Each run creates a sandbox of Docker Sandboxes (installed and running, with
`sbx version` answering), gives the agent a private clone of the repository,
pushes its API key to that sandbox only, and deletes it all at the end:

    export ANTHROPIC_API_KEY=...
    fastsandbox run fix --repo . --issue "the parser drops the last line" > fix.patch
"""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from fastsandbox import Context, FastSandbox, Network, WorkspaceDir

app = FastSandbox("my-agents")

# What the agent may reach besides its own service, which is always allowed:
# the package index, for the dependencies of the tests.
NEEDS = Network.allow("pypi.org", "files.pythonhosted.org")


class Fix(BaseModel):
    """The outcome of a fix: whether the tests pass, and the commits as a patch."""

    passed: bool
    patch: str


@app.agent("claude", network=NEEDS, timeout="30m")
async def fix(
    ctx: Context,
    repo: Annotated[Path, WorkspaceDir(clone=True)],
    issue: str,
    command: str = "make test",
) -> Fix:
    """Has Claude Code fix an issue on a private clone, then runs the tests."""
    workdir = str(repo.resolve())
    head = await ctx.sandbox.exec(["git", "rev-parse", "HEAD"], working_dir=workdir, check=True)
    await ctx.agent.prompt(
        f"{issue}\n\nFix it, check the fix with `{command}`, and commit it.",
        working_dir=workdir,
    )
    # What the agent reports is not a result: the tests decide.
    tests = await ctx.sandbox.exec(command, working_dir=workdir)
    # The clone goes with the sandbox: its new commits leave as a patch.
    patch = await ctx.sandbox.exec(
        ["git", "format-patch", "--stdout", f"{head.stdout.strip()}..HEAD"],
        working_dir=workdir,
        check=True,
    )
    return Fix(passed=tests.ok, patch=patch.stdout)
