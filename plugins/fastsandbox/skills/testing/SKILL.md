---
name: testing
description: Testing code that uses fastsandbox without Docker Sandboxes - `FakeDaemon` (a fake sandboxd on a Unix socket, `on_exec`, `route`, `requests_to`, `sandboxes`, `rules`, `files`, `requests`), the published kits it serves so that kits are forged against it (`kits`, `PublishedKit`), `fake_package` kit packages that need no sbx CLI, `Request` and `Response`, pointing a FastSandbox application or a client at the fake, testing agent tasks, and what the fake cannot do. Load before writing or fixing tests (pytest, pytest-asyncio) for tasks, agent tasks or client code, or a CI that has no daemon.
---

# Testing without a daemon

Code that creates sandboxes needs Docker Sandboxes; its tests do not. The
testing module of fastsandbox serves the socket API of the daemon in memory
(`FakeDaemon`) and writes kit packages that need neither the `sbx` CLI nor an
image (`fake_package`), so tasks and client code run in any CI.

Full documentation: https://aartintelligent.github.io/fastsandbox/guides/testing/

## Setup

```toml
# pyproject.toml of the project under test
[dependency-groups]
dev = ["pytest", "pytest-asyncio"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

Without `asyncio_mode = "auto"`, mark each async test with
`@pytest.mark.asyncio`.

## FakeDaemon

```python
from fastsandbox.testing import FakeDaemon, Request, Response, fake_package
```

| API | What it does |
|---|---|
| `FakeDaemon(*, version="v0.54.1", api_version="0.52.0")` | the fake; `async with FakeDaemon() as daemon:` starts it on a socket of a temporary directory and stops it at the end of the block (`await daemon.start()` / `await daemon.stop()` otherwise) |
| `daemon.socket_path` | the `Path` of its socket; `RuntimeError` before it is started |
| `daemon.on_exec(handler)` | decides what commands print and exit with: `handler(sandbox_name: str, cmd: list[str])`, plain or async, returns an `ExecOutput`; a string command arrives as `["sh", "-c", script]`; usable as a decorator. Default: exit code 0, no output |
| `daemon.route(method, pattern)` | decorator adding or replacing a route, ahead of the built-in ones: `handler(request: Request) -> Response` (plain or async); `pattern` like `/sandbox/{name}/ports` |
| `daemon.requests_to(method, pattern)` | the recorded `Request` objects of a route |
| `daemon.sandboxes` | sandboxes that exist, by name, in the shape of `GET /sandbox/{name}`; `sandboxes[name]["request"]` is the creation request; empty again after a task run |
| `daemon.rules` | the network rules applied through it |
| `daemon.files` | files written into sandboxes, by `(sandbox, absolute path)` |
| `daemon.requests` | every request received, in order |

`Request`: `method`, `path` (no query string), `query`, `headers` (lowercase
names), `body` (bytes), `params` (route parameters, e.g. `{"name": "job-42"}`),
and `json()`.

`Response(status=200, body=None, lines=None, hold=False, raw=None,
content_type="application/octet-stream")`: `body` is sent as JSON, `lines` as
an NDJSON stream instead, `raw` as bytes; `hold` keeps a streamed body open.

Built-in routes: daemon health; list, create, inspect, delete, start and stop
of sandboxes; held sessions; `exec`; file upload and download; credentials;
the ports of a sandbox; network rules (list, apply); image load and list. Any
other route answers 404.

## fake_package

`fake_package(directory, *, agent="shell", sbx_version="v0.54.1",
artifact=None)` writes a kit package into `directory` and returns the
`KitPackage`. For an agent kit, `artifact` describes it:

```python
from pathlib import Path

from fastsandbox import KitPackage
from fastsandbox.testing import fake_package


