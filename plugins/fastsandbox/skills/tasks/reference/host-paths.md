# Host paths

Full page: https://aartintelligent.github.io/fastsandbox/framework/host-paths/

## API

Markers given in `Annotated` on a `Path` input. The caller passes a host
directory; the marker says what happens to it.

| Marker | What happens | Inside the sandbox | Changes made in the sandbox |
|---|---|---|---|
| `WorkspaceDir(clone=False)` | Mounted read-write as the workspace (the working directory of the sandbox) | at its own absolute path | reach the host, live |
| `WorkspaceDir(clone=True)` | A private Git clone of the repository of the directory, with its history | at its own absolute path; the host repository read-only at `/run/sandbox/source` | stay in the clone, deleted with the sandbox |
| `Mounted(target=None, read_only=False)` | Mounted as a further directory, or a file | at `target`, else at its own absolute path | reach the host, unless `read_only=True` |
| `Uploaded(target)` | Its contents copied into `target` before the task runs | under `target` | stay in the sandbox |

- At most one `WorkspaceDir` per task: a run with two raises `TaskError`.
- Paths are expanded (`~`) and resolved to absolute host paths before they are
  mounted or copied; the parameter keeps the value the caller gave.
- `Uploaded` creates `target` as root, owned by the default user of the kit, so
  it may lie where that user cannot write (`/work`). The copy is made before the
  dependencies and the function run.
- An input whose value is `None` (`Path | None = None`) is neither mounted nor
  copied.
- `client.create(workspace=..., clone=True, workspaces=[...])` gives the same
  modes to a sandbox created with the client.

## Example

```python
from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, Mounted, Uploaded, WorkspaceDir

app = FastSandbox("paths")


@app.task(kit="shell")
async def inventory(
    ctx: Context,
    repo: Annotated[Path, WorkspaceDir()],
    data: Annotated[Path, Mounted("/data", read_only=True)],
    fixtures: Annotated[Path, Uploaded("/work/fixtures")],
) -> list[str]:
    """Lists what the sandbox sees of three host directories."""
    listings = []
    for path in (str(repo.resolve()), "/data", "/work/fixtures"):
        output = await ctx.sandbox.exec(["ls", "-A", path], check=True)
        listings.append(output.stdout.strip())
    return listings
```

```sh
fastsandbox run app.py inventory --repo . --data ~/datasets --fixtures tests/fixtures
```

Clone mode returning the commits made in the sandbox as a patch:

```python
from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("patches")


@app.task(kit="shell", timeout="10m")
async def format_code(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Formats a clone of the repository and returns the commit as a patch."""
    workdir = str(repo.resolve())
    head = await ctx.sandbox.exec(["git", "rev-parse", "HEAD"], working_dir=workdir, check=True)
    await ctx.sandbox.exec("make format && git commit -am 'style: format'", working_dir=workdir)
    patch = await ctx.sandbox.exec(
        ["git", "format-patch", "--stdout", f"{head.stdout.strip()}..HEAD"],
        working_dir=workdir,
        check=True,
    )
    return patch.stdout
```

## Gotchas

- **Mounts are shared with the host**: what the task, or an agent, changes in
  a `WorkspaceDir()` or a read-write `Mounted` directory changes the files of
  the host during the run, and an interrupted run leaves half-done edits. Use
  `Uploaded`, `Mounted(..., read_only=True)` or `WorkspaceDir(clone=True)` when
  the host must stay as it is.
- Clone mode needs a Git repository; the clone goes with the sandbox: return
  what you keep (a patch, a file, a report) from the task.
- Name mounted paths inside the sandbox with `str(path.resolve())`, never with
  the relative value the caller passed.
- To copy the work back, `await ctx.sandbox.download_dir(path, host_dir)` or
  `await ctx.sandbox.read_text(path)`.
