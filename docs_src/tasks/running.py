import asyncio

import fastsandbox
from fastsandbox import Context, FastSandbox

app = FastSandbox("digests", max_concurrency=2)


@app.task(kit="shell", timeout="2m")
async def sha256(ctx: Context, text: str) -> str:
    """The SHA-256 digest of a text, computed in a sandbox."""
    await ctx.report_progress(1, 2, "sandbox ready")
    output = await ctx.sandbox.exec(
        ["sh", "-c", 'printf %s "$1" | sha256sum', "sh", text], check=True
    )
    await ctx.report_progress(2, 2, "digest computed")
    return output.stdout.split()[0]


def show_progress(progress: float, total: float | None, message: str | None) -> None:
    print(f"{progress:g}/{total}: {message}")


async def main() -> None:
    print(await app.run("sha256", text="hello", on_progress=show_progress))
    digests = await asyncio.gather(*(sha256(text=text) for text in ("a", "b", "c")))
    print(digests)


if __name__ == "__main__":
    fastsandbox.run(main())
