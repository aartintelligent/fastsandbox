# Agents

[`@app.agent`][fastsandbox.FastSandbox.agent] declares a task whose sandbox
runs a coding agent: its sandbox comes from the kit of the agent, the
credentials of the agent found in the environment are given to that sandbox
only, the hosts the agent needs are allowed along with the network rules of
the task, and the task drives the agent through `ctx.agent`. This page covers
the declaration, the agents there are, their credentials, and the three ways to
run an agent from a task.

!!! tip "In a hurry?"
    The [quickstart](../get-started/quickstart.md) runs an agent in five
    minutes, and the [Agent sandboxes](../agents/repository.md) pages answer
    the questions of a real setup, one page each: its repository, its network,
    following its work, its tools, several agents at once.

## An agent task

```python title="docs_src/agents/fix_bug.py" hl_lines="16 24 26"
--8<-- "docs_src/agents/fix_bug.py"
```

- `@app.agent("claude", ...)` takes the agent first, then the options of
  [`@app.task`][fastsandbox.FastSandbox.task] (see [Tasks](tasks.md)), with the
  kit of the agent as the default kit, and `allow_agent_hosts` (see
  [The network of an agent](#the-network-of-an-agent)). It is always called:
  `@app.agent("claude")`, never bare.
- [`ctx.agent.prompt(...)`][fastsandbox.AgentRunner.prompt] runs the agent once
  on a prompt, without a terminal, and waits for it to end.
- The task then checks the work itself, with the tests of the project: what the
  agent reports is not a result.

Run it as any task, here on the current directory:

```sh
export ANTHROPIC_API_KEY=...
fastsandbox run docs_src/agents/fix_bug.py fix_bug --repo . --issue "the parser drops the last line"
```

## The agents

The agents are those `sbx` knows, by the name of their kit; another name raises
[`TaskError`][fastsandbox.exceptions.TaskError] when the task is declared. Their
profiles are in [`fastsandbox.AGENTS`][fastsandbox.AGENTS].

| Agent | Credentials read from the environment | Output of an unattended run |
|---|---|---|
| `claude` | `ANTHROPIC_API_KEY` | JSON lines |
| `codex` | `OPENAI_API_KEY`, else `CODEX_API_KEY` | JSON lines |
| `copilot` | `COPILOT_GITHUB_TOKEN`, else `GH_TOKEN`, else `GITHUB_TOKEN` | Text |
| `cursor` | `CURSOR_API_KEY` | JSON lines |
| `devin` | `DEVIN_API_KEY` | Text |
| `docker-agent` | The keys of the model providers, below | Text |
| `droid` | `FACTORY_API_KEY` | JSON lines |
| `kiro` | None: `KIRO_API_KEY` is given to the agent process | Text |
| `opencode` | The keys of the model providers, below | Text |

The keys of the model providers, each pushed when it is set, are
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` (else
`GOOGLE_API_KEY`), `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`,
`NEBIUS_API_KEY` and `XAI_API_KEY`.

## Credentials

The socket of the daemon never reads the secrets stored with `sbx secret set`:
the credentials of a sandbox are pushed to it. Before the task runs, each
credential of the agent found in the environment of the calling process is
pushed as a service secret of the sandbox of the run, and of that sandbox only:

- The proxy of the sandbox injects the secret into the requests to its service;
  the sandbox itself, and the agent, only see a placeholder.
- The secret goes with the sandbox when the run ends.
- When none is set, nothing is pushed, and the credential the daemon holds
  for the kit of the agent applies, a subscription or a secret stored with
  `sbx secret set` for instance, as it does to every sandbox of that kit.
- The daemon gives the credential a kit declares only when it authorizes it,
  as it does for the kits forged by fastsandbox or compiled by the CLI; one it
  withholds gets nothing from the proxy, a secret just pushed included (see
  [Withheld credentials](../client/credentials.md#withheld-credentials)).

`kiro` has no service secret in `sbx`: `KIRO_API_KEY`, when set, is passed as
an environment variable to the agent process that `prompt` and `stream` start,
and its value is visible inside the sandbox.

## The network of an agent

An agent needs to reach its own service. When a task gives `network`, the hosts
its kit declares for the agent are allowed ahead of those rules, so that a
narrow policy does not cut the agent off; `allow_agent_hosts=False` applies the
rules of `network` alone. Without `network`, no rule is applied, and what the
agent reaches is what the policy of the daemon allows (see
[Network rules](network.md)).

## Running the agent

The task reaches the agent through [`ctx.agent`][fastsandbox.Context.agent], an
[`AgentRunner`][fastsandbox.AgentRunner]; a parameter annotated
`AgentRunner` receives the same object. In a task declared with `@app.task`,
`ctx.agent` raises `TaskError`.

### One prompt, unattended

[`prompt(prompt, *, timeout, working_dir, env)`][fastsandbox.AgentRunner.prompt]
runs the agent on one prompt, with the command its profile gives for an
unattended run, and returns an [`AgentRun`][fastsandbox.AgentRun]:

- `exit_code`, and `ok` when it is 0;
- `stdout` and `stderr`, as text;
- `events`, the JSON lines of `stdout` parsed, for the agents whose output is
  JSON lines.

`timeout` bounds the run of the agent and raises
[`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError] when it is
over; `working_dir` defaults to the working directory of the sandbox.

The command is the program and the run options the kit declares, followed by
the arguments of the profile. [`command(prompt)`][fastsandbox.AgentRunner.command]
returns it without running it:

```python title="docs_src/agents/agent_command.py"
--8<-- "docs_src/agents/agent_command.py"
```

For `claude`, it is `claude --dangerously-skip-permissions -p <prompt>
--output-format stream-json --verbose`: the run options of the kit let the agent
edit files and run commands without asking, which the sandbox makes safe.

### Following what it does

[`stream(prompt, *, working_dir)`][fastsandbox.AgentRunner.stream] runs the
same command and yields what the agent writes on its standard output as it
comes, a line at a time: parsed JSON values for the agents whose output is JSON
lines, text lines otherwise. Unlike `prompt`, it has no `timeout` of its own,
since the timeout of the task bounds it, and no `env`: the agent process gets
the variables its profile forwards, as with `prompt`.

```python title="docs_src/agents/review_stream.py" hl_lines="14-19"
--8<-- "docs_src/agents/review_stream.py"
```

The events are those of the agent; the stream of Claude Code ends with an event
of type `result`, which holds its final answer.

### An interactive session

[`session(*args, tty=True, size=None)`][fastsandbox.AgentRunner.session] starts
the agent as `sbx run` does, in an interactive session: an
[`Interactive`][fastsandbox.Interactive] to write to and read from, for a
program that relays a terminal or drives the agent itself. `args` are passed
to the agent, as after `sbx run AGENT --`. See
[Interactive sessions](../client/interactive.md).

## Choosing the kit

The kit of an agent task is the kit of the agent. `kit=` replaces it with a
composition of that kit, for instance with kit arguments, which select what
the kit declares, such as the model of `claude`:

```python
@app.agent("claude", kit=Kit(base="claude", args={"model": "claude-haiku-5-5"}))
```

Each composition is forged once and kept apart (see
[Kits](../client/kits.md)). The kit must describe an agent: one that does not
makes the run raise `TaskError`.
