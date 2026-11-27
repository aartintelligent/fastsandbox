"""Running a coding agent unattended: a task, a prompt, and a check that does not trust the agent.

`main` is the whole flow of the `agent-*-automation` examples, the flow of a
runner: forge the kit without the `sbx` CLI, create a sandbox, give it the credential found
in the environment (else the secret stored with `sbx secret set` applies),
mount the task written on the host as its workspace, run the agent in its
non-interactive mode with a deadline, then check the result with the
project's own tests, and show what changed and which hosts the agent reached.
The agent works on the files of the host, as with `sbx run`: nothing is copied
back.

The non-interactive command of each agent is its profile in
`fastsandbox.agents`, built from the program and the run options its kit
declares (`KitPackage.agent`). In an application, `FastSandbox.agent` and
`ctx.agent.prompt(...)` run the same command; the examples spell the flow out
with the client, to relay the output of the agent as it comes.

The default task is the `calc` project of `common/task/`, whose test suite
fails; a prompt given on the command line replaces the default one.
"""

from __future__ import annotations

import argparse
import asyncio
import functools
import json
import shlex
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any, BinaryIO, Literal

import common
import fastsandbox
from common import agent, kit
from fastsandbox import SandboxTimeoutError
from fastsandbox.agents import agent_profile
from fastsandbox.models import AttachSpec, Workspace

if TYPE_CHECKING:
    from fastsandbox import AgentProfile, Sandbox
    from fastsandbox.models import ExecOutput

__all__ = ["DEFAULT_PROMPT", "RUNS", "main", "run", "summarize"]

TASK = Path(__file__).parent / "task"
"""The default task: a calculator in POSIX shell whose `sub` operation adds."""

EXECUTABLES = frozenset({"calc.sh", "test.sh"})
"""The files of the task written executable on the host."""

RUNS = Path(__file__).resolve().parents[1] / "target" / "automation"
"""Where the task of each run is written on the host: `examples/target/automation/<run>/`.

`target/` is ignored by Git; the task of a run stays there after it, as the
agent left it.
"""

DEFAULT_PROMPT = (
    "The test suite of this project fails: run `sh test.sh` to see it. Fix the bug in calc.sh "
    "so that every test passes, without changing test.sh. Then run `sh test.sh` again to "
    "confirm, and summarize the fix in one sentence."
)
"""Prompt of the default task."""

AGENT_DEADLINE = 15 * 60.0
"""How long the agent may work on the task, in seconds."""

EXIT_TIMEOUT = 30.0
"""How long the exit code of the agent is awaited once its output has ended, in seconds."""

SUMMARY_CHARS = 300
"""Longest summary printed for one streamed event."""


def main(name: str) -> None:
    """Runs the agent `name` unattended, the entry point of every `agent-*-automation` example.

    The words given on the command line form the prompt, which replaces the
    default task; `--help` prints the documentation of the example.

    Args:
        name: The kit of the agent, as `sbx create` takes it, e.g. `claude`.
    """
    parser = argparse.ArgumentParser(
        prog=f"just example agent-{name}-automation",
        description=sys.modules["__main__"].__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "prompt",
        nargs=argparse.REMAINDER,
        metavar="PROMPT",
        help="the task for the agent, replacing the default one",
    )
    words: list[str] = parser.parse_args().prompt
    prompt = " ".join(words) or DEFAULT_PROMPT
    common.main(functools.partial(run, agent_profile(name), prompt))


async def run(profile: AgentProfile, prompt: str) -> None:
    """Runs the agent of `profile` unattended on `prompt`, and checks its work.

    The sandbox is removed in every case; the task stays on the host.

    Raises:
        KitForgeError: When the kit cannot be forged.
        SandboxTimeoutError: When the agent exceeds its deadline (an agent
            without a credential cannot log in).
        ExampleError: When the kit declares no agent, or when the tests of the
            task still fail after the agent.
    """
    forwarded = profile.forwarded_values()
    if not profile.found_credentials() and not forwarded:
        # A secret stored with `sbx secret set` applies to every sandbox, and
        # the socket does not tell whether there is one.
        names = [name for credential in profile.credentials for name in credential.env]
        print(
            f"no credential in the environment ({', '.join([*names, *profile.forwarded_env])}): "
            "the agent relies on the secrets stored with `sbx secret set`, since nobody can "
            "log in",
            file=sys.stderr,
        )
    client = await common.connect()
    package = await kit.package(client, profile.name)
    described = package.agent
    if described is None:
        raise common.ExampleError(f"the {profile.name} kit declares no agent program")
    name = fastsandbox.unique_name(f"example-{profile.name}-auto")

    # The task lives on the host, mounted as the workspace of the sandbox at
    # its own path: the agent changes the files of the host. A pristine copy,
    # mounted read-only, gives the diff without the agent being able to alter
    # it.
    project = await asyncio.to_thread(write_task, RUNS / name / "calc")
    original = await asyncio.to_thread(write_task, RUNS / name / "calc.orig")
    request = (
        package.request(name)
        .with_workspace(project)
        .with_additional_workspace(Workspace(dir=original, read_only=True))
    )
    print(f"task written to {project}, mounted as the workspace", file=sys.stderr)

    async with client.create(kit=package, request=request) as sandbox, sandbox.running():
        pushed = await agent.push_credentials(sandbox, profile)
        if pushed:
            print(f"credentials given to the sandbox: {', '.join(pushed)}", file=sys.stderr)

        before = await _tests(sandbox, project)
        print(f"tests before the agent: exit code {before.exit_code}", file=sys.stderr)

        command = profile.headless(described, prompt)
        print(f"running {shlex.join(command)} without a terminal", file=sys.stderr)
        spec = AttachSpec(cmd=command, working_dir=project, env=forwarded)
        try:
            async with asyncio.timeout(AGENT_DEADLINE):
                code = await _run_agent(sandbox, spec, profile.output)
        except TimeoutError:
            raise SandboxTimeoutError(
                "the agent did not finish within its deadline",
                operation="agent run",
                after=AGENT_DEADLINE,
            ) from None
        print(f"agent exited with code {code}", file=sys.stderr)

        after = await _tests(sandbox, project)
        print(after.stdout, end="")
        diff = await sandbox.exec(["diff", "-ru", original, project])
        print(f"changes made by the agent:\n{diff.stdout}")
        print(f"the project, as the agent left it: {project}", file=sys.stderr)
        await _report_network(sandbox)

        if not after.ok:
            raise common.ExampleError("the tests still fail after the agent")


