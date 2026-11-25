from typing import Annotated

from pydantic import BaseModel, Field

from fastsandbox import Context, FastSandbox

app = FastSandbox("text")


class Count(BaseModel):
    lines: int
    words: int
    tags: list[str] = []


@app.task(kit="shell")
async def count(
    ctx: Context,
    text: str,
    repeat: Annotated[int, Field(ge=1, le=10)] = 1,
    tags: list[str] | None = None,
) -> Count:
    """Counts the lines and the words of a text, repeated."""
    await ctx.sandbox.write_file("/tmp/input.txt", text * repeat)
    output = await ctx.sandbox.exec(["wc", "-l", "-w", "/tmp/input.txt"], check=True)
    lines, words, _ = output.stdout.split()
    return Count(lines=int(lines), words=int(words), tags=tags or [])
