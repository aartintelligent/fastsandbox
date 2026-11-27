# The agents and how a task runs them

Full page: https://aartintelligent.github.io/fastsandbox/framework/agents/

`@app.agent("<kit>")` declares a task whose sandbox runs a coding agent. The
agents are those `sbx` knows, by the name of their kit; their profiles are in
`fastsandbox.AGENTS`, a `dict[str, AgentProfile]` keyed by kit name.

## The agents

| Kit | Agent | Credentials read from the environment (first set wins within a row) | Unattended output |
|---|---|---|---|
| `claude` | Claude Code | `ANTHROPIC_API_KEY` | JSON lines |
| `codex` | Codex | `OPENAI_API_KEY`, else `CODEX_API_KEY` | JSON lines |
| `copilot` | GitHub Copilot | `COPILOT_GITHUB_TOKEN`, else `GH_TOKEN`, else `GITHUB_TOKEN` | Text |
| `cursor` | Cursor | `CURSOR_API_KEY` | JSON lines |
| `devin` | Devin | `DEVIN_API_KEY` | Text |
| `docker-agent` | Docker Agent | The model provider keys, below | Text |
| `droid` | Droid | `FACTORY_API_KEY` | JSON lines |
| `kiro` | Kiro | None pushed; `KIRO_API_KEY` is forwarded to the agent process | Text |
| `opencode` | OpenCode | The model provider keys, below | Text |

Model provider keys (`docker-agent`, `opencode`), each pushed when set:
`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` (else
`GOOGLE_API_KEY`), `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`,
`NEBIUS_API_KEY`, `XAI_API_KEY`.

Every credential found is pushed, before the task runs, as a service secret of
the run's sandbox only: the proxy injects it into the requests to that
service, the agent sees a placeholder, and it goes with the sandbox. Nothing
set: nothing pushed, and a secret stored with `sbx secret set` applies.
`kiro`'s `KIRO_API_KEY` is passed as an environment variable to the agent
process that `prompt` and `stream` start: its value is visible in the sandbox.

## API

```text
FastSandbox.agent(agent, *, name=None, kit=None, network=None,
                  allow_agent_hosts=True, timeout=None, env=None, cpus=None,
                  memory=None, keep=False, description=None,
                  max_concurrency=None)
```

- `agent`: the kit name of the agent; another name raises `TaskError` at
  declaration.
- `kit`: a `Kit` or a kit name; `Kit(base=agent)` by default. It must describe
  an agent, or the run raises `TaskError`.
- `allow_agent_hosts`: when `network` is given, the hosts the kit declares for
  the agent are allowed ahead of the task's rules.

`ctx.agent` is an `AgentRunner` (a parameter annotated `AgentRunner` receives
the same object). In a task declared with `@app.task`, `ctx.agent` raises
`TaskError`.

| `AgentRunner` member | What it does |
|---|---|
| `name` | The kit name of the agent, e.g. `"claude"`. |
| `command(prompt) -> list[str]` | The command an unattended run on `prompt` would run, without running it. |
| `await prompt(prompt, *, timeout=None, working_dir=None, env=None) -> AgentRun` | Runs the agent once, without a terminal, and waits. `timeout` (seconds, `timedelta` or `"15m"`) raises `SandboxTimeoutError`; `working_dir` defaults to the sandbox's; `env` adds variables. |
| `async for item in stream(prompt, *, working_dir=None)` | Same command; yields each line of standard output as it comes, parsed as JSON for JSON-lines agents (a line that is not JSON stays text). No `timeout` argument: bound it with the task's `timeout`. |
| `await session(*args, tty=True, size=None) -> Interactive` | Starts the agent interactively, as `sbx run AGENT -- args` does. |

`AgentRun` (a frozen Pydantic model): `exit_code: int`, `ok` (exit code 0),
`stdout: str`, `stderr: str`, `events: list` (the parsed JSON lines of
`stdout`, for JSON-lines agents; empty otherwise). There is no "final answer"
field: for Claude Code, take the `result` field of the last event of type
`result`, or ask the agent to write a file.

`AgentProfile` (frozen dataclass): `name`, `credentials: tuple[Credential, ...]`,
`headless` (builds the unattended command), `output: "jsonl" | "text"`,
`forwarded_env: tuple[str, ...]`; `found_credentials()` gives the
`(service, value)` pairs set in the environment, `forwarded_values()` the
forwarded variables that are set.

`Credential(service, env)` (frozen dataclass): an `sbx` service name and the
environment variables that may hold its value, in order of preference;
`from_env()` returns the first non-empty one.

The unattended command is the program and the run options the kit declares,
followed by the profile's arguments: `claude -p <prompt> --output-format
stream-json --verbose`, `codex exec --dangerously-bypass-approvals-and-sandbox
--skip-git-repo-check --json <prompt>`, `copilot -p <prompt> --no-ask-user`,
`cursor -p <prompt> --trust --output-format stream-json`, `devin -p <prompt>`,
`docker-agent --exec <prompt>`, `droid exec --auto high -o stream-json
<prompt>`, `kiro --no-interactive <prompt>`, `opencode run --auto <prompt>`
(for `codex`, `droid` and `opencode` the profile builds the whole command after
the program). The kit's run options let the agent edit files and run commands
without asking: the sandbox is what makes that safe.

## Choosing the kit and the model

`kit=Kit(base="claude", args={...})` composes the agent's kit with kit
arguments (`sbx create --kit-arg`), or with `mixins=(...)`: directories, or
`Mixin`s written in Python (see the client skill). The `claude` kit
declares `model` and `reasoningEffort`, whose values the forge checks as the
CLI does (`InvalidKitError`). Each composition is forged once and kept apart
from the plain kit.

## Example

```python
from pathlib import Path
from typing import Annotated

from fastsandbox import Context, FastSandbox, Kit, WorkspaceDir

app = FastSandbox("quickstart")


@app.agent(
    "claude",
    kit=Kit(base="claude", args={"model": "claude-haiku-5-5"}),
    timeout="15m",
)
async def explain(ctx: Context, repo: Annotated[Path, WorkspaceDir(clone=True)]) -> str:
    """Has Claude Code explain a project, working on a private clone of it."""
    workdir = str(repo.resolve())
    run = await ctx.agent.prompt(
        "Explain what this project does in twenty lines at most, "
        "and write the explanation to EXPLAINED.md.",
        timeout="10m",
        working_dir=workdir,
    )
    if not run.ok:
        return f"the agent exited with {run.exit_code}"
    return await ctx.sandbox.read_text(f"{workdir}/EXPLAINED.md")
```

```sh
export ANTHROPIC_API_KEY=sk-ant-...
fastsandbox run app.py explain --repo .   # the claude kit is forged on the first run
```

## Gotchas

- Changing the agent is changing the kit name and the exported key; a task that
  reads a file rather than the agent's output works for every agent.
- `fastsandbox.AGENTS` is read-only data: to run another agent, use one of the
  nine kit names, not a new profile.
- `stream` and `prompt` read standard output only; standard error is in
  `AgentRun.stderr` for `prompt` and dropped by `stream`.
- A wrong or missing key usually shows as an agent that exits non-zero: check
  `run.ok` and `run.stderr` (never print the environment).
- Testing: against the fake daemon (`FakeDaemon`, in the testing module), the declaration,
  the credentials pushed and `agent.command(prompt)` can be checked; `prompt`,
  `stream` and `session` need the real daemon (the fake one answers 501).
