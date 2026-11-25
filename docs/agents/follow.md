# Follow its work

An unattended agent can run for many minutes. This page shows four ways to see
what it does: its events as they come, progress reported to the caller, the
logs of the task, and the sandbox kept after the run to look inside.

## Stream its events

[`ctx.agent.stream(prompt)`][fastsandbox.AgentRunner.stream] runs the agent as
`prompt` does, and yields what it reports as it goes:

```python title="docs_src/agents/follow_progress.py" linenums="1" hl_lines="15 18-22"
--8<-- "docs_src/agents/follow_progress.py"
```

- **Line 15**: each item is a line of the output of the agent, parsed as JSON
  for the agents that report JSON lines (`claude`, `codex`, `cursor`, `droid`),
  a text line for the others.
- **Lines 18 to 22**: Claude Code reports an `assistant` event for each step it
  takes, and ends with a `result` event that holds its final answer. The task
  counts the steps, and keeps the answer as its result.

## Report progress to the caller

**Line 20**: [`ctx.report_progress`][fastsandbox.Context.report_progress] sends
how far the run got to whoever called it. **Lines 26 to 31**: the caller
receives it through `on_progress`, here a function that prints it:

```console
$ python docs_src/agents/follow_progress.py
step 1: the agent took a step
step 2: the agent took a step
...
```

A progress bar, a chat message or a web page take the place of `print` the
same way; the handler may be a plain function or a coroutine function (see
[Running tasks](../framework/running.md#progress)).

## Read the logs

[`ctx.log(message)`][fastsandbox.Context.log] logs through the logger of the
task, `fastsandbox.task.<name>`, with the name of its sandbox. The standard
`logging` module shows them: `logging.basicConfig(level=logging.INFO)` at the
start of the program is enough.

## Look inside after the run

`keep=True` on the decorator keeps the sandbox after the run instead of
deleting it, with what the agent left in it:

- `sbx ls` lists it; the task can log its name, `ctx.sandbox.name`;
- `ssh -o ProxyCommand="fastsandbox ssh-proxy NAME" agent@NAME` opens a shell
  in it, through the socket (see [SSH](../client/ssh.md));
- [`client.sandbox(NAME)`][fastsandbox.Client.sandbox] reaches it from Python.

It stops once nothing holds it running, and it is then yours to delete, with
`sbx` or [`delete()`][fastsandbox.Sandbox.delete]. Keep it for debugging only:
a kept sandbox holds the clone and the work of the agent.

## Talk to it

[`ctx.agent.session()`][fastsandbox.AgentRunner.session] starts the agent in an
interactive session, as `sbx run` does, for a program that relays a terminal
or drives the conversation itself (see
[Interactive sessions](../client/interactive.md)). The `agent-claude` example
of the repository relays one to your terminal:

```sh
just example agent-claude ~/my-project -- "explain this project"
```
