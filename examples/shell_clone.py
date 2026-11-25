"""A Git repository worked on in clone mode, and the work fetched back on the host.

In clone mode (`client.create(..., workspace=repository, clone=True)`, as
`sbx run --clone`) the sandbox works on a private clone of the repository, at
the same path and with its history, while the repository of the host is
mounted read-only at `/run/sandbox/source`: the agent can neither change it
nor push to it, and its commits stay in the sandbox until the host fetches
them.

The `sbx` CLI fetches them through a Git remote whose `uploadpack` runs
`sbx upload-pack <sandbox>`: `git upload-pack` started in the sandbox, its
standard input and output relayed over the socket. This example does the same
with the library: `git fetch --upload-pack` runs this script again as
`upload-pack <sandbox> <repository>`, which relays the exchange of Git to an
interactive execution of `git upload-pack` in the sandbox. No remote is
written to the configuration of the repository.

The repository is made for the run under `examples/target/clone/`, and left
there to be looked at (`git log sandbox/main`).

Run it with:

    just example shell-clone
"""

from __future__ import annotations

import asyncio
import os
import shlex
import subprocess
import sys
from pathlib import Path

import common
import fastsandbox
from common import kit
from fastsandbox.models import AttachSpec

SCRIPT = Path(__file__).resolve()
"""This script, which `git fetch` runs again as the relay of `git upload-pack`."""

RUNS = SCRIPT.parent / "target" / "clone"
"""Directory of the repositories made by the runs."""

RELAY = "upload-pack"
"""First argument with which `git fetch` runs this script as the relay of `git upload-pack`."""

AGENT_UID = "1000"
"""User of the sandbox that owns the clone, as the CLI runs `git upload-pack`."""

EXIT_TIMEOUT = 30.0
"""How long `git upload-pack` may take to exit once Git is done, in seconds."""

READ_SIZE = 65536
"""How many bytes of standard input the relay reads at once."""

AGENT_WORK = """\
pwd
git log --format=%s
printf 'written in the sandbox\\n' > AGENT.md
git add AGENT.md
git -c user.name=agent -c user.email=agent@example.invalid -c commit.gpgsign=false \\
    commit -q -m 'agent work'
touch /run/sandbox/source/AGENT.md 2>/dev/null && echo source-writable || echo source-read-only
"""
"""What the agent does in the clone.

It looks at the history, commits a file, then tries to write to the
repository of the host.
"""


async def main() -> None:
    """Runs the example."""
    client = await common.connect()
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-clone")
    repository = seed(RUNS / name)
    print("repository of the host: one commit, `seed`")

    async with (
        client.create(name, kit=package, workspace=repository, clone=True) as sandbox,
        sandbox.running(),
    ):
        output = await sandbox.exec(AGENT_WORK, check=True)
        lines = output.stdout.splitlines()
        if lines != [repository, "seed", "source-read-only"]:
            raise common.ExampleError(f"unexpected work in the sandbox: {lines}")
        print(
            "in the sandbox: a clone at the same path, with the history, and the source read-only"
        )
        print("the agent committed `agent work` in its clone")
        if git(repository, "log", "--format=%s") != "seed\n":
            raise common.ExampleError("the commit reached the repository of the host on its own")
        print("the repository of the host still has one commit")

        # `git fetch` runs the relay through a shell, with the URL appended:
        # the URL only names the sandbox, as the remote of the CLI does.
        upload_pack = shlex.join([sys.executable, str(SCRIPT), RELAY, sandbox.name, repository])
        # The fetch waits for the relay, a process of its own: run it off the
        # event loop.
        await asyncio.to_thread(
            git,
            repository,
            "fetch",
            "-q",
            "--upload-pack",
            upload_pack,
            f"/sandbox/{sandbox.name}",
            "+refs/heads/*:refs/remotes/sandbox/*",
        )
        fetched = git(repository, "log", "--format=%s", "sandbox/main")
        if fetched != "agent work\nseed\n":
            raise common.ExampleError(f"unexpected history fetched: {fetched!r}")
        file = git(repository, "show", "sandbox/main:AGENT.md").rstrip("\n")
        print(
            "fetched on the host as sandbox/main: `agent work` on top of `seed`, "
            f"AGENT.md reads {file!r}"
        )


async def upload_pack(name: str, repository: str) -> int:
    """Relays standard input and output to `git upload-pack repository` in the sandbox `name`.

    The `uploadpack` side of a `git fetch` from the sandbox: Git on the host
    talks to the standard input and output of this process. Returns the exit
    code of `git upload-pack`.
    """
    client = await fastsandbox.connect()
    sandbox = client.sandbox(name)
    # Git asks for its protocol version through the environment.
    env = {"GIT_PROTOCOL": protocol} if (protocol := os.environ.get("GIT_PROTOCOL")) else {}
    spec = AttachSpec(
        cmd=["git", "upload-pack", repository], user=AGENT_UID, working_dir="/", env=env
    )
    session = await sandbox.attach(spec)
    loop = asyncio.get_running_loop()
    stdin = asyncio.StreamReader()
    await loop.connect_read_pipe(lambda: asyncio.StreamReaderProtocol(stdin), sys.stdin)

    async def forward() -> None:
        """Copies standard input to the execution, then closes its input."""
        while data := await stdin.read(READ_SIZE):
            await session.write(data)
        await session.close_stdin()

    forwarding = asyncio.create_task(forward())
    try:
        async for chunk in session:
            # Git waits for each answer before it sends more: flush every chunk.
            stream = sys.stdout.buffer if chunk.stream == "stdout" else sys.stderr.buffer
            stream.write(chunk.data)
            stream.flush()
    finally:
        forwarding.cancel()
    return await session.wait(EXIT_TIMEOUT)


def seed(directory: Path) -> str:
    """Makes a repository with one commit in `directory`, and returns its real path.

    The clone of the sandbox sits at that same path.
    """
    directory.mkdir(parents=True, exist_ok=True)
    git(directory, "init", "-q", "-b", "main", "repo")
    repository = (directory / "repo").resolve()
    (repository / "README.md").write_text("made by the shell-clone example\n")
    git(repository, "add", "README.md")
    git(repository, "commit", "-q", "-m", "seed")
    return str(repository)


def git(directory: str | Path, *args: str) -> str:
    """Runs `git args` in `directory`, and returns its standard output.

    The hooks, signing and identity of the user are left out.

    Raises:
        ExampleError: When Git fails.
    """
    identity = ["-c", "user.name=example", "-c", "user.email=example@example.invalid"]
    isolation = ["-c", "commit.gpgsign=false", "-c", "core.hooksPath=/dev/null"]
    result = subprocess.run(
        ["git", *identity, *isolation, *args],
        cwd=directory,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise common.ExampleError(f"git {' '.join(args)}: {result.stderr.strip()}")
    return result.stdout


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == RELAY:
        raise SystemExit(fastsandbox.run(upload_pack(sys.argv[2], sys.argv[3])))
    common.main(main)
