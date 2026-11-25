"""The coding agents `sbx` knows, and how a task runs them.

The socket never reads the secrets stored with `sbx secret`: a program pushes
the credentials of a sandbox itself. An agent's credentials are read from
environment variables and pushed as sandbox-scoped service secrets, which the
proxy of the sandbox injects into outgoing requests; the sandbox only sees a
placeholder, and the secret goes away with the sandbox.

The headless commands come from the documentation of each agent; the program
and its run options come from the kit itself (`KitAgent.command`).
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
from collections.abc import AsyncIterator, Callable, Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict

from .exceptions import SandboxTimeoutError, TaskError
from .models import AttachSpec
from .utils import parse_timeout

if TYPE_CHECKING:
    from datetime import timedelta

    from .kits import KitAgent
    from .sandbox import Sandbox
    from .sessions import Interactive

__all__ = ["AGENTS", "AgentProfile", "AgentRun", "AgentRunner", "Credential", "agent_profile"]


@dataclass(frozen=True)
class Credential:
    """A credential an agent can use.

    Attributes:
        service: Service known to `sbx`, as listed by `sbx secret set --help`.
        env: Environment variables holding the value, in order of preference.
    """

    service: str
    env: tuple[str, ...]

    def from_env(self) -> str | None:
        """The first non-empty value of `env`, if any."""
        for name in self.env:
            if value := os.environ.get(name):
                return value
        return None


Headless = Callable[["KitAgent", str], list[str]]
"""Builds the command that runs an agent on one prompt, without a terminal."""


def _program(agent: KitAgent, default: str) -> str:
    """The program of the agent, as its kit names it."""
    return agent.binary or default


@dataclass(frozen=True)
class AgentProfile:
    """How to run one agent unattended.

    Attributes:
        name: Kit of the agent, as accepted by `sbx create`.
        credentials: Credentials it can use; each one set in the environment is
            pushed, from the first of its variables that is set.
        forwarded_env: Variables given as they are to the agent process when
            set, for an agent `sbx` knows no service secret for; their values
            are visible inside the sandbox.
        headless: The command of one non-interactive run on a prompt.
        output: What that run writes: JSON lines or plain text.
    """

    name: str
    credentials: tuple[Credential, ...]
    headless: Headless
    output: Literal["jsonl", "text"] = "text"
    forwarded_env: tuple[str, ...] = field(default=())

    def found_credentials(self) -> list[tuple[str, str]]:
        """The credentials found in the environment, as `(service, value)`."""
        found = []
        for credential in self.credentials:
            if (value := credential.from_env()) is not None:
                found.append((credential.service, value))
        return found

    def forwarded_values(self) -> dict[str, str]:
        """The variables of `forwarded_env` set in the environment."""
        return {name: value for name in self.forwarded_env if (value := os.environ.get(name))}


_PROVIDERS = (
    Credential("anthropic", ("ANTHROPIC_API_KEY",)),
    Credential("openai", ("OPENAI_API_KEY",)),
    Credential("google", ("GEMINI_API_KEY", "GOOGLE_API_KEY")),
    Credential("openrouter", ("OPENROUTER_API_KEY",)),
    Credential("groq", ("GROQ_API_KEY",)),
    Credential("mistral", ("MISTRAL_API_KEY",)),
    Credential("nebius", ("NEBIUS_API_KEY",)),
    Credential("xai", ("XAI_API_KEY",)),
)


AGENTS: dict[str, AgentProfile] = {
    profile.name: profile
    for profile in (
        AgentProfile(
            name="claude",
            credentials=(Credential("anthropic", ("ANTHROPIC_API_KEY",)),),
            # `-p` runs one prompt and exits; `stream-json` reports every step.
            headless=lambda a, p: a.command("-p", p, "--output-format", "stream-json", "--verbose"),
            output="jsonl",
        ),
        AgentProfile(
            name="codex",
            credentials=(Credential("openai", ("OPENAI_API_KEY", "CODEX_API_KEY")),),
            headless=lambda a, p: [
                _program(a, "codex"),
                "exec",
                "--dangerously-bypass-approvals-and-sandbox",
                "--skip-git-repo-check",
                "--json",
                p,
            ],
            output="jsonl",
        ),
        AgentProfile(
            name="copilot",
            credentials=(
                Credential("copilot", ("COPILOT_GITHUB_TOKEN", "GH_TOKEN", "GITHUB_TOKEN")),
            ),
            headless=lambda a, p: a.command("-p", p, "--no-ask-user"),
        ),
        AgentProfile(
            name="cursor",
            credentials=(Credential("cursor", ("CURSOR_API_KEY",)),),
            headless=lambda a, p: a.command("-p", p, "--trust", "--output-format", "stream-json"),
            output="jsonl",
        ),
        AgentProfile(
            name="devin",
            credentials=(Credential("devin", ("DEVIN_API_KEY",)),),
            headless=lambda a, p: a.command("-p", p),
        ),
        AgentProfile(
            name="docker-agent",
            credentials=_PROVIDERS,
            headless=lambda a, p: a.command("--exec", p),
        ),
        AgentProfile(
            name="droid",
            credentials=(Credential("droid", ("FACTORY_API_KEY",)),),
            headless=lambda a, p: [
                _program(a, "droid"),
                "exec",
                "--auto",
                "high",
                "-o",
                "stream-json",
                p,
            ],
            output="jsonl",
        ),
        AgentProfile(
            name="kiro",
            credentials=(),
            headless=lambda a, p: a.command("--no-interactive", p),
            forwarded_env=("KIRO_API_KEY",),
        ),
        AgentProfile(
            name="opencode",
            credentials=_PROVIDERS,
            headless=lambda a, p: [_program(a, "opencode"), "run", "--auto", p],
        ),
    )
}
"""The agents `sbx` knows, by kit name."""


def agent_profile(name: str) -> AgentProfile:
    """The profile of the agent `name`.

    Raises:
        TaskError: When `sbx` knows no such agent.
    """
    try:
        return AGENTS[name]
    except KeyError:
        known = ", ".join(sorted(AGENTS))
        raise TaskError(f"unknown agent {name!r}: expected one of {known}") from None


class AgentRun(BaseModel):
    """The outcome of one unattended agent run.

    Attributes:
        exit_code: Exit code of the agent.
        stdout: What it wrote on its standard output.
        stderr: What it wrote on its standard error.
        events: The JSON lines of `stdout`, for agents that report JSON lines.
    """

    model_config = ConfigDict(frozen=True)

    exit_code: int
    stdout: str = ""
    stderr: str = ""
    events: list[Any] = []

    @property
    def ok(self) -> bool:
        """Whether the agent exited with code 0."""
        return self.exit_code == 0


def _json_lines(text: str) -> list[Any]:
    """The JSON values of the lines of `text`, other lines skipped."""
    events = []
    for line in text.splitlines():
        line = line.strip()
        if line.startswith(("{", "[")):
            with contextlib.suppress(ValueError):
                events.append(json.loads(line))
    return events


class AgentRunner:
    """Runs the agent of the sandbox of a task: one prompt unattended, or an interactive session."""

    def __init__(self, sandbox: Sandbox, profile: AgentProfile, agent: KitAgent) -> None:
        self.sandbox = sandbox
        self.profile = profile
        self.agent = agent

    @property
    def name(self) -> str:
        """The name of the agent, e.g. `claude`."""
        return self.profile.name

    def command(self, prompt: str) -> list[str]:
        """The command that runs the agent unattended on `prompt`."""
        return self.profile.headless(self.agent, prompt)

    async def prompt(
        self,
        prompt: str,
        *,
        timeout: float | str | timedelta | None = None,
        working_dir: str | None = None,
        env: Mapping[str, str] | None = None,
    ) -> AgentRun:
        """Runs the agent once on `prompt`, without a terminal, and waits for it.

        Args:
            prompt: The task for the agent.
            timeout: Deadline of the run.
            working_dir: Working directory; the sandbox's by default.
            env: Additional environment variables.

        Raises:
            SandboxTimeoutError: When the run does not end in time.
        """
        spec = AttachSpec(
            cmd=self.command(prompt),
            working_dir=working_dir,
            env={**self.profile.forwarded_values(), **(env or {})},
        )
        seconds = parse_timeout(timeout)
        session = await self.sandbox.attach(spec)
        try:
            async with asyncio.timeout(seconds):
                output = await session.collect(b"")
        except TimeoutError:
            raise SandboxTimeoutError(
                f"agent {self.name} ran over {seconds}s", operation="agent run", after=seconds
            ) from None
        stdout = output.stdout.decode(errors="replace")
        return AgentRun(
            exit_code=output.exit_code,
            stdout=stdout,
            stderr=output.stderr.decode(errors="replace"),
            events=_json_lines(stdout) if self.profile.output == "jsonl" else [],
        )

    async def stream(self, prompt: str, *, working_dir: str | None = None) -> AsyncIterator[Any]:
        """Runs the agent once on `prompt`, yielding what it reports.

        Parsed JSON lines for agents that report JSON lines, text lines otherwise.
        """
        spec = AttachSpec(
            cmd=self.command(prompt),
            working_dir=working_dir,
            env=self.profile.forwarded_values(),
        )
        session = await self.sandbox.attach(spec)
        buffer = ""
        async for chunk in session:
            if chunk.stream != "stdout":
                continue
            buffer += chunk.text
            *lines, buffer = buffer.split("\n")
            for line in lines:
                yield self._line(line)
        if buffer:
            yield self._line(buffer)

    def _line(self, line: str) -> Any:
        """A line of output, parsed when the agent reports JSON lines."""
        if self.profile.output == "jsonl":
            with contextlib.suppress(ValueError):
                return json.loads(line)
        return line

    async def session(
        self, *args: str, tty: bool = True, size: tuple[int, int] | None = None
    ) -> Interactive:
        """Starts an interactive session with the agent, as `sbx run` does."""
        return await self.sandbox.agent_session(list(args), tty=tty, size=size)
