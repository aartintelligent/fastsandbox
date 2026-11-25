from collections.abc import AsyncIterator
from typing import Annotated

from fastsandbox import Context, Depends, FastSandbox, Sandbox

app = FastSandbox("deps")


async def scratch_dir(sandbox: Sandbox) -> AsyncIterator[str]:
    output = await sandbox.exec(["mktemp", "-d"], check=True)
    path = output.stdout.strip()
    yield path
    await sandbox.exec(["rm", "-rf", path])


async def input_file(sandbox: Sandbox, scratch: Annotated[str, Depends(scratch_dir)]) -> str:
    path = f"{scratch}/input.txt"
    await sandbox.write_file(path, "one\ntwo\nthree\n")
    return path


@app.task(kit="shell")
async def count_lines(
    ctx: Context,
    path: Annotated[str, Depends(input_file)],
    scratch: Annotated[str, Depends(scratch_dir)],
) -> dict[str, str]:
    """Counts the lines of a file that dependencies prepared."""
    output = await ctx.sandbox.exec(["wc", "-l", path], check=True)
    return {"lines": output.stdout.split()[0], "scratch": scratch}
