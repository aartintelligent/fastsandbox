# Lifespan and state

Full page: https://aartintelligent.github.io/fastsandbox/framework/lifespan/

## API

- `FastSandbox(lifespan=fn)`: `fn(app)` returns an async context manager
  (type `Lifespan`, `from fastsandbox.types import Lifespan`), usually written
  with `contextlib.asynccontextmanager`:
  - code before `yield` runs when the application starts, on the host;
  - what it yields, a mapping or `None`, is the state: `ctx.state` in every
    run, `app.state` while the application is started (`None` gives `{}`);
  - code after `yield` runs when the application stops.
- `async with app:` starts the application once: connects one client, enters
  the lifespan once, and every run inside the block uses both. Entering it
  again inside the block raises `TaskError`. After the block, runs start the
  application for themselves again.
- Without `async with app:`, each run connects, enters the lifespan, runs and
  stops: each run then has a state of its own.
- Choosing the client, in the constructor:
  - `socket="/path/to/sandboxd.sock"`: another socket;
  - `client=client`: a `Client` already connected, used as it is (for instance
    `await fastsandbox.connect(version_policy="warn")`);
  - `kits=KitCache(...)`: where kits come from, instead of the cache of the
    process, which forges them without the `sbx` CLI and keeps them in memory:
    `KitCache(directory)` keeps them in a directory, `KitCache(sbx="sbx")`
    compiles them with the CLI.

## Example

```python
import contextlib
from collections.abc import AsyncIterator
from typing import Any

import fastsandbox
from fastsandbox import Context, FastSandbox


@contextlib.asynccontextmanager
async def lifespan(app: FastSandbox) -> AsyncIterator[dict[str, Any]]:
    runs: list[str] = []
    yield {"runs": runs}
    print(f"{app.name}: {len(runs)} runs")


app = FastSandbox("digests", lifespan=lifespan)


@app.task(kit="shell")
async def sha256(ctx: Context, text: str) -> str:
    """The SHA-256 digest of a text, computed in a sandbox."""
    output = await ctx.sandbox.exec(
        ["sh", "-c", 'printf %s "$1" | sha256sum', "sh", text], check=True
    )
    ctx.state["runs"].append(ctx.run_id)
    return output.stdout.split()[0]


async def main() -> None:
    async with app:  # one client, one lifespan, for the three runs
        for text in ("one", "two", "three"):
            print(await app.run("sha256", text=text))


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- The lifespan runs on the host, not in a sandbox: there is no sandbox yet.
  Per-run resources inside the sandbox belong to dependencies.
- A program that runs many tasks should use `async with app:`; otherwise every
  run opens a connection and runs the whole lifespan again.
- The state is shared by concurrent runs of a started application: guard
  mutable state accordingly.
- Tests point an application at the fake daemon with `socket=` and `kit=`
  (see the `testing` skill).
