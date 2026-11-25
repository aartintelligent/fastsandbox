"""The tasks of my-checks: the checks of a project, run on a copy of it.

Each run creates a sandbox of Docker Sandboxes (installed and running, with
`sbx version` answering), copies the project into it, runs the command, and
deletes the sandbox; the project on the host is never touched:

    fastsandbox run check --repo . --command "make test"
"""

from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from fastsandbox import Context, FastSandbox, Network, Uploaded

app = FastSandbox("my-checks")

# What the sandbox may reach: the package index, for the dependencies.
PYPI = Network.allow("pypi.org", "files.pythonhosted.org")


class Report(BaseModel):
    """The outcome of the checks: whether they pass, and the end of their output."""

    passed: bool
    exit_code: int
    output: str


@app.task(kit="shell", network=PYPI, timeout="15m")
async def check(
    ctx: Context, repo: Annotated[Path, Uploaded("/work")], command: str = "make test"
) -> Report:
    """Runs the checks of a project on a copy of it."""
    await ctx.report_progress(1, 2, "project copied")
    output = await ctx.sandbox.exec(command, working_dir="/work")
    await ctx.report_progress(2, 2, "checks done")
    return Report(
        passed=output.ok,
        exit_code=output.exit_code,
        output=(output.stdout + output.stderr)[-2000:],
    )
