from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("reviews")


@app.agent("claude", timeout="30m")
async def review(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Has Claude Code review a project, reporting each step it takes."""
    prompt = "Review this project and list its three main risks."
    steps = 0
    answer = ""
    async for event in ctx.agent.stream(prompt, working_dir=str(repo.resolve())):
        if not isinstance(event, dict):
            continue
        if event.get("type") == "assistant":
            steps += 1
            await ctx.report_progress(steps, message="the agent took a step")
        elif event.get("type") == "result":
            answer = str(event.get("result", ""))
    return answer


def show(progress: float, total: float | None, message: str | None) -> None:
    print(f"step {progress:g}: {message}")


if __name__ == "__main__":
    print(app.run_sync("review", repo=".", on_progress=show))
