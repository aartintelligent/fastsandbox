# Following the work of an agent

Full page: https://aartintelligent.github.io/fastsandbox/agents/follow/

An unattended agent can run for many minutes. Four ways to see what it does:
its events as they come, progress for the caller, the task's logs, and the
sandbox kept after the run.

## API

- `async for item in ctx.agent.stream(prompt, *, working_dir=None)`: runs the
  same command as `prompt` and yields each line of standard output, parsed as
  JSON for `claude`, `codex`, `cursor` and `droid`, a text line for the others
  (a JSON-lines agent's line that is not JSON stays a string). Claude Code
  reports an `assistant` event for each step and ends with a `result` event
  whose `result` field holds its final answer. Other agents' event shapes are
  their own.
- `await ctx.report_progress(progress, total=None, message=None)`: sends
  progress to the caller, which receives it through
  `app.run(..., on_progress=handler)` or `app.run_sync(..., on_progress=handler)`;
  the handler, plain or async, gets `(progress, total, message)`. Also logged
  at debug level.
- `ctx.log(message, level=logging.INFO)`: logs through the task's own logger,
  `ctx.logger`, with the task and sandbox names;
  `logging.basicConfig(level=logging.INFO)` shows it.
- `keep=True` on the decorator: the sandbox is not deleted after the run.
  `sbx ls` lists it, `client.sandbox(name)` reaches it, and
  `ssh -o ProxyCommand="fastsandbox ssh-proxy NAME" agent@NAME` opens a shell
  in it. It stops once no session holds it and is then the user's to delete
  (`sbx` or `await client.sandbox(name).delete()`).
- `await ctx.agent.session(*args, tty=True, size=None)`: an interactive
  `Interactive` session with the agent, for a program that relays a terminal.

## Example

```python
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
```

## Gotchas

- `stream` has no `timeout`: bound the run with the task's `timeout=`, which
  raises `SandboxTimeoutError` and deletes the sandbox.
- Always guard with `isinstance(event, dict)`: text lines and non-JSON lines
  arrive as strings.
- Log the agent's events, never the environment or the keys.
- A kept sandbox holds the clone and the work of the agent: keep for debugging
  only, and delete it afterwards.
- The `agent-claude` example of the repository relays an interactive session to
  the terminal: `just example agent-claude ~/my-project -- "explain this project"`.
