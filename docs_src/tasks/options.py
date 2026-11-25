from fastsandbox import Context, FastSandbox, Network

app = FastSandbox("builds", kit="shell", max_concurrency=4)


@app.task(
    name="describe-sandbox",
    network=Network.allow("pypi.org"),
    timeout="5m",
    env={"STAGE": "ci"},
    cpus=2,
    memory="4g",
    max_concurrency=2,
)
async def describe(ctx: Context) -> dict[str, str]:
    """Reports the processors and the environment the sandbox was given."""
    cpus = await ctx.sandbox.exec("nproc", check=True)
    stage = await ctx.sandbox.exec(["printenv", "STAGE"], check=True)
    return {"cpus": cpus.stdout.strip(), "stage": stage.stdout.strip()}
