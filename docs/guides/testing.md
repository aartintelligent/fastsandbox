# Testing

Code that creates sandboxes needs a daemon; its tests should not.
[`fastsandbox.testing`][fastsandbox.testing] has a fake daemon,
[`FakeDaemon`][fastsandbox.testing.FakeDaemon], which serves the socket API in
memory, and [`fake_package()`][fastsandbox.testing.fake_package], which writes
kit packages that need neither the `sbx` CLI nor an image. This page shows how
to test an application with them, how to run code written for the real daemon
against the fake one unchanged, and what the fake cannot do.

The examples are async test functions: run them with
[pytest-asyncio](https://pytest-asyncio.readthedocs.io/) in its `auto` mode,
or mark them with `@pytest.mark.asyncio`.

## Testing an application

```python title="docs_src/testing/test_word_count.py"
--8<-- "docs_src/testing/test_word_count.py"
```

- `async with FakeDaemon() as daemon:` listens on a Unix socket of a temporary
  directory, `daemon.socket_path`, until the block ends.
- [`daemon.on_exec(handler)`][fastsandbox.testing.FakeDaemon.on_exec] decides
  what commands print and exit with: the handler, plain or async, receives the
  name of the sandbox and the command as a list (a string command arrives as
  `["sh", "-c", script]`), and returns an
  [`ExecOutput`][fastsandbox.models.ExecOutput]. Without one, every command
  exits with 0 and prints nothing.
- `FastSandbox(socket=..., kit=fake_package(...))` points the application at the
  fake daemon, with a kit package it can create sandboxes from.
- `daemon.sandboxes` holds the sandboxes that exist: empty again after the run,
  since the run deleted its sandbox.

## What the fake daemon records

The state of the fake daemon is plain data, for the assertions of a test:

| Attribute | Holds |
|---|---|
| `sandboxes` | The sandboxes, by name, in the shape of `GET /sandbox/{name}`; `sandboxes[name]["request"]` is the creation request |
| `rules` | The network rules applied through it |
| `files` | The files written into sandboxes, by `(sandbox, path)` |
| `requests` | Every request it received, in order |

[`daemon.requests_to(method, pattern)`][fastsandbox.testing.FakeDaemon.requests_to]
selects requests by route, with the parameters of the route in braces:

```python
create = daemon.requests_to("POST", "/sandbox")[0].json()
commands = [r.json()["cmd"] for r in daemon.requests_to("POST", "/sandbox/{name}/exec")]
```

Each is a [`Request`][fastsandbox.testing.Request]: its method, path, query,
headers and body, and `json()` to decode the body.

## Code written for the real daemon

An application declared as it is used in production, `FastSandbox("ci")` with
the kits of `sbx`, runs against the fake daemon when the environment points it
there:

```python title="docs_src/testing/test_environment.py" hl_lines="21-24"
--8<-- "docs_src/testing/test_environment.py"
```

- `DOCKER_SANDBOXES_API` ([`fastsandbox.SOCKET_ENV`][fastsandbox.SOCKET_ENV])
  names the socket [`connect()`][fastsandbox.connect] uses when it is given
  none.
- `FASTSANDBOX_KIT_CACHE` moves the kit cache; a package written there under
  the cache key of a kit, `Kit(base="shell").cache_key`, is the package of that
  kit. `fake_package` writes one compiled with the `sbx` version the fake daemon
  reports, so that the cache uses it instead of compiling the kit with the CLI.

The tests of this repository make that a fixture, `fake_environment`, with
packages of the `shell` and `claude` kits: every snippet of this documentation
is tested that way.

## Agents

`fake_package(directory, agent="claude", artifact=...)` writes the package of an
agent kit; the artifact describes the program of the agent, its run options and
the hosts it needs:

```python
fake_package(
    tmp_path / "claude",
    agent="claude",
    artifact={
        "manifest": {"name": "claude", "binary": "claude", "runOptions": ["--yolo"]},
        "caps": {"network": {"allow": ["api.anthropic.com:443"]}},
    },
)
```

A task declared with `@app.agent("claude")` then runs against the fake daemon:
its credentials are pushed (set dummy values in the environment), the hosts of
the agent are allowed, and
[`agent.command(prompt)`][fastsandbox.AgentRunner.command] gives the command a
prompt would run. Running the agent itself, with `prompt`, `stream` or
`session`, needs the real daemon, as the next section explains.

## Routes and limits

The fake daemon serves what the client and the framework need for most tasks:
the health of the daemon, the life cycle of sandboxes, sessions, commands,
files, network rules, credentials, the ports of a sandbox and the loading of
images. A route it does not serve answers `404`.
[`daemon.route(method, pattern)`][fastsandbox.testing.FakeDaemon.route] adds a
route, or replaces a built-in one, with a handler that returns a
[`Response`][fastsandbox.testing.Response]:

```python
@daemon.route("GET", "/sandbox/{name}/ports")
def ports(request: Request) -> Response:
    return Response(200, [{"host_port": 8080, "sandbox_port": 80, "protocol": "tcp"}])
```

Interactive sessions, agent runs and SSH tunnels upgrade the HTTP connection of
the socket into a raw stream, which the fake daemon does not do: it answers
them with `501`. Code that uses them,
[`Sandbox.attach`][fastsandbox.Sandbox.attach],
[`AgentRunner.prompt`][fastsandbox.AgentRunner.prompt] and
[`stream`][fastsandbox.AgentRunner.stream], or `ssh_tunnel`, is tested against
the real daemon. The fake daemon does not run commands either: what a test
asserts about one is what its `on_exec` handler answered.
