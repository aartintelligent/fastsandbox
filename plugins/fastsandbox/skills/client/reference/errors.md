# Errors

Full page: https://aartintelligent.github.io/fastsandbox/client/errors/

Every error of the daemon, the library and the framework derives from
`SandboxError`, in `fastsandbox.exceptions`. The most used are also exported
by `fastsandbox`: `SandboxError`, `ApiError`, `NotFoundError`, `ConflictError`,
`DaemonUnavailableError`, `SandboxTimeoutError`, `CommandFailedError`,
`TaskError`. The extension builds them by class name, so they are caught
without importing it.

## API

Every error has `message`, `operation` (e.g. `"sandbox start"`, when known)
and `transient` (whether the same call may succeed later).

| Exception | Base | Raised when | Attributes |
|---|---|---|---|
| `SandboxError` | `Exception` | base of all | `message`, `operation`, `transient` |
| `DaemonUnavailableError` | `SandboxError`, `ConnectionError` | no socket, refused or broken connection | `path` |
| `SandboxTimeoutError` | `SandboxError`, `TimeoutError` | no outcome within the deadline | `after` |
| `ApiError` | `SandboxError` | the daemon answered with an error status | `status`, `code`, `detail` |
| `NotFoundError` | `ApiError` | 404: sandbox, image, rule, execution, MCP server | as `ApiError` |
| `ConflictError` | `ApiError` | 409: name in use, sandbox stopped, host port taken | as `ApiError` |
| `InvalidInputError` | `ApiError` | 400: request rejected as invalid | as `ApiError` |
| `OperationFailedError` | `SandboxError` | a failure inside a successful answer: a rule change, a pull | |
| `ProtocolError` | `SandboxError` | an answer could not be decoded | |
| `UnsupportedVersionError` | `SandboxError` | daemon API outside `SUPPORTED_API` with `version_policy="strict"` | `found`, `supported` |
| `InvalidRequestError` | `SandboxError`, `ValueError` | a request rejected before being sent | |
| `HostFileError` | `SandboxError`, `OSError` | a host file or directory cannot be accessed | `path` |
| `ArchiveError` | `SandboxError` | a tar archive cannot be built or extracted | |
| `CommandFailedError` | `SandboxError` | a checked command exited non-zero | `exit_code`, `stdout`, `stderr` |
| `KitPackageError` | `SandboxError` | a kit package directory is missing or invalid | `path` |
| `KitCompileError` | `SandboxError` | the `sbx` CLI could not compile a kit | |
| `TaskError` | `SandboxError` | a FastSandbox task failed or is misdeclared | |

`code` is the daemon's machine-readable code when it gives one, e.g.
`desired_port_not_found`.

### Retrying

`transient` is set for an unreachable daemon, an expired deadline, a 5xx
answer, and a conflict (the state may change). A command sent to a stopped
sandbox succeeds once it runs; a name in use stays in use until its sandbox is
deleted: retrying is the program's decision. A few invalid inputs come back as
500 and never succeed on retry: an upload into a missing directory, an image
archive the daemon cannot load.

Outside the hierarchy: a stream or interactive session used after it was
closed raises `RuntimeError`; `client.create()` with neither kit nor request
raises `ValueError`.

## Example

```python
import asyncio

import fastsandbox
from fastsandbox.exceptions import ConflictError, NotFoundError, SandboxError


async def inspect_with_retry(client: fastsandbox.Client, name: str, attempts: int = 3) -> None:
    for attempt in range(attempts):
        try:
            info = await client.sandbox(name).inspect()
            print(info.status)
            return
        except NotFoundError as error:
            print(f"no sandbox {name}: HTTP {error.status} during {error.operation}")
            return
        except SandboxError as error:
            if not error.transient or attempt == attempts - 1:
                raise
            await asyncio.sleep(2**attempt)


async def main() -> None:
    client = await fastsandbox.connect()
    await inspect_with_retry(client, "no-such-sandbox")
    async with client.create("taken-name", kit="shell"):
        try:
            await client.create("taken-name", kit="shell")
        except ConflictError as error:
            print(f"conflict: HTTP {error.status}, code {error.code}")


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- A non-zero exit code is not an error unless the command is checked
  (`check=True` or `output.check()`).
- Catch the most specific class first: `NotFoundError` and `ConflictError`
  are `ApiError`s, which are `SandboxError`s.
- Generic handlers keep working: `except ConnectionError`, `TimeoutError`,
  `ValueError` and `OSError` catch the matching classes.
- A creation stream reports a failure as a `CreateFailure` item, not an
  exception.
