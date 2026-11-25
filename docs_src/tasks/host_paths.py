from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, Mounted, Uploaded, WorkspaceDir

app = FastSandbox("paths")


@app.task(kit="shell")
async def inventory(
    ctx: Context,
    repo: Annotated[Path, WorkspaceDir()],
    data: Annotated[Path, Mounted("/data", read_only=True)],
    fixtures: Annotated[Path, Uploaded("/work/fixtures")],
) -> list[str]:
    """Lists what the sandbox sees of three host directories."""
    listings = []
    for path in (str(repo.resolve()), "/data", "/work/fixtures"):
        output = await ctx.sandbox.exec(["ls", "-A", path], check=True)
        listings.append(output.stdout.strip())
    return listings