def claude_package(tmp_path: Path) -> KitPackage:
    return fake_package(
        tmp_path / "claude",
        agent="claude",
        artifact={
            "manifest": {"name": "claude", "binary": "claude", "runOptions": ["--yolo"]},
            "caps": {"network": {"allow": ["api.anthropic.com:443"]}},
        },
    )
```

## Pointing code at the fake

Two ways:

1. **Explicitly**, for an application or a client built in the test:
   `FastSandbox(socket=str(daemon.socket_path), kit=fake_package(tmp_path / "kit"))`,
   or `await fastsandbox.connect(daemon.socket_path)` for client code.
2. **Through the environment**, for an application declared as in production
   (`FastSandbox("ci")`, kits of `sbx`): set `DOCKER_SANDBOXES_API`
   (`fastsandbox.SOCKET_ENV`) to the socket of the fake, and
   either let the kits be forged against the fake, which serves the published
   `shell` and `claude` kits (`daemon.kits`, a `PublishedKit` each, extended
   with a kit of one's own), or set `FASTSANDBOX_KIT_CACHE` to a directory
   where `fake_package` wrote a package under the cache key of each kit used,
   `Kit(base="shell").cache_key`. The default `sbx_version` of `fake_package`
   matches the version the fake reports, so the cache uses the package as it
   is.

## A complete test

```python
from pathlib import Path

import pytest

import fastsandbox
from fastsandbox import Context, FastSandbox, Kit, Network
from fastsandbox.models import ExecOutput
from fastsandbox.testing import FakeDaemon, fake_package

app = FastSandbox("ci")


@app.task(kit="shell", network=Network.allow("pypi.org"))
async def python_version(ctx: Context) -> str:
    output = await ctx.sandbox.exec(["python3", "--version"], check=True)
    return output.stdout.strip()


async def test_python_version(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    async with FakeDaemon() as daemon:
        kits = tmp_path / "kits"
        fake_package(kits / Kit(base="shell").cache_key)
        monkeypatch.setenv(fastsandbox.SOCKET_ENV, str(daemon.socket_path))
        monkeypatch.setenv("FASTSANDBOX_KIT_CACHE", str(kits))
        daemon.on_exec(lambda sandbox, cmd: ExecOutput(exit_code=0, stdout="Python 3.14.0\n"))

        assert await app.run("python_version") == "Python 3.14.0"

        commands = [r.json()["cmd"] for r in daemon.requests_to("POST", "/sandbox/{name}/exec")]
        assert ["python3", "--version"] in commands
        assert daemon.rules  # the rule of the task was applied
        assert daemon.sandboxes == {}  # the run deleted its sandbox
```

## Agent tasks

A task declared with `@app.agent("claude")` runs against the fake daemon with a
`fake_package(..., agent="claude", artifact=...)` package: set a dummy key in
the environment (`monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy-key")`), and
the run pushes it as a service secret (`requests_to("POST",
"/sandbox/{name}/credentials")`) and allows the hosts of the artifact. Test:

- the declaration: `task = app.get_task("fix_bug")`, `task.agent.name`,
  `task.input_schema`, the markers of `task.parameters`, `task.timeout`;
- the command a prompt would run, from inside a task:
  `agent.command("prompt")` (an `AgentRunner` parameter) does not run it.

Running the agent itself (`ctx.agent.prompt`, `stream`, `session`) needs the
real daemon.

## Limits

- Interactive sessions, agent runs and SSH tunnels upgrade the connection: the
  fake answers them with 501. Code using `Sandbox.attach`,
  `AgentRunner.prompt` / `stream` / `session` or `ssh_tunnel` is tested against
  the real daemon (mark those tests and run them on a machine with Docker
  Sandboxes).
- Commands are not run: what a test asserts about one is what the `on_exec`
  handler answered. Make the handler branch on `cmd` when a task runs several
  commands.
- Routes it does not serve answer 404: add them with `daemon.route(...)`
  returning a `Response`.
- Use dummy secret values only; never read the real environment's keys in a
  test.
