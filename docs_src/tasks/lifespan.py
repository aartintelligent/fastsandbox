import contextlib
from collections.abc import AsyncIterator
from typing import Any

import fastsandbox
from fastsandbox import Context, FastSandbox


@contextlib.asynccontextmanager
async def lifespan(app: FastSandbox) -> AsyncIterator[dict[str, Any]]:
    runs: list[str] = []
    yield {"runs": runs}
    print(f"{app.name}: {len(runs)} runs")


app = FastSandbox("digests", lifespan=lifespan)


@app.task(kit="shell")
async def sha256(ctx: Context, text: str) -> str:
    """The SHA-256 digest of a text, computed in a sandbox."""
    output = await ctx.sandbox.exec(
        ["sh", "-c", 'printf %s "$1" | sha256sum', "sh", text], check=True
    )
    ctx.state["runs"].append(ctx.run_id)
    return output.stdout.split()[0]


async def main() -> None:
    async with app:
        for text in ("one", "two", "three"):
            print(await app.run("sha256", text=text))


if __name__ == "__main__":
    fastsandbox.run(main())
