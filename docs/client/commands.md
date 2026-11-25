# Commands

[`sandbox.exec()`][fastsandbox.Sandbox.exec] runs a command in a sandbox to
completion and returns its outputs and exit code. This page covers how a
command is given, what it returns, its errors and deadlines, and the
executions followed by their identifier. Commands that read standard input or
stream their output are [interactive sessions](interactive.md).

## Running a command

The sandbox must run: commands go inside `async with sandbox.running():` (see
[Sessions](sandboxes.md#sessions)).

```python title="docs_src/client/commands.py" hl_lines="9 11 14-20"
--8<-- "docs_src/client/commands.py"
```

A command is given in one of three ways:

- a **string**, run as a shell script with `sh -c`;
- a **list**, the program and its arguments, not interpreted by a shell;
- an [`ExecSpec`][fastsandbox.models.ExecSpec], the full specification;
  `ExecSpec.shell(script)` builds one from a script.

| Argument | Default | What it sets |
|---|---|---|
| `user` | the user of the kit | a user name or UID; `"0"` for root |
| `working_dir` | the working directory of the kit | where the command runs |
| `env` | none | environment variables added to those of the sandbox |
| `timeout` | the long-operation deadline of the client, 15 min | the deadline of the execution, in seconds |
| `check` | `False` | raises on a non-zero exit code |

## Outputs and exit codes

[`ExecOutput`][fastsandbox.models.ExecOutput] holds the `exit_code`, `stdout`
and `stderr` of the command, as strings, and
[`ok`][fastsandbox.models.ExecOutput.ok], whether it exited with 0.

A non-zero exit code is an output, not an error: the command ran. A program
that does not exist is not an error either: it exits with code 127. `check=True`, or [`output.check()`][fastsandbox.models.ExecOutput.check]
afterwards, turns a non-zero exit code into a
[`CommandFailedError`][fastsandbox.exceptions.CommandFailedError], which keeps
`exit_code`, `stdout` and `stderr`; its message ends with the last lines of
the standard error, or of the standard output when the error is empty.

The errors of the call itself are those of the daemon:

| Exception | When |
|---|---|
| [`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError] | the command did not end within its deadline |
| [`ConflictError`][fastsandbox.exceptions.ConflictError] | the sandbox is stopped |
| [`InvalidInputError`][fastsandbox.exceptions.InvalidInputError] | the command is empty |
| [`NotFoundError`][fastsandbox.exceptions.NotFoundError] | the sandbox does not exist |

## Standard input

`exec()` sends no standard input. A command that reads it runs as an
interactive session, whose [`collect()`][fastsandbox.Interactive.collect] writes
the input, closes it and gathers everything until the exit:

```python
counted = await (await sandbox.attach(["wc", "-l"])).collect("one\ntwo\nthree\n")
print(counted.stdout.decode())  # bytes, as the command wrote them
```

## Following an execution

An interactive execution has an identifier,
[`Interactive.id`][fastsandbox.Interactive.id], which a program can hand to
another task. [`sandbox.exec_inspect(id)`][fastsandbox.Sandbox.exec_inspect]
gives its state, an [`ExecInspect`][fastsandbox.models.ExecInspect]: whether it
still runs, and its exit code once it ended. The daemon forgets an execution
once its end has been reported: `exec_inspect()` then raises
[`NotFoundError`][fastsandbox.exceptions.NotFoundError].

```python
session = await sandbox.attach("sleep 1; exit 3")
state = await sandbox.exec_inspect(session.id)  # running
code = await session.wait()  # 3
```

## The agent of the kit

[`sandbox.agent_session()`][fastsandbox.Sandbox.agent_session] starts the agent
of the sandbox kit, with arguments as `sbx run AGENT -- ARGS` passes them:
`bash` for the `shell` kit, a coding agent for the others. Without a terminal
(`tty=False`, the default), its standard output and error come apart, as an
unattended run needs them:

```python
agent = await sandbox.agent_session(["-c", "echo out; echo err >&2"])
output = await agent.collect()
```

It returns an [interactive session](interactive.md). To run a coding agent on a
task, with its credentials and network rules, see
[Agents](../framework/agents.md).
