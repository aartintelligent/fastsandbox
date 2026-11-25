from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from fastsandbox import Context, FastSandbox, Network, WorkspaceDir

app = FastSandbox("upgrades")

# What the agent needs besides its own service: the package index, and the
# GitHub API for reading only.
NEEDS = Network.allow("pypi.org", "files.pythonhosted.org") | Network.allow_http(
    "api.github.com", methods=["GET"]
)


class Outcome(BaseModel):
    ok: bool
    reached: list[str]
    refused: list[str]


@app.agent("claude", network=NEEDS | Network.deny("example.org"), timeout="20m")
async def upgrade(
    ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)], package: str
) -> Outcome:
    """Has Claude Code upgrade a dependency, then reports what the sandbox reached."""
    run = await ctx.agent.prompt(
        f"Upgrade {package} to its latest version and fix what breaks.",
        working_dir=str(repo.resolve()),
    )
    # The activity log of the policy, narrowed to the sandbox of this run.
    log = (await ctx.client.policy.log()).for_sandbox(ctx.sandbox.name)
    return Outcome(
        ok=run.ok,
        reached=[host.host for host in log.allowed_hosts],
        refused=[host.host for host in log.blocked_hosts],
    )
