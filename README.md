# fastsandbox

**Run code and coding agents in throw-away Docker Sandboxes, from Python.**

fastsandbox lets a Python program hand work to
[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/): a test suite to run
on a copy of a repository, an issue for a coding agent to fix, a tool to try
out. It gets back a typed result, and the sandbox is gone.

[![CI](https://github.com/aartintelligent/fastsandbox/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/aartintelligent/fastsandbox/actions/workflows/ci.yml)
[![Coverage](https://codecov.io/gh/aartintelligent/fastsandbox/graph/badge.svg)](https://codecov.io/gh/aartintelligent/fastsandbox)
[![PyPI](https://img.shields.io/pypi/v/fastsandbox.svg)](https://pypi.org/project/fastsandbox/)
[![Python](https://img.shields.io/python/required-version-toml?tomlFilePath=https://raw.githubusercontent.com/aartintelligent/fastsandbox/main/pyproject.toml)](https://aartintelligent.github.io/fastsandbox/get-started/installation/)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-blue.svg)](https://aartintelligent.github.io/fastsandbox/project/license/)
[![Monthly Downloads](https://static.pepy.tech/badge/fastsandbox/month)](https://pepy.tech/projects/fastsandbox)

[![Requires Docker Sandboxes](https://img.shields.io/badge/requires-Docker%20Sandboxes-2496ED?logo=docker&logoColor=white)](https://aartintelligent.github.io/fastsandbox/get-started/installation/)

[![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-D97757?logo=claude&logoColor=white)](https://aartintelligent.github.io/fastsandbox/get-started/claude-code/)

[Documentation](https://aartintelligent.github.io/fastsandbox/) ·
[Quickstart](https://aartintelligent.github.io/fastsandbox/get-started/quickstart/) ·
[API reference](https://aartintelligent.github.io/fastsandbox/reference/) ·
[Examples](https://aartintelligent.github.io/fastsandbox/guides/examples/) ·
[docker-sandbox, the Rust crate underneath](https://github.com/aartintelligent/docker-sandbox)

fastsandbox is an independent, community-maintained project. It is not
affiliated with, sponsored or endorsed by Docker, Inc., and uses the Docker
name only to say which product it is made for.

## Docker Sandboxes, in a few words

[Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) runs code, and coding
agents, in throw-away microVMs on your machine. Each sandbox has its own
system, its own files and its own network policy. Its proxy decides which
hosts it reaches and adds the credentials of a service to the requests sent to
it, so a secret never has to be inside the sandbox. A sandbox is created from a
kit, which says what it holds: a plain shell, or a coding agent such as Claude
Code or Codex, ready to work. All of it is driven by the `sbx` CLI, which talks
to a daemon, `sandboxd`, through a socket.

For anyone who runs coding agents, this changes what is safe. An agent can edit
files and run commands without asking, because the worst it can break is a
machine thrown away after the run. It can work on a clone of your repository
rather than the repository itself, and reach only the hosts you allowed.

## The goal of this stack

Without a library, a Python program that wants a sandbox runs the CLI and
parses what it prints. fastsandbox talks to the socket of the daemon instead.

It is built on [`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox),
a Rust crate by the same author that does all the work with the daemon. The
crate is the client of the socket: it maps the API of the daemon version by
version, and checks the version of the daemon when it connects. fastsandbox
brings it to Python through a native extension, and adds two layers: a typed
async client that reaches every route of the daemon, and **FastSandbox**,
where the work done in a sandbox is a typed function under a decorator.

What that buys you, in practice:

- **Work declared, not scripted.** `@app.task` and `@app.agent` put the kit,
  the network rules, the deadline and the credentials of a sandbox next to the
  function that uses it. The signature of the function validates its inputs
  and its result.
- **Every agent `sbx` knows, one way.** Claude Code, Codex, Copilot, Cursor,
  Devin, Docker Agent, Droid, Kiro and OpenCode are all run the same way: one
  prompt run unattended, a stream of what the agent reports as it goes, or an
  interactive session.
- **Keys that stay outside.** The API key of an agent is read from your
  environment and pushed to the sandbox of the run only. Its proxy adds the key
  to the requests the agent sends to its service; the agent only sees a
  placeholder.
- **Your repository untouched.** On a private clone, the agent may change and
  commit anything. Its work comes back as a patch to review, and your
  directory stays as it was.
- **Sandboxes that clean up after themselves.** The sandbox of a run is
  deleted when the run ends, also on an error, a timeout or Ctrl-C.
- **Errors you can act on.** A missing sandbox, a deadline or a failed command
  each raise their own error class, with typed details, not a message to
  parse.
- **Tests without a daemon.** A fake daemon serves the socket API in memory,
  so the code that drives sandboxes is tested in any CI.

## Where it fits

- **Coding agents on your repositories**: a fix, a review, a patch from a
  private clone, or several agents on one issue with the tests choosing the
  patch that holds.
- **Checks in a throw-away machine**: a test suite, a build or a linter on a
  copy of a repository, with access to the hosts it needs and no others.
- **Code you would rather not run on your machine**: run it in a sandbox
  instead, then read its output and the hosts it tried to reach.
- **Agents with tools**: the MCP servers an agent needs, given through the
  gateway of its sandbox.
- **Tooling around the daemon**: a watcher on its events, an audit of the
  network policy, a cleanup of old sandboxes and images.

## Getting started

Install [Docker Sandboxes](https://docs.docker.com/ai/sandboxes/) first, its
daemon running for your user: fastsandbox connects to its socket and does
nothing without it. Then, with Python 3.12 or newer:

```sh
uv add fastsandbox      # or: pip install fastsandbox
fastsandbox info        # finds the daemon and checks its API version
```

An agent task: Claude Code explains a project, working on a private clone of
it.

```python
from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, WorkspaceDir

app = FastSandbox("quickstart")


@app.agent("claude", timeout="15m")
async def explain(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Has Claude Code explain a project, working on a private clone of it."""
    workdir = str(repo.resolve())
    await ctx.agent.prompt(
        "Explain what this project does and how its code is laid out, "
        "in twenty lines at most, and write the explanation to EXPLAINED.md.",
        working_dir=workdir,
    )
    # The file is in the clone, inside the sandbox: the host is untouched.
    return await ctx.sandbox.read_text(f"{workdir}/EXPLAINED.md")
```

```sh
export ANTHROPIC_API_KEY=sk-ant-...
fastsandbox run agent.py explain --repo .
```

The [quickstart](https://aartintelligent.github.io/fastsandbox/get-started/quickstart/)
explains this task line by line. From there, the
[documentation](https://aartintelligent.github.io/fastsandbox/) covers what a
real setup needs: an agent's repository, its network, following its work,
giving it tools, then tasks, the client and testing.

### With Claude Code

The repository is also a marketplace of Claude Code plugins. Its plugin teaches
Claude the whole library and adds commands that set up a project, check the
machine and add tasks:

```text
/plugin install fastsandbox --marketplace aartintelligent/fastsandbox
```

See [With Claude Code](https://aartintelligent.github.io/fastsandbox/get-started/claude-code/).

## Status

fastsandbox is in alpha. Version `0.1` covers:

- the whole socket API of the daemon;
- tasks and agent tasks, with the nine agents of `sbx`;
- the MCP gateway;
- the fake daemon for tests.

It runs on Linux and macOS, where Docker Sandboxes runs.

The socket API of Docker Sandboxes is private and changes with `sbx` releases.
Each release of fastsandbox is checked against a range of API versions, and
connecting to a daemon outside that range fails unless you allow it. The API
of fastsandbox itself may still change before 1.0. Such changes are listed in
the [changelog](https://github.com/aartintelligent/fastsandbox/blob/main/CHANGELOG.md).

## FAQ

**Is this an official Docker project?** No. fastsandbox is independent and
community-maintained. Docker Sandboxes, its licence and its roadmap belong to
Docker, Inc.

**Do I need Docker Sandboxes installed?** Yes. fastsandbox is a client of its
daemon and connects to the `sandboxd` socket, and that is all it uses: it forges
the kits it needs through the socket, without the `sbx` CLI. The CLI is used
only for a kit that it alone resolves, such as a local kit directory, when
asked.

**Can it drive the Docker Engine, containers and images?** No. It works only
with Docker Sandboxes; containers and images outside it are the job of the
Docker SDK.

**Does my API key enter the sandbox?** No, for every agent but Kiro. The key is
pushed as a secret of the sandbox of the run, and the proxy adds it to the
requests the agent sends to its service. Kiro has no such secret in `sbx`, so
its key is passed to the agent process as an environment variable, and is
visible inside the sandbox.

**Is it safe to let an agent run unattended?** The isolation is that of Docker
Sandboxes; fastsandbox decides what crosses it: which directory, which hosts,
which credentials. The default network policy of `sbx` may allow everything,
so give an unattended agent network rules. Then check its work with the tests
of the project rather than trusting what it reports. The
[security guide](https://aartintelligent.github.io/fastsandbox/guides/security/)
goes through each point.

**Can I test my code without a daemon?** Yes. `fastsandbox.testing` serves the
socket API from memory: no `sbx`, no image, no microVM.

**Is it production ready?** It is `0.1`. Every change runs the following
checks:

- the tests on Linux, and on macOS when the package changes;
- mypy in strict mode;
- a coverage threshold;
- the build of the documentation;
- an audit of the Rust and Python dependencies.

The socket API it relies on is private, though: read the status above before
building a product on it.

**How is it organised?** A Python package over
[`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox), the Rust
client of the socket, joined by a thin native extension. Everything about the
daemon is in the crate: a new route or field of the daemon goes into it
first, then into fastsandbox. Every helper and every default is Python. The
[design page](https://aartintelligent.github.io/fastsandbox/overview/design/)
records the layers and the decisions behind them.

## Contributing

See [CONTRIBUTING.md](https://github.com/aartintelligent/fastsandbox/blob/main/CONTRIBUTING.md):
setting up, the checks, commits and pull requests. To report a vulnerability,
see the [security policy](https://github.com/aartintelligent/fastsandbox/blob/main/SECURITY.md).

## License

Licensed under either of [Apache License, Version 2.0](https://github.com/aartintelligent/fastsandbox/blob/main/LICENSE-APACHE)
or [MIT license](https://github.com/aartintelligent/fastsandbox/blob/main/LICENSE-MIT)
at your option.

Unless you explicitly state otherwise, any contribution intentionally submitted
for inclusion in this work by you, as defined in the Apache-2.0 license, shall
be dual licensed as above, without any additional terms or conditions.
