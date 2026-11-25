# Interactive sessions

An interactive session is a command whose standard input a program writes and
whose output it reads as it comes: a filter fed with data, a server that runs
until the sandbox goes, a shell in a terminal, the agent of the kit. This page
covers [`sandbox.attach()`][fastsandbox.Sandbox.attach], the
[`Interactive`][fastsandbox.Interactive] session it returns, and terminals.

```python title="docs_src/client/interactive.py"
--8<-- "docs_src/client/interactive.py"
```

The first command gets its whole input at once and is collected to its exit;
the second is written to, then read chunk by chunk.

## Starting a session

`attach()` takes a command as [`exec()`](commands.md#running-a-command) does: a
string run with `sh -c`, a list, or a full
[`AttachSpec`][fastsandbox.models.AttachSpec]; with `user`, `working_dir` and
`env`. The command runs until it exits or the sandbox goes: a server started
with `attach()` keeps serving while the program does other work.

## Input and output

| Call | What it does |
|---|---|
| [`write(data)`][fastsandbox.Interactive.write] | writes a string (as UTF-8) or bytes to the standard input |
| [`close_stdin()`][fastsandbox.Interactive.close_stdin] | closes it: the command reads the end of the file |
| `async for chunk in session` | reads the output as it comes, an [`OutputChunk`][fastsandbox.models.OutputChunk] at a time |
| [`wait(timeout=60.0)`][fastsandbox.Interactive.wait] | waits for the exit code |
| [`inspect()`][fastsandbox.Interactive.inspect] | the state of the execution |
| [`collect(stdin=b"", exit_timeout=10.0)`][fastsandbox.Interactive.collect] | writes `stdin`, closes it, and gathers everything until the exit |

An [`OutputChunk`][fastsandbox.models.OutputChunk] has the `stream` it comes
from, `stdout` or `stderr`, and its `data` as bytes;
[`text`][fastsandbox.models.OutputChunk.text] decodes it, replacing invalid
sequences. [`collect()`][fastsandbox.Interactive.collect] returns an
[`AttachOutput`][fastsandbox.models.AttachOutput], whose `stdout` and `stderr`
are bytes; it is only possible before the session is read chunk by chunk.

Used as an async context manager, a session closes its standard input on the
way out.

## Terminals

`tty=True` gives the command a pseudo-terminal, of `size=(width, height)`
characters; [`resize(width, height)`][fastsandbox.Interactive.resize] changes
it, as a window does. A terminal merges the output into one stream, `stdout`.

```python
shell = await sandbox.attach(["bash", "-l"], tty=True, size=(120, 40))
await shell.write("ls\n")
await shell.resize(160, 50)
```

!!! note "Ending a terminal session"
    Closing the standard input of a terminal session does not end the
    program in it, as closing a terminal would not: type what a user would,
    `exit` or Ctrl-D (`await shell.write(b"\x04")`).

The `shell-interactive` example relays a terminal session to the local
terminal, keys, output and window size included (see [Examples](../guides/examples.md)).

## The agent of the kit

[`sandbox.agent_session()`][fastsandbox.Sandbox.agent_session] starts the agent
of the sandbox kit in a session, with its arguments as `sbx run AGENT -- ARGS`
passes them, or a full [`AgentSessionSpec`][fastsandbox.models.AgentSessionSpec].
Interactive agents expect a terminal (`tty=True`); without one, an unattended
run gets its standard output and error apart. To run coding agents on tasks,
see [Agents](../framework/agents.md).

!!! info "Testing"
    Interactive sessions upgrade their connection to the daemon, which the
    fake daemon of [`fastsandbox.testing`](../guides/testing.md) does not do: code
    that uses them is tested against the real daemon.
