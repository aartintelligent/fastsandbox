"""Commands run in a sandbox: specifications, outputs and states."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel

from ..exceptions import CommandFailedError
from ._base import Model

__all__ = [
    "AgentSessionSpec",
    "AttachOutput",
    "AttachSpec",
    "ExecInspect",
    "ExecOutput",
    "ExecSpec",
    "OutputChunk",
    "TerminalSize",
]


class TerminalSize(Model):
    """Terminal dimensions, in characters.

    Attributes:
        height: Number of rows.
        width: Number of columns.
    """

    height: int
    width: int


class ExecSpec(Model):
    """A command to run to completion inside a sandbox.

    Attributes:
        cmd: Program and arguments, not interpreted by a shell.
        user: User name or UID (`"0"` for root); the kit's user by default.
        working_dir: Working directory; the kit's by default.
        env: Additional environment variables.
    """

    cmd: list[str]
    user: str | None = None
    working_dir: str | None = None
    env: dict[str, str] = {}

    @classmethod
    def shell(cls, script: str, **fields: Any) -> ExecSpec:
        """A shell script, run with `sh -c`."""
        return cls(cmd=["sh", "-c", script], **fields)


class AttachSpec(Model):
    """An interactive command.

    Attributes:
        cmd: Program and arguments, not interpreted by a shell.
        user: User name or UID (`"0"` for root).
        working_dir: Working directory.
        env: Additional environment variables.
        tty: Allocates a pseudo-terminal; the output is then a single stream.
        terminal_size: Initial terminal size, when `tty` is set.
    """

    cmd: list[str]
    user: str | None = None
    working_dir: str | None = None
    env: dict[str, str] = {}
    tty: bool = False
    terminal_size: TerminalSize | None = None

    @classmethod
    def shell(cls, script: str, **fields: Any) -> AttachSpec:
        """A shell script, run with `sh -c`."""
        return cls(cmd=["sh", "-c", script], **fields)


class AgentSessionSpec(Model):
    """A session with the agent of the sandbox kit.

    Attributes:
        args: Arguments of the agent, as `sbx run AGENT -- ARGS` passes them.
        tty: Allocates a pseudo-terminal; agents generally expect one.
        terminal_size: Initial terminal size, when `tty` is set.
        working_dir: Working directory; the sandbox's by default.
        env: Additional environment variables.
        ssh_agent_socket_path: Host SSH agent socket to forward.
    """

    args: list[str] = []
    tty: bool = False
    terminal_size: TerminalSize | None = None
    working_dir: str | None = None
    env: dict[str, str] = {}
    ssh_agent_socket_path: str | None = None


class ExecOutput(Model):
    """Result of a command run to completion.

    Attributes:
        exit_code: Exit code of the process.
        stdout: Standard output.
        stderr: Standard error.
    """

    exit_code: int
    stdout: str = ""
    stderr: str = ""

    @property
    def ok(self) -> bool:
        """Whether the command exited with code 0."""
        return self.exit_code == 0

    def check(self) -> ExecOutput:
        """The output itself, or `CommandFailedError` on a non-zero exit code."""
        if not self.ok:
            tail = (self.stderr or self.stdout).strip().splitlines()[-5:]
            raise CommandFailedError(
                f"command exited with code {self.exit_code}: " + " / ".join(tail),
                exit_code=self.exit_code,
                stdout=self.stdout,
                stderr=self.stderr,
            )
        return self


class ExecInspect(Model):
    """State of an execution.

    Attributes:
        id: Execution identifier.
        running: Whether the process is still running.
        exit_code: Exit code, once the process has exited.
    """

    id: str
    running: bool
    exit_code: int | None = None


class OutputChunk(BaseModel):
    """A chunk of the output of an interactive session.

    Attributes:
        stream: `stdout` or `stderr`; a TTY session writes everything to
            `stdout`.
        data: The bytes.
    """

    stream: Literal["stdout", "stderr", "other"]
    data: bytes

    @property
    def text(self) -> str:
        """The bytes decoded as UTF-8, invalid sequences replaced."""
        return self.data.decode(errors="replace")


class AttachOutput(BaseModel):
    """Everything an interactive session wrote, collected until its exit.

    Attributes:
        exit_code: Exit code of the process.
        stdout: Standard output.
        stderr: Standard error.
    """

    exit_code: int
    stdout: bytes = b""
    stderr: bytes = b""

    @property
    def ok(self) -> bool:
        """Whether the command exited with code 0."""
        return self.exit_code == 0
