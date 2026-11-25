from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, Network, WorkspaceDir

app = FastSandbox("reviews")


@app.agent("claude", network=Network.deny("example.org"), timeout="30m")
async def review(ctx: Context, repo: Annotated[Path, WorkspaceDir()]) -> str:
    """Has Claude Code review a project, logging each step it reports."""
    prompt = "Review this project and list its three main risks."
    summary = ""
    async for event in ctx.agent.stream(prompt, working_dir=str(repo.resolve())):
        if not isinstance(event, dict):
            continue
        ctx.log(f"agent event: {event.get('type')}")
        if event.get("type") == "result" and isinstance(event.get("result"), str):
            summary = event["result"]
    return summary
