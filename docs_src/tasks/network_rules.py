from fastsandbox import Context, FastSandbox, Network

PYPI = Network.allow("pypi.org", "files.pythonhosted.org")
GITHUB_READ_ONLY = Network.allow_http("api.github.com", methods=["GET"])

app = FastSandbox("network")


@app.task(kit="shell", network=PYPI | GITHUB_READ_ONLY | Network.deny("example.org"))
async def probe(ctx: Context, url: str) -> str:
    """The HTTP status a URL answers from inside the sandbox."""
    output = await ctx.sandbox.exec(
        ["curl", "-sS", "-m", "10", "-o", "/dev/null", "-w", "%{http_code}", url]
    )
    return output.stdout
