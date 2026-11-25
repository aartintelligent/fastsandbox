# Interactive sessions

Full page: https://aartintelligent.github.io/fastsandbox/client/interactive/

An interactive session is a command whose standard input the program writes
and whose output it reads as it comes: a filter, a server, a shell in a
terminal, the agent of the kit.

## API

```text
await Sandbox.attach(
    command: Command | AttachSpec,     # str runs with sh -c, a list is the argv
    *,
    tty: bool = False,
    size: tuple[int, int] | None = None,   # (width, height) of the terminal
    user: str | None = None,
    working_dir: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Interactive

await Sandbox.agent_session(
    args: Sequence[str] | AgentSessionSpec = (),  # as `sbx run AGENT -- ARGS` passes them
    *,
    tty: bool = False,
    size: tuple[int, int] | None = None,
    working_dir: str | None = None,
    env: Mapping[str, str] | None = None,
) -> Interactive
```

`AttachSpec(cmd, user=None, working_dir=None, env={}, tty=False,
terminal_size=None)` (`AttachSpec.shell(script, **fields)`) and
`AgentSessionSpec(args=[], tty=False, terminal_size=None, working_dir=None,
env={}, ssh_agent_socket_path=None)` are the full specifications;
`TerminalSize(height, width)` is their terminal size.

### `Interactive`

| Member | What it does |
|---|---|
| `id: str` | the execution id, for `sandbox.exec_inspect(id)` |
| `await write(data: bytes \| str)` | writes to standard input (UTF-8 for a string) |
| `await close_stdin()` | the command reads end of file |
| `async for chunk in session` | `OutputChunk`: `stream` (`"stdout"`, `"stderr"`, `"other"`), `data: bytes`, `text` (decoded, invalid sequences replaced) |
| `await resize(width, height)` | resizes the terminal of a TTY session |
| `await inspect() -> ExecInspect` | `id`, `running`, `exit_code` |
| `await wait(timeout=60.0) -> int` | the exit code |
| `await collect(stdin=b"", exit_timeout=10.0) -> AttachOutput` | writes `stdin`, closes it, gathers everything until the exit: `exit_code`, `stdout: bytes`, `stderr: bytes`, `ok`; only before reading chunk by chunk |
| `async with session:` | closes standard input on exit |

## Example

```python
import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        upper = await sandbox.attach(["tr", "a-z", "A-Z"])
        output = await upper.collect("piped through the sandbox\n")
        print(output.stdout.decode(), end="")

        greeter = await sandbox.attach("read name; echo hello $name")
        await greeter.write("sandbox\n")
        await greeter.close_stdin()
        async for chunk in greeter:
            print(chunk.text, end="")

        shell = await sandbox.attach(["bash", "-l"], tty=True, size=(120, 40))
        await shell.write("ls\n")
        await shell.resize(160, 50)
        await shell.write(b"\x04")  # Ctrl-D ends the shell
        print(await shell.wait())


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- A terminal (`tty=True`) merges the output into one stream, `stdout`, and
  closing its standard input does not end the program: write `exit` or
  Ctrl-D (`b"\x04"`).
- `collect()` is all or nothing: do not mix it with `async for`.
- A session or stream used after it was closed raises `RuntimeError`.
- A server started with `attach()` keeps running until it exits or the
  sandbox goes; `exec()` would wait for its end.
- `agent_session()`: interactive agents expect `tty=True`; without a terminal
  an unattended run gets stdout and stderr apart. For coding agents run as
  tasks (credentials, network rules), load the agents skill.
- The fake daemon answers `attach()` and `agent_session()` with 501: test this
  code against the real daemon.
