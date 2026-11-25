"""The exceptions of fastsandbox.

Every error of the daemon, of the library and of the framework derives from
`SandboxError`. The native extension builds them by class name with the message
of `docker-sandbox` and its details as keyword arguments, so they carry typed
attributes and can be caught without importing the extension.

Some classes also derive from the matching built-in exception
(`ConnectionError`, `TimeoutError`, `ValueError`, `OSError`), so that generic
handlers keep working.
"""

from __future__ import annotations

from typing import Any

__all__ = [
    "ApiError",
    "ArchiveError",
    "CommandFailedError",
    "ConflictError",
    "DaemonUnavailableError",
    "HostFileError",
    "InvalidInputError",
    "InvalidRequestError",
    "KitCompileError",
    "KitPackageError",
    "NotFoundError",
    "OperationFailedError",
    "ProtocolError",
    "SandboxError",
    "SandboxTimeoutError",
    "TaskError",
    "UnsupportedVersionError",
]


class SandboxError(Exception):
    """Base of every fastsandbox error.

    Attributes:
        message: The message of the error.
        operation: The operation that failed, e.g. `sandbox start`, when known.
        transient: Whether retrying the same call may succeed (a timeout, a
            dropped connection, a 5xx answer of the daemon).
    """

    def __init__(
        self,
        message: str,
        *,
        operation: str | None = None,
        transient: bool = False,
        **details: Any,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.operation = operation
        self.transient = transient
        for name, value in details.items():
            setattr(self, name, value)


class DaemonUnavailableError(SandboxError, ConnectionError):
    """The daemon cannot be reached.

    No socket, a refused connection, a broken HTTP exchange or interactive connection.

    Attributes:
        path: The socket path that could not be connected to, when known.

    """

    path: str | None = None


class SandboxTimeoutError(SandboxError, TimeoutError):
    """An operation got no outcome in time.

    Attributes:
        after: How long it waited, in seconds.
    """

    after: float | None = None


class ApiError(SandboxError):
    """The daemon answered with an error status.

    Attributes:
        status: The HTTP status of the answer.
        code: The error code of the daemon, when it gives one.
        detail: The message of the daemon.
    """

    status: int = 0
    code: str | None = None
    detail: str = ""


class NotFoundError(ApiError):
    """The sandbox, image, rule or execution does not exist (HTTP 404)."""


class ConflictError(ApiError):
    """The request conflicts with the current state, e.g. a name already in use (HTTP 409)."""


class InvalidInputError(ApiError):
    """The daemon rejected the request as invalid (HTTP 400)."""


class OperationFailedError(SandboxError):
    """The daemon reported the failure of an operation in a successful answer.

    E.g. in the progress stream of a creation.
    """


class ProtocolError(SandboxError):
    """An answer of the daemon could not be decoded."""


class UnsupportedVersionError(SandboxError):
    """The daemon reports an API version this release was not audited on.

    Attributes:
        found: The version the daemon reports.
        supported: The range this release supports.
    """

    found: str = ""
    supported: str = ""


class InvalidRequestError(SandboxError, ValueError):
    """A request was rejected before being sent."""


class HostFileError(SandboxError, OSError):
    """A file or directory of the host could not be accessed.

    Attributes:
        path: The path on the host.
    """

    path: str | None = None


class ArchiveError(SandboxError):
    """A tar archive could not be built or extracted."""


class CommandFailedError(SandboxError):
    """A command ran to completion with a non-zero exit code.

    Attributes:
        exit_code: The exit code of the command.
        stdout: Its standard output.
        stderr: Its standard error.
    """

    exit_code: int = 0
    stdout: str = ""
    stderr: str = ""


class KitPackageError(SandboxError):
    """A kit package directory is missing or invalid.

    Attributes:
        path: The directory of the package.
    """

    path: str | None = None


class KitCompileError(SandboxError):
    """A kit could not be compiled with the `sbx` CLI."""


class TaskError(SandboxError):
    """A task of a FastSandbox application failed or is misdeclared."""
