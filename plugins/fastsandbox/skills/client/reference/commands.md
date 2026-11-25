# Commands

Full page: https://aartintelligent.github.io/fastsandbox/client/commands/

## API

```text
await Sandbox.exec(
    command: Command | ExecSpec,
    *,
    user: str | None = None,          # name or UID; "0" for root; the kit's user by default
    working_dir: str | None = None,   # the kit's working directory by default
    env: Mapping[str, str] | None = None,  # added to the sandbox environment
    timeout: float | None = None,     # seconds; the client's long-operation deadline (15 min) by default
    check: bool = False,              # raise CommandFailedError on a non-zero exit code
) -> ExecOutput
```

- `Command`, a type alias of the `types` module of the package
  (`fastsandbox/types.py`), is `str | Sequence[str]`:
  a string runs with `sh -c`, a sequence is the argument vector, not
  interpreted by a shell.
- `ExecSpec(cmd: list[str], user=None, working_dir=None, env={})` is the full
  specification; `ExecSpec.shell(script, **fields)` builds one from a script.
  With an `ExecSpec`, `user`, `working_dir` and `env` of `exec()` are ignored.
- `ExecOutput`: `exit_code: int`, `stdout: str`, `stderr: str`, `ok` (exit
  code 0), `check() -> ExecOutput` (returns itself or raises
  `CommandFailedError` with `exit_code`, `stdout`, `stderr`; its message ends
  with the last lines of stderr, else stdout).

| Error | When |
|---|---|
| `SandboxTimeoutError` | the command did not end within its deadline |
| `ConflictError` | the sandbox is stopped (work inside `sandbox.running()`) |
| `InvalidInputError` | the command is empty |
| `NotFoundError` | the sandbox does not exist |
| `CommandFailedError` | `check=True` and a non-zero exit code |

### Executions by identifier

`await sandbox.exec_inspect(exec_id) -> ExecInspect` (`id`, `running`,
`exit_code`) follows an interactive execution by its `Interactive.id`. The
daemon forgets an execution once its end was reported: then `NotFoundError`.

### Standard input and the kit agent

`exec()` sends no standard input. A command that reads it runs with
`sandbox.attach()`, and `collect(stdin)` feeds it; the agent of the kit runs
with `sandbox.agent_session()`. Both are in [interactive](interactive.md).

## Example

```python
import fastsandbox
from fastsandbox.exceptions import CommandFailedError
from fastsandbox.models import ExecSpec


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        output = await sandbox.exec("echo hello from $(hostname)")
        print(output.exit_code, output.stdout, end="")

        await sandbox.exec(["mkdir", "-p", "/work"], user="0", check=True)
        await sandbox.exec(
            ExecSpec.shell("make test", working_dir="/work", env={"CI": "1"}), timeout=600
        )

        failed = await sandbox.exec("exit 3")
        print(failed.ok, failed.exit_code)  # False 3: an output, not an error
        try:
            await sandbox.exec("exit 3", check=True)
        except CommandFailedError as error:
            print(error.exit_code, error.stderr)


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- A non-zero exit code is not an error, and a program that does not exist
  exits with 127: use `check=True` when failure must stop the flow.
- Quote arguments with the list form rather than building a shell string from
  untrusted input.
- `timeout` bounds one command; past it, `SandboxTimeoutError` (`after`).
- A long-running server never returns from `exec()`: start it with
  `attach()` (see [ports](ports.md)).
- Root is the UID `"0"`, given as a string.
