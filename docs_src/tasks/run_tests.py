from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from fastsandbox import Context, FastSandbox, Network, Uploaded

app = FastSandbox("ci")


class Report(BaseModel):
    passed: bool
    summary: str


@app.task(kit="shell", network=Network.allow("pypi.org"), timeout="10m")
async def run_tests(
    ctx: Context, repo: Annotated[Path, Uploaded("/work")], command: str = "make test"
) -> Report:
    """Runs the tests of a project in a copy of it."""
    output = await ctx.sandbox.exec(f"cd /work && {command}")
    return Report(passed=output.ok, summary=(output.stdout + output.stderr)[-500:])
