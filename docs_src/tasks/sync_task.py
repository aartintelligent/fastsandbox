from fastsandbox import Context, FastSandbox

app = FastSandbox("sync")


@app.task
def disk_usage(ctx: Context, path: str = "/") -> str:
    """Reports the disk usage of a directory of the sandbox, from synchronous code."""
    output = ctx.wait(ctx.sandbox.exec(["du", "-sh", path], check=True))
    return output.stdout.strip()
