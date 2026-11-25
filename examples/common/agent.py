"""Running a coding agent in a throw-away sandbox, with or without an MCP server.

`main` is the whole flow of the `agent-*` examples: compile the kit of the
agent once, create a sandbox from it, give it the credentials found in the
environment, load the MCP server of the `-mcp` variant and check it from
inside the sandbox, and plug the terminal into the agent session, opened with
what `sbx run` passes from the host (`common.host`).

What each agent can use comes from the library: `fastsandbox.agents` has a
profile per agent `sbx` knows, with the services and environment variables of
its credentials. A credential found in the environment is pushed to the
sandbox as a sandbox-scoped service secret: the proxy of the sandbox injects
it into outgoing requests, the agent never sees it, and it goes away with the
sandbox. The secrets stored with `sbx secret set` apply to the sandbox as to
any other; without a credential at all, the agent offers its own login inside
the session.
"""

from __future__ import annotations

import argparse
import functools
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

import common
import fastsandbox
from common import host, kit, mcp, terminal
from fastsandbox.agents import agent_profile

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastsandbox import AgentProfile, Client, KitPackage, Sandbox

__all__ = ["Launch", "main", "push_credentials", "run"]


def main(agent: str, *, with_mcp: bool = False) -> None:
    """Runs the example of `agent`, the entry point of every `agent-*` example.

    When `sbx` starts the script of an `-mcp` variant as the MCP server of the
    examples, it serves MCP instead, and runs nothing else.

    Args:
        agent: The kit of the agent, as `sbx create` takes it, e.g. `claude`.
        with_mcp: Gives the agent the MCP server of the examples.
    """
    if with_mcp and mcp.serve_if_requested():
        return
    profile = agent_profile(agent)
    suffix = "-mcp" if with_mcp else ""
    launch = Launch.parse(sys.argv[1:], prog=f"just example agent-{agent}{suffix}")
    common.main(functools.partial(run, profile, launch, with_mcp=with_mcp))


async def run(profile: AgentProfile, launch: Launch, *, with_mcp: bool = False) -> None:
    """Runs the agent of `profile` in a throw-away sandbox until its session ends.

    The sandbox, and the registration of the MCP server when `with_mcp` is
    set, are removed in every case.

    Raises:
        KitCompileError: When the kit cannot be compiled.
        SandboxError: When the sandbox cannot be created or started, or the
            session breaks.
    """
    client = await common.connect()
    package = await kit.package(client, profile.name)
    name = fastsandbox.unique_name(f"example-{profile.name}")
    registration = await mcp.Registration.add(client, f"{name}-tools") if with_mcp else None
    try:
        await _session(client, package, profile, launch, name, registration)
    finally:
        if registration is not None:
            await registration.remove()


async def _session(
    client: Client,
    package: KitPackage,
    profile: AgentProfile,
    launch: Launch,
    name: str,
    registration: mcp.Registration | None,
) -> None:
    """Creates the sandbox `name`, prepares it, and relays the agent session to the terminal."""
    # What `sbx run` adds from the host: the SSH agent of the sandbox, and the
    # terminal, time zone and desktop session of the agent session.
    request = package.request(name).model_copy(
        update={"ssh_agent_socket_path": await host.ssh_agent_socket(client)}
    )
    if launch.workspace is not None:
        print(
            f"workspace {launch.workspace}: mounted read-write, the agent changes its files",
            file=sys.stderr,
        )
        request = request.with_workspace(launch.workspace)
    spec = await host.agent_session(client, terminal.size(), launch.args)
    # Variables of an agent `sbx` knows no service secret for (Kiro) go to the
    # agent process as they are: their values are visible inside the sandbox.
    spec = spec.model_copy(update={"env": {**spec.env, **profile.forwarded_values()}})

    async with client.create(kit=package, request=request) as sandbox, sandbox.running():
        pushed = await push_credentials(sandbox, profile)
        if pushed:
            print(f"credentials given to the sandbox: {', '.join(pushed)}", file=sys.stderr)
        else:
            print(
                "no credential in the environment: the agent uses the secrets stored with "
                "`sbx secret set`, or offers its own login",
                file=sys.stderr,
            )
        if registration is not None:
            await sandbox.load_mcp_server(registration.name)
            await mcp.check_gateway(sandbox)
            print(
                f"MCP server {registration.name} loaded: ask the agent to call its `sum` tool",
                file=sys.stderr,
            )
        code = await terminal.relay(await sandbox.agent_session(spec))
        print(f"agent exited with code {code}", file=sys.stderr)


async def push_credentials(sandbox: Sandbox, profile: AgentProfile) -> list[str]:
    """Pushes to `sandbox` every credential of `profile` found in the environment.

    Each one becomes a service secret of that sandbox only; the values are
    never stored nor printed.

    Returns:
        The services pushed, e.g. `["anthropic"]`.
    """
    pushed = []
    for service, value in profile.found_credentials():
        await sandbox.push_service_secret(service, value)
        pushed.append(service)
    return pushed


@dataclass(frozen=True)
class Launch:
    """What follows the name of an agent example, as for `sbx run AGENT [PATH] [-- AGENT_ARGS...]`.

    Attributes:
        workspace: Host directory the agent works on, mounted read-write at
            its own path, by its real path. Without one, the agent works in
            the filesystem of the sandbox: nothing of the host is mounted.
        args: Arguments of the agent: options added to its default command,
            or a prompt in its place.
    """

    workspace: str | None = None
    args: tuple[str, ...] = ()

    @classmethod
    def parse(cls, words: Sequence[str], *, prog: str | None = None) -> Launch:
        """Reads `[PATH] [-- AGENT_ARGS...]` from `words`.

        `--help` prints the documentation of the example, the docstring of
        its script. Exits with an error message when the workspace is not a
        directory, or when more than one path comes before `--`.
        """
        words = list(words)
        # Everything after the first `--` belongs to the agent, options
        # included, so it never reaches the parser.
        if "--" in words:
            split = words.index("--")
            words, args = words[:split], words[split + 1 :]
        else:
            args = []
        parser = argparse.ArgumentParser(
            prog=prog,
            usage="%(prog)s [-h] [PATH] [-- AGENT_ARGS...]",
            description=sys.modules["__main__"].__doc__,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        parser.add_argument(
            "path",
            nargs="?",
            metavar="PATH",
            help="the directory the agent works on, mounted read-write at the same path",
        )
        path: str | None = parser.parse_args(words).path
        if path is None:
            return cls(args=tuple(args))
        workspace = Path(path).expanduser().resolve()
        if not workspace.is_dir():
            parser.error(f"workspace {path}: no such directory")
        return cls(workspace=str(workspace), args=tuple(args))
