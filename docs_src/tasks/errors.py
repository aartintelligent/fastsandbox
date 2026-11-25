from pydantic import ValidationError

import fastsandbox
from fastsandbox import CommandFailedError, Context, FastSandbox, SandboxTimeoutError

app = FastSandbox("scripts")


@app.task(kit="shell", timeout="30s")
async def run_script(ctx: Context, script: str) -> str:
    """Runs a shell script and returns what it printed."""
    output = await ctx.sandbox.exec(script, check=True)
    return output.stdout


async def main() -> None:
    try:
        await app.run("run_script")
    except ValidationError as error:
        print(f"invalid inputs: {error.error_count()} error")

    try:
        print(await app.run("run_script", script="exit 3"))
    except CommandFailedError as error:
        print(f"the script exited with code {error.exit_code}")
    except SandboxTimeoutError as error:
        print(f"the script ran over {error.after}s")


if __name__ == "__main__":
    fastsandbox.run(main())