def write_task(dir: Path) -> str:
    """Writes the default task into the host directory `dir`, created when missing.

    Returns:
        The real path of `dir`, as a workspace must be given: it is mounted at
        that path, and a `..` or a symbolic link in it names nothing inside
        the sandbox.
    """
    dir.mkdir(parents=True, exist_ok=True)
    for source in sorted(TASK.iterdir()):
        if not source.is_file():
            continue
        target = dir / source.name
        shutil.copyfile(source, target)
        target.chmod(0o755 if source.name in EXECUTABLES else 0o644)
    return str(dir.resolve())


async def _tests(sandbox: Sandbox, project: str) -> ExecOutput:
    """Runs the test suite of the task."""
    return await sandbox.exec(["sh", "test.sh"], working_dir=project)


async def _run_agent(sandbox: Sandbox, spec: AttachSpec, output: Literal["jsonl", "text"]) -> int:
    """Runs `spec` without a terminal, relaying its output as it comes, and returns its exit code.

    Text is relayed as it is; JSON lines are summarized one by one
    (`summarize`). Standard error goes to standard error.
    """
    session = await sandbox.attach(spec)
    # Nothing is typed: closing the input keeps the agent from waiting for it.
    await session.close_stdin()
    pending = b""
    async for chunk in session:
        if chunk.stream != "stdout":
            _write(sys.stderr.buffer, chunk.data)
        elif output == "text":
            _write(sys.stdout.buffer, chunk.data)
        else:
            pending += chunk.data
            *lines, pending = pending.split(b"\n")
            for line in lines:
                if (summary := summarize(line)) is not None:
                    _write(sys.stdout.buffer, summary.encode())
    if (summary := summarize(pending)) is not None:
        _write(sys.stdout.buffer, summary.encode())
    return await session.wait(EXIT_TIMEOUT)


def _write(stream: BinaryIO, data: bytes) -> None:
    """Writes `data` to `stream` at once, after what `print` buffered."""
    sys.stdout.flush()
    sys.stderr.flush()
    stream.write(data)
    stream.flush()


def summarize(line: bytes) -> str | None:
    """One line summarizing a JSON event of an agent, or the line itself when it is not JSON.

    The fields read are those the agents document for their streamed output:
    `type` and `subtype`, a `message` with content blocks of `text` or
    `tool_use`, an `item` with a `text`, and the final `result`.

    Returns:
        The summary with its newline, or `None` for an empty line.
    """
    text = line.decode(errors="replace").strip()
    if not text:
        return None
    try:
        event: Any = json.loads(text)
    except ValueError:
        return f"{text}\n"
    if not isinstance(event, dict):
        return f"{text}\n"
    parts: list[str] = []
    if isinstance(subtype := event.get("subtype"), str):
        parts.append(subtype)
    message = event.get("message")
    blocks = message.get("content") if isinstance(message, dict) else None
    for block in blocks if isinstance(blocks, list) else []:
        if not isinstance(block, dict):
            continue
        if block.get("type") == "text" and isinstance(block.get("text"), str):
            parts.append(block["text"])
        elif block.get("type") == "tool_use":
            parts.append(f"tool {block.get('name', '?')}")
    item = event.get("item")
    for value in (
        item.get("text") if isinstance(item, dict) else None,
        event.get("text"),
        event.get("result"),
    ):
        if isinstance(value, str):
            parts.append(value)
    kind = event.get("type") if isinstance(event.get("type"), str) else "event"
    summary = " \N{MIDDLE DOT} ".join(parts).replace("\n", " ")[:SUMMARY_CHARS]
    return f"[{kind}] {summary}\n"


async def _report_network(sandbox: Sandbox) -> None:
    """Prints the hosts the sandbox reached or was refused, as the proxy logged them."""
    log = (await sandbox.client.policy.log()).for_sandbox(sandbox.name)
    for host in log.allowed_hosts:
        print(f"network: reached {host.host} ({host.count_since} times)", file=sys.stderr)
    for host in log.blocked_hosts:
        print(f"network: refused {host.host} ({host.count_since} times)", file=sys.stderr)
