---
name: agents
description: Putting a coding agent to work in a throw-away Docker Sandboxes sandbox with fastsandbox — Claude Code (`claude`), Codex (`codex`), Copilot (`copilot`), Cursor (`cursor`), Devin (`devin`), Docker Agent (`docker-agent`), Droid (`droid`), Kiro (`kiro`), OpenCode (`opencode`). Load before writing or changing an `@app.agent` task, a call to `ctx.agent.prompt`, `ctx.agent.stream` or `ctx.agent.session`, the credentials or the network of an agent, how an agent gets a repository (`WorkspaceDir`, clone mode, `Uploaded`, `Mounted`) and how its work comes back (tests, patch, file), MCP tools for an agent, or several agents run at once.
---

# Agents in sandboxes

fastsandbox is a client of Docker Sandboxes: Docker Sandboxes must be installed
and its daemon running for the user (`sbx version` answers), or nothing runs. An
agent task runs the agent inside its own throw-away sandbox, created from the
agent's kit and deleted after the run. The agent's API key is read from the
environment of the calling process and pushed as a secret of that sandbox only:
the proxy of the sandbox injects it, the agent sees a placeholder.

## Essentials

- **Declare with `@app.agent("<kit>", ...)`**, always called, never bare. It takes
  the options of `@app.task` (`timeout`, `network`, `env`, `cpus`, `memory`,
  `keep`, `max_concurrency`, `name`, `description`), plus `kit` (a `Kit` or a kit
  name, the agent's own by default) and `allow_agent_hosts`. An unknown agent
  raises `TaskError` when the task is declared.
- **Start with `WorkspaceDir(clone=True)`**: the agent works on a private Git
  clone, the host repository stays as it is, and what you keep is what the task
  returns. The directory must be a Git repository.
- **`WorkspaceDir()` edits the host**: the directory is mounted read-write and
  the agent's edits reach the files of the machine during the run. Use it only
  when that is the point, and commit or stash first.
- **The agent's report is not a result.** Run the project's checks in the
  sandbox after the agent (`await ctx.sandbox.exec(command, working_dir=...)`)
  and return what they say.
- **Bring the work back explicitly**: a patch (`git format-patch` on the clone),
  a file the agent was asked to write (`ctx.sandbox.read_text(path)`), a
  directory (`ctx.sandbox.download_dir(path, host_dir)`), or a test report. A
  clone or an upload goes with the sandbox.
- **Give unattended agents `network` rules** (`Network.allow`, `allow_http`,
  `deny`, `deny_http`). Rules add to the daemon's policy, whose default may
  allow everything: an allow rule does not block the rest, a deny rule blocks
  its host. Read what the sandbox reached afterwards with
  `(await ctx.client.policy.log()).for_sandbox(ctx.sandbox.name)`.
- **`allow_agent_hosts=True`** (default) allows the hosts the agent's kit
  declares ahead of the task's rules, only when `network` is given. With
  `False`, the task's rules apply alone and may cut the agent off its service.
- **Keys come from the caller's environment** (`ANTHROPIC_API_KEY`, ...). Never
  print, log, hard-code or pass a key as an input; tell the user which variable
  to export. If none is set, nothing is pushed and a secret stored with
  `sbx secret set` applies.
- **`kiro` is the exception**: `sbx` has no service secret for it, so
  `KIRO_API_KEY` is given as an environment variable to the agent process and
  its value is visible inside the sandbox.
- **Bound the time twice**: `timeout=` on the decorator bounds the whole call of
  the function; `ctx.agent.prompt(..., timeout="15m")` bounds one agent run.
  Both raise `SandboxTimeoutError`.
- **Name the working directory**: the parameter keeps the caller's value (`.`),
  so pass `working_dir=str(repo.resolve())` to `prompt`/`stream` and `exec`.
- **Write prompts the run can be checked against**: what to do, the command
  that checks it, what to leave behind (commits on the clone, a file at a
  given path).
- **First run of a kit compiles it** with the `sbx` CLI (minutes for an agent
  kit): suggest `fastsandbox kits compile <kit>` ahead of time.

## Decide

How the agent gets the code (an `Annotated[Path, marker]` input):

| You want | Marker | Changes |
|---|---|---|
| Changes reviewed before they land (default choice) | `WorkspaceDir(clone=True)` | Stay in the sandbox, leave as the result |
| Edits made live on the host | `WorkspaceDir()` | Reach the host during the run |
| A copy to experiment on | `Uploaded("/work")` | Stay in the sandbox |
| Material to read only | `Mounted("/data", read_only=True)` | None |

How the work comes back:

| Result | How |
|---|---|
| Pass or fail | Run the tests with `ctx.sandbox.exec` after the agent |
| A change to review | Commits on the clone, returned by `git format-patch --stdout <head>..HEAD` |
| An answer | Ask for a file, read it with `ctx.sandbox.read_text` (works for every agent) |
| A directory | `ctx.sandbox.download_dir(path, host_dir)` |

How the agent runs:

| Mode | Call | Returns |
|---|---|---|
| One prompt, wait for the end | `await ctx.agent.prompt(prompt, timeout=..., working_dir=..., env=...)` | `AgentRun` (`exit_code`, `ok`, `stdout`, `stderr`, `events`) |
| One prompt, follow it | `async for event in ctx.agent.stream(prompt, working_dir=...)` | Parsed JSON lines or text lines |
| Interactive | `await ctx.agent.session(*args, tty=True, size=None)` | `Interactive` |

## Map

| Need | API | Reference |
|---|---|---|
| The agents, their keys, outputs, commands; model choice | `AGENTS`, `AgentProfile`, `Credential`, `AgentRunner`, `AgentRun`, `Kit(base=..., args=...)` | [agents.md](reference/agents.md) |
| Getting the code in and the work out | `WorkspaceDir`, `Uploaded`, `Mounted`, `read_text`, `download_dir` | [repository.md](reference/repository.md) |
| Network rules and the activity log | `Network`, `allow_agent_hosts`, `ctx.client.policy.log()` | [network.md](reference/network.md) |
| Events, progress, logs, debugging a run | `stream`, `ctx.report_progress`, `ctx.log`, `keep=True` | [follow.md](reference/follow.md) |
| MCP tools for the agent | `ctx.sandbox.load_mcp_server` | [tools.md](reference/tools.md) |
| Several agents or runs at once | `max_concurrency`, `async with app`, `asyncio.gather` | [several.md](reference/several.md) |

## References

- [reference/agents.md](reference/agents.md): the agents table, profiles,
  credentials, the runner's methods, choosing the kit and the model.
- [reference/repository.md](reference/repository.md): workspace, clone, upload,
  read-only mount; tests, patch, file.
- [reference/network.md](reference/network.md): baseline, rules, agent hosts,
  activity log.
- [reference/follow.md](reference/follow.md): streaming events, progress, logs,
  keeping the sandbox, interactive sessions.
- [reference/tools.md](reference/tools.md): MCP servers loaded for the agent.
- [reference/several.md](reference/several.md): several agents on one issue,
  many runs of one agent, failures.

Full pages:

- https://aartintelligent.github.io/fastsandbox/get-started/quickstart/
- https://aartintelligent.github.io/fastsandbox/framework/agents/
- https://aartintelligent.github.io/fastsandbox/agents/repository/
- https://aartintelligent.github.io/fastsandbox/agents/network/
- https://aartintelligent.github.io/fastsandbox/agents/follow/
- https://aartintelligent.github.io/fastsandbox/agents/tools/
- https://aartintelligent.github.io/fastsandbox/agents/several/
- https://aartintelligent.github.io/fastsandbox/guides/troubleshooting/
