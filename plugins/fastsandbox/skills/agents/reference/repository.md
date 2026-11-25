# Giving an agent a repository, and getting its work back

Full page: https://aartintelligent.github.io/fastsandbox/agents/repository/

How the files reach the sandbox decides what the agent can break; how the work
comes back is the result of the task.

## API

Markers on a `Path` input, in `Annotated[Path, marker]`:

| Marker | The agent works on | Inside the sandbox | Its changes |
|---|---|---|---|
| `WorkspaceDir(clone=True)` | A private Git clone, with history | At the same absolute path; the host repository is mounted read-only at `/run/sandbox/source` | Stay in the sandbox |
| `WorkspaceDir()` | The directory itself, read-write, as the sandbox's workspace | At its own absolute path | Reach the host during the run |
| `Uploaded(target)` | A copy of the contents, made before the task runs | Under `target` (created as root, owned by the kit's default user) | Stay in the sandbox |
| `Mounted(target=None, read_only=False)` | A further mounted directory or file | At `target`, else its own absolute path | Reach the host unless `read_only=True` |

- At most one `WorkspaceDir` per task, or the run raises `TaskError`.
- Paths are expanded (`~`) and resolved on the host; the parameter keeps the
  caller's value (`.`), so use `str(repo.resolve())` as the working directory.
- An optional input (`Path | None = None`) left at `None` is neither mounted
  nor copied.
- Clone mode needs the directory to be a Git repository.

Getting the work back:

| Result | Code |
|---|---|
| Tests decide | `check = await ctx.sandbox.exec(command, working_dir=workdir)`; return `check.ok` and the end of the output |
| A patch | Record `git rev-parse HEAD` before the agent, ask it to commit, return `git format-patch --stdout <head>..HEAD` |
| A file | `await ctx.sandbox.read_text(f"{workdir}/NAME.md")` |
| A directory | `await ctx.sandbox.download_dir(path, host_dir)` |

## Example

```python
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("patches")


class Proposal(BaseModel):
    passed: bool
    patch: str


@app.agent("claude", timeout="20m")
async def propose_fix(
    ctx: Context,
    repo: Annotated[Path, WorkspaceDir(clone=True)],
    issue: str,
    command: str = "make test",
) -> Proposal:
    """Has Claude Code fix an issue on a private clone; the tests decide."""
    workdir = str(repo.resolve())
    head = await ctx.sandbox.exec(["git", "rev-parse", "HEAD"], working_dir=workdir, check=True)
    await ctx.agent.prompt(
        f"{issue}\n\nFix it, run `{command}` to confirm, and commit the fix.",
        working_dir=workdir,
    )
    # The agent says the tests pass; the tests decide.
    tests = await ctx.sandbox.exec(command, working_dir=workdir)
    patch = await ctx.sandbox.exec(
        ["git", "format-patch", "--stdout", f"{head.stdout.strip()}..HEAD"],
        working_dir=workdir,
        check=True,
    )
    return Proposal(passed=tests.ok, patch=patch.stdout)
```

The command line prints a model result as indented JSON and a string result as
it is: a variant that returns `patch.stdout` alone (`-> str`) goes straight to
a file, to review and apply with
`fastsandbox run app.py propose_fix --repo . --issue "..." > fix.patch && git am fix.patch`.

## Gotchas

- `WorkspaceDir()` changes the host while the agent runs, and an interrupted run
  leaves its edits half done: commit or stash first, or use the clone.
- Everything on a clone or an upload is deleted with the sandbox: return what
  you keep, or set `keep=True` to look at it afterwards.
- `check=True` on `exec` raises `CommandFailedError` on a non-zero exit; for the
  tests, leave it off and return `ok`.
- A prompt the run can be checked against names what to do, the command that
  checks it, and what to leave behind (commits, a file at a given path).
