import contextlib
from collections.abc import AsyncIterator
from typing import Annotated

from fastsandbox import Context, Depends, FastSandbox, Sandbox


@contextlib.asynccontextmanager
async def lifespan(app: FastSandbox) -> AsyncIterator[dict[str, str]]:
    yield {"registry": "https://pypi.org/simple"}


app = FastSandbox("deps", lifespan=lifespan)


async def python_version(sandbox: Sandbox) -> str:
    output = await sandbox.exec(["python3", "--version"], check=True)
    return output.stdout.strip()


async def scratch_dir(sandbox: Sandbox) -> AsyncIterator[str]:
    await sandbox.exec(["mkdir", "-p", "/tmp/scratch"], check=True)
    yield "/tmp/scratch"
    await sandbox.exec(["rm", "-rf", "/tmp/scratch"])


@app.task(kit="shell")
async def describe(
    ctx: Context,
    version: Annotated[str, Depends(python_version)],
    scratch: Annotated[str, Depends(scratch_dir)],
) -> dict[str, str]:
    """Describes the Python of the sandbox."""
    return {"python": version, "scratch": scratch, "registry": ctx.state["registry"]}
