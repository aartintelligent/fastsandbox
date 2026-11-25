import fastsandbox
from fastsandbox import Context, FastSandbox

app = FastSandbox("hello")


@app.task
async def uname(ctx: Context) -> str:
    """Says which system the sandbox runs."""
    output = await ctx.sandbox.exec("uname -sm", check=True)
    return output.stdout.strip()


if __name__ == "__main__":
    print(fastsandbox.run(uname))
