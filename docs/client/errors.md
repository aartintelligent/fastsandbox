# Errors

Every error of the daemon, of the library and of the framework derives from
[`SandboxError`][fastsandbox.exceptions.SandboxError], with one class per kind
of failure and typed attributes, so that a program tells them apart without
reading messages. This page covers the hierarchy, the attributes, and which
errors are worth a retry.

```python title="docs_src/client/errors.py" hl_lines="9 15"
--8<-- "docs_src/client/errors.py"
```

The errors are in [`fastsandbox.exceptions`](../reference/exceptions.md); the
most used are also exported by `fastsandbox` itself: `SandboxError`,
`ApiError`, `NotFoundError`, `ConflictError`, `DaemonUnavailableError`,
`SandboxTimeoutError`, `CommandFailedError` and `TaskError`.

## The hierarchy

Every error has a `message`, the `operation` that failed when it is known
(`sandbox start`, `sandbox inspection`…), and `transient`. Some also derive
from the built-in exception that matches, so that generic handlers keep
working.

| Exception | Raised when | Attributes |
|---|---|---|
| [`SandboxError`][fastsandbox.exceptions.SandboxError] | the base of all | `message`, `operation`, `transient` |
| [`DaemonUnavailableError`][fastsandbox.exceptions.DaemonUnavailableError] (`ConnectionError`) | the daemon cannot be reached: no socket, a refused or broken connection | `path` |
| [`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError] (`TimeoutError`) | an operation got no outcome within its deadline | `after` |
| [`ApiError`][fastsandbox.exceptions.ApiError] | the daemon answered with an error status | `status`, `code`, `detail` |
| [`NotFoundError`][fastsandbox.exceptions.NotFoundError] | 404: the sandbox, image, rule or execution does not exist | as `ApiError` |
| [`ConflictError`][fastsandbox.exceptions.ConflictError] | 409: the request conflicts with the current state, a name in use or a stopped sandbox | as `ApiError` |
| [`InvalidInputError`][fastsandbox.exceptions.InvalidInputError] | 400: the daemon rejected the request as invalid | as `ApiError` |
| [`OperationFailedError`][fastsandbox.exceptions.OperationFailedError] | the daemon reported a failure inside a successful answer: a rule change, an image pull | |
| [`ProtocolError`][fastsandbox.exceptions.ProtocolError] | an answer of the daemon could not be decoded | |
| [`UnsupportedVersionError`][fastsandbox.exceptions.UnsupportedVersionError] | the API version of the daemon is outside the supported range (see [The API version](index.md#the-api-version)) | `found`, `supported` |
| [`InvalidRequestError`][fastsandbox.exceptions.InvalidRequestError] (`ValueError`) | a request was rejected before being sent | |
| [`HostFileError`][fastsandbox.exceptions.HostFileError] (`OSError`) | a file or directory of the host could not be accessed | `path` |
| [`ArchiveError`][fastsandbox.exceptions.ArchiveError] | a tar archive could not be built or extracted | |
| [`CommandFailedError`][fastsandbox.exceptions.CommandFailedError] | a checked command exited with a non-zero code (see [Commands](commands.md)) | `exit_code`, `stdout`, `stderr` |
| [`KitPackageError`][fastsandbox.exceptions.KitPackageError] | a kit package directory is missing or invalid | `path` |
| [`KitCompileError`][fastsandbox.exceptions.KitCompileError] | the `sbx` CLI could not compile a kit | |
| [`TaskError`][fastsandbox.exceptions.TaskError] | a task of a FastSandbox application failed or is misdeclared | |

`NotFoundError`, `ConflictError` and `InvalidInputError` derive from
`ApiError`; every other class derives from `SandboxError` directly. `code` is
the machine-readable code of the daemon, when it gives one, such as
`desired_port_not_found`.

## Retrying

[`transient`][fastsandbox.exceptions.SandboxError] says whether the same call
may succeed later: it is set for a daemon that could not be reached, a
deadline that expired, an answer of the daemon with a 5xx status, and a
conflict, since the state the request conflicts with may change. A command
sent to a stopped sandbox succeeds once the sandbox runs; a name in use stays
in use until its sandbox is deleted, so a retry is the program's decision.

The daemon also answers a few invalid inputs with a server error, which a
retry does not fix: an upload into a directory that does not exist, an image
archive it cannot load.

## Outside the hierarchy

A stream or an interactive session used after it was closed raises a
`RuntimeError`; `client.create()` with neither a kit nor a request raises a
`ValueError`.
