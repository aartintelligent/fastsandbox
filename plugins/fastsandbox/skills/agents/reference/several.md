# Several agents, or many runs at once

Full page: https://aartintelligent.github.io/fastsandbox/agents/several/

Each run of a task has its own sandbox: agents run side by side without seeing
each other's files, network rules or credentials.

## API

- `FastSandbox(name, max_concurrency=N)`: at most `N` runs of the application
  hold a sandbox at once; the others wait for a free slot before creating
  theirs. `@app.agent(..., max_concurrency=M)` bounds the runs of one task.
- `async with app:` starts the application once (one client, one lifespan)
  for every run inside the block.
- Calling a task (`await fix_with_claude(repo=..., issue=...)`) runs it through
  its application, as `await app.run("fix_with_claude", ...)` does.
- `asyncio.gather(...)` runs them at once and returns the results in order; by
  default it raises the first error while the other runs go on until they
  end; `return_exceptions=True` returns the errors in place of the results.

## Example

```python
import asyncio
import sys
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

import fastsandbox
from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("contest", max_concurrency=2)

Clone = Annotated[Path, WorkspaceDir(clone=True)]


class Attempt(BaseModel):
    agent: str
    passed: bool
    patch: str


async def attempt(ctx: Context, workdir: str, issue: str, command: str) -> Attempt:
    """Has the agent of the task fix the issue on its clone, then runs the tests."""
    head = await ctx.sandbox.exec(["git", "rev-parse", "HEAD"], working_dir=workdir, check=True)
    await ctx.agent.prompt(f"{issue}\n\nFix it and commit the fix.", working_dir=workdir)
    tests = await ctx.sandbox.exec(command, working_dir=workdir)
    patch = await ctx.sandbox.exec(
        ["git", "format-patch", "--stdout", f"{head.stdout.strip()}..HEAD"],
        working_dir=workdir,
        check=True,
    )
    return Attempt(agent=ctx.agent.name, passed=tests.ok, patch=patch.stdout)


@app.agent("claude", timeout="20m")
async def fix_with_claude(
    ctx: Context, repo: Clone, issue: str, command: str = "make test"
) -> Attempt:
    """Has Claude Code fix an issue."""
    return await attempt(ctx, str(repo.resolve()), issue, command)


@app.agent("codex", timeout="20m")
async def fix_with_codex(
    ctx: Context, repo: Clone, issue: str, command: str = "make test"
) -> Attempt:
    """Has Codex fix the same issue."""
    return await attempt(ctx, str(repo.resolve()), issue, command)


async def main(repo: str, issue: str) -> None:
    async with app:
        attempts = await asyncio.gather(
            fix_with_claude(repo=repo, issue=issue),
            fix_with_codex(repo=repo, issue=issue),
            return_exceptions=True,
        )
    for result in attempts:
        if isinstance(result, BaseException):
            print(f"failed: {result}")
        else:
            print(f"{result.agent}: {'passed' if result.passed else 'failed'}")


if __name__ == "__main__":
    fastsandbox.run(main(sys.argv[1], sys.argv[2]))
```

```sh
export ANTHROPIC_API_KEY=sk-ant-... OPENAI_API_KEY=sk-...
python app.py . "the parser drops the last line"
```

## Gotchas

- Each agent needs its own key in the caller's environment; its kit is forged
  on its first run, once per process.
- Many runs of one agent follow the same pattern:
  `await asyncio.gather(*(review(repo=r) for r in repos))`, bounded by
  `max_concurrency` so the machine does not run them all at once.
- Every sandbox is deleted at the end of its run, an error or a timeout
  included.
- Write the shared body once (a plain `async def` taking `ctx`), and keep the
  `Path` resolution in the task functions.
