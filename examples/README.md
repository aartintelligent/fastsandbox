# Examples

One program per use of fastsandbox: the examples of
[`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox/tree/main/examples),
under the same names, written against the Python API. Run one from the
repository root:

```sh
just example base
just example agent-claude-mcp
# or
uv run python examples/shell_exec.py
```

Every example talks to the daemon of the current user, creates the sandboxes
it needs and deletes them when it ends, also on an error or Ctrl-C: they are
`async with client.create(...)` blocks, which `asyncio` unwinds when it
cancels the example. Run them as the user owning the daemon. Their kits need
no `sbx` CLI: the kit cache of the library (`fastsandbox.KitCache`, see
[`common/kit.py`](common/kit.py)) forges each package through the socket
alone, in a few seconds, and keeps it in memory for the run; the image of the
base kit, pulled on the first run, stays on the daemon as the cache of the
next ones. Only [`shell-kits`](shell_kits.py) asks the CLI, for its mixin
written in YAML: it compiles it once, into `~/.cache/fastsandbox/kits`.
The `-mcp` variants and the [MCP examples](#mcp) still register their servers
with `sbx mcp add`.

When a kit declares a credential the daemon does not authorize, the creation
of a sandbox reports it as withheld (`Created.withheld`), and the examples
print it: the daemon gives the sandbox none of its values. The credential of
a published kit is authorized when its artifact is the one the CLI resolves,
as with the packages the forge makes and those the CLI compiles.

Each file opens with what it shows, what was measured and how to run it; the
plumbing several examples need lives in [`common/`](#common), so that each
example stays about the library. A check that does not hold ends the example
with `error: …` and exit code 1.

## The basics

| Example | Shows |
|---|---|
| [`base`](base.py) | Connect, list sandboxes and images, create a sandbox from a kit package, run a command, delete it |
| [`daemon`](daemon.py) | A client configured before it connects (socket, deadlines, version policy); what a program reads to watch the daemon: health, settings changed from their default, log levels, disk usage, network policy, internal state and diagnostics; a setting and a log level changed then restored; a sandbox created with CPU and memory limits and the metrics of its VM |
| [`images`](images.py) | The images of the daemon: the list, a pull followed as it happens then waited for, the details and local metadata of an image, what an unknown image gives. The tag it adds is removed |

## Shell sandboxes

| Example | Shows |
|---|---|
| [`shell-lifecycle`](shell_lifecycle.py) | The life of a sandbox step by step: a creation refused for an unknown profile, a streamed creation with a port and options, typed errors (`NotFoundError`, `ConflictError`, `InvalidInputError`), sessions, start and stop, desired ports replaced, a UDP port, the working directory, a deletion guarded by the identifier |
| [`shell-exec`](shell_exec.py) | Commands: outputs and exit codes, `check`, users, working directory, environment, per-command deadlines, standard input, an execution followed by its identifier, the agent of the kit without a terminal |
| [`shell-files`](shell_files.py) | Files: a configuration file, an executable script, whole directories in both directions, tar archives as they are |
| [`shell-network`](shell_network.py) | Network policy of one sandbox: a denied host and the proxy answer, an HTTP rule narrowed to a method and a path, the rules of the sandbox, checks, activity log. The rules go with the sandbox |
| [`shell-policy`](shell_policy.py) | The policy beyond one sandbox: a global rule added, checked and removed by identifier, failures inside a success, hosts a rule cannot name refused before anything is sent (`InvalidRequestError`), sandbox host and HTTP rules removed through the sandbox, the reload of the policy, host path permissions, approval prompts. The global policy ends as it began |
| [`shell-ports`](shell_ports.py) | A web server in the sandbox (`serve` of [`tools.py`](common/programs/tools.py)), published on a port of the host and reached from it |
| [`shell-secrets`](shell_secrets.py) | Secrets pushed through the socket alone, with dummy values. Custom secrets: the proxy writes the value of a secret into a request to its host and leaves the placeholder of another, the sandbox holds no value, the secrets survive a restart and go with an empty list (checked from inside with `get` of [`tools.py`](common/programs/tools.py) and the public echo service `postman-echo.com`). Service credentials: recorded by the daemon, never in the sandbox. The answer of the daemon to each update (`CredentialsOutcome`), and the credentials it withholds |
| [`shell-ssh`](shell_ssh.py) | SSH through the socket: the greeting read through the tunnel of the library, then the SSH client of the system with `fastsandbox ssh-proxy` as its `ProxyCommand`, as `agent` and as `root`, with no key and nothing written to `~/.ssh`. The server accepts any user: the socket is the boundary |
| [`shell-clone`](shell_clone.py) | Clone mode (`client.create(workspace=…, clone=True)`): the sandbox works on a private clone of a repository, the source read-only; the agent commits there, and the host fetches the commits with `git fetch` through a relay of `git upload-pack` in the sandbox, the example run again |
| [`shell-templates`](shell_templates.py) | A sandbox saved as an image, a new sandbox started from it with its changes (from a creation request stored as JSON), the image exported to a file, removed and loaded back |
| [`shell-kits`](shell_kits.py) | A mixin kit of the examples ([`example-mixin`](kits/example-mixin/spec.yaml)) added to running sandboxes: in place (the kit list stays as it was), by a swap of the container (work in progress kept, kit list updated), then both by hand from the parts of the package |
| [`shell-forge`](shell_forge.py) | A kit package forged through the socket alone, without the `sbx` CLI (`KitForge`): the shell kit rebuilt from its published image, a mixin written in Python (`KitDescriptor`, `LifecycleStep`: an install command given the variables of the MCP gateway, a startup command in the background, a host allowed and one denied) and one read from its directory ([`json-mixin`](kits/json-mixin/spec.yaml), JSON, `Mixin.read`). What a forged mixin may not declare, refused with its kit and its reason (`InvalidKitError`); the package forged in memory, its images too; then both mixins run in the sandbox, the network rules of the first are applied by the daemon and removed with the sandbox, and the kit is forged into a directory and opened again from it |
| [`shell-interactive`](shell_interactive.py) | An interactive shell relayed to the local terminal, window resizing included |
| [`shell-events`](shell_events.py) | The daemon event stream: the replay of recent state up to its sync marker, then live events while a sandbox is created, used and deleted |

## MCP

The MCP gateway of a sandbox, checked from where its agent uses it: inside the
sandbox. Each example runs [`mcp_client.py`](common/programs/mcp_client.py), a
minimal MCP client over streamable HTTP, in a shell sandbox against
`http://mcp-gateway.docker.internal/mcp`, and removes what it registered and
stored when it ends. The MCP servers of the examples run on the host, built
with the official [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
([`common/mcp.py`](common/mcp.py)).

| Example | Shows |
|---|---|
| [`mcp-gateway`](mcp_gateway.py) | A local server (`sbx mcp add --command`) loaded through the socket, its tools listed and called from the sandbox, the gateway port refusing the host, the server unloaded |
| [`mcp-remote`](mcp_remote.py) | A remote server over streamable HTTP (`--url`) behind a bearer token the gateway takes from the `sbx` secret store: called from the sandbox, which never holds the token, then the token rotated |
| [`mcp-static`](mcp_static.py) | A sandbox created with a static MCP set (`CreateRequest.with_static_mcp_servers`): served without a load, and closed to additions from inside |
| [`mcp-dynamic`](mcp_dynamic.py) | The gateway's own tools used from inside: `mcp-find` finds a server registered on the host, `mcp-add` loads it, `mcp-exec` calls a tool by name |

The local server is the example itself: `sbx` starts it as
`python <example> mcp-serve`, with the Python of the environment of the
examples, and it serves MCP on standard input and output. The HTTP server of
`mcp-remote` and `mcp-dynamic` listens on a loopback port of the host, for the
gateway only, with a dummy token made for the run.

What the examples of `docker-sandbox` measured on `sbx` v0.54.0, and these
check again:

- The gateway answers inside the sandbox only: its port on the host answers
  `401 Unauthorized`, since the proxy of the sandbox adds the credential.
- Besides the tools of its servers, a gateway offers `mcp-find`, `mcp-add`,
  `mcp-config-set`, `mcp-exec` and `code-mode`. Tools are not prefixed by
  server: `mcp-add` refuses a server whose tool names are already taken.
- A server added from inside with `mcp-add` stays loaded: the socket lists it
  among the `servers` of the gateway, and later sessions offer it, until the
  program unloads it. An agent can thus load any server registered on the
  host; a static gateway offers only `mcp-exec` and `code-mode`, so a runner
  that must fix the MCP servers of a sandbox creates it with a static set.
- `sbx mcp add --url` probes the server: one that answers `401` without OAuth
  metadata is refused, so a header secret is stored before the registration.
  The first connection adds a `mcp:<server>:<placeholder>:endpoint` entry that
  binds the secret to the URL and outlives it; the examples remove both.
- A gateway fills the header when it connects to the server and keeps that
  connection: a rotated secret is used once the server is unloaded and loaded
  again.

## Coding agents

One example per agent `sbx` knows, and an `-mcp` variant that also gives the
agent the MCP server of the examples. Each forges the kit of its agent from
`docker.io/sbx/<agent>:latest` without the `sbx` CLI, runs the agent session
in the local terminal, and deletes the sandbox when the session ends.

Like `sbx run AGENT [PATH] [-- AGENT_ARGS...]`, an example takes the directory
the agent works on, mounted read-write at the same path, and arguments for the
agent after `--`: options added to its default command, or a prompt in its
place. Without a directory, nothing of the host is mounted: the agent works in
the filesystem of the sandbox.

```sh
just example agent-claude
just example agent-claude ~/my-project
just example agent-claude ~/my-project -- "explain this project"
```

| Agent | Examples | Credential read from the environment |
|---|---|---|
| Claude Code | [`agent-claude`](agent_claude.py), [`agent-claude-mcp`](agent_claude_mcp.py) | `ANTHROPIC_API_KEY` |
| Codex | [`agent-codex`](agent_codex.py), [`agent-codex-mcp`](agent_codex_mcp.py) | `OPENAI_API_KEY` or `CODEX_API_KEY` |
| OpenCode | [`agent-opencode`](agent_opencode.py), [`agent-opencode-mcp`](agent_opencode_mcp.py) | Any of the provider keys below |
| GitHub Copilot | [`agent-copilot`](agent_copilot.py), [`agent-copilot-mcp`](agent_copilot_mcp.py) | `COPILOT_GITHUB_TOKEN`, `GH_TOKEN` or `GITHUB_TOKEN` |
| Cursor | [`agent-cursor`](agent_cursor.py), [`agent-cursor-mcp`](agent_cursor_mcp.py) | `CURSOR_API_KEY` |
| Devin | [`agent-devin`](agent_devin.py), [`agent-devin-mcp`](agent_devin_mcp.py) | `DEVIN_API_KEY` |
| Docker Agent | [`agent-docker-agent`](agent_docker_agent.py), [`agent-docker-agent-mcp`](agent_docker_agent_mcp.py) | Any of the provider keys below |
| Droid | [`agent-droid`](agent_droid.py), [`agent-droid-mcp`](agent_droid_mcp.py) | `FACTORY_API_KEY` |
| Kiro | [`agent-kiro`](agent_kiro.py), [`agent-kiro-mcp`](agent_kiro_mcp.py) | `KIRO_API_KEY`, given to the agent as is: `sbx` knows no service secret for Kiro |

Provider keys: `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY` (or
`GOOGLE_API_KEY`), `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `MISTRAL_API_KEY`,
`NEBIUS_API_KEY`, `XAI_API_KEY`. The credentials of each agent are those of
its profile in `fastsandbox.agents`, the ones `FastSandbox.agent` uses.

A key found in the environment is given to the sandbox of the example only,
as a sandbox-scoped service secret: the proxy of the sandbox injects it on
outgoing requests, the agent never sees it, and it goes away with the sandbox.
Without a key, the agent uses the credential the daemon holds for its kit, a
Claude subscription or a secret stored with `sbx secret set <service>` for
instance, which the proxy injects into every sandbox of that kit, those of the
examples included; a key from the environment takes precedence for one
sandbox. The examples never read it, and cannot tell whether there is one. A
credential the daemon withholds instead is printed at creation, and so is a
key it withholds when the example pushes it. Without any credential, the
agent offers its own login inside the session: `/login` for Claude Code, the
device flow for Kiro; Codex can also sign in on the host beforehand with
`sbx secret set openai --oauth`.

The agent session opens as `sbx run` opens it
([`common/host.py`](common/host.py)): with the terminal type (`TERM`,
`COLORTERM`) and the time zone (`TZ`) of the host, its desktop session as
`SBX_HOST_*` variables, through which the sandbox reaches it, and its SSH
agent, unless the `ssh.agentForwardingEnabled` setting is off.

### Kit arguments

[`agent-kit-args`](agent_kit_args.py) chooses the model and the effort of the
`claude` kit, the arguments it declares, when the kit is forged
(`Kit(args=…)`, as `sbx create --kit-arg model=…`): the forge checks their
values as the CLI does, a value the kit refuses being an `InvalidKitError`,
and the sandbox gets them as `CLAUDE_MODEL` and `CLAUDE_REASONING_EFFORT`, and
in `~/.claude/settings.json`. It starts no agent and uses no credential.

[`agent-kit-forge`](agent_kit_forge.py) makes the same sandbox from a package
forged into a directory (`KitForge`), checks that the daemon withholds no
credential of the kit, and gives Claude Code the MCP
server of the examples by a mixin (`Mixin.mcp`): served by the script on a
loopback port of the host, the same at every run unless it is taken (the port
is part of the mixin, and another one would add images to the daemon), which
the sandbox reaches at `host.docker.internal`, registered at install time
with `claude mcp add`, its bearer token, random at
every run, given at creation (`McpServer.env`). From inside the sandbox, the
MCP client of the examples uses the server as Claude Code would, at the URL
and with the header it registered in `~/.claude.json`: it lists the tools and
calls `sum`, and the server checks the token of every request. It never starts
Claude Code.

### The MCP variants

The `-mcp` examples register their own script as a local MCP server
(`sbx mcp add`, checked first against the MCP policy of the daemon), load it
into the gateway of the sandbox, call its `sum` tool from inside the sandbox
with the client of the [MCP examples](#mcp), then start the agent session: ask
the agent to call the `sum`, `echo` or `host_time` tool. When `sbx` starts the
script as the server (`mcp-serve`), it serves MCP on standard input and output
instead ([`common/mcp.py`](common/mcp.py)). The registration is removed when
the example ends.

## Unattended agents

The `-automation` examples run an agent the way a runner does: one prompt, no
terminal, a deadline, and a verification that does not trust the agent. Each
writes a small project whose test suite fails ([`common/task/`](common/task))
under `examples/target/automation/<run>/calc` on the host, and mounts it as
the workspace of a throw-away sandbox, with a pristine copy mounted read-only
for the diff. The agent runs in its non-interactive mode and changes the files
of the host, as with `sbx run`; the example then runs the tests again and
prints the diff and the hosts the agent reached. A prompt given on the command
line replaces the default task; the example fails when the tests still fail.

```sh
just example agent-claude-automation
just example agent-codex-automation "Add a div operation to calc.sh, with its tests"
```

| Agent | Example | Non-interactive command |
|---|---|---|
| Claude Code | [`agent-claude-automation`](agent_claude_automation.py) | `claude --dangerously-skip-permissions -p <prompt> --output-format stream-json --verbose` |
| Codex | [`agent-codex-automation`](agent_codex_automation.py) | `codex exec --dangerously-bypass-approvals-and-sandbox --skip-git-repo-check --json <prompt>` |
| OpenCode | [`agent-opencode-automation`](agent_opencode_automation.py) | `opencode run --auto <prompt>` |
| GitHub Copilot | [`agent-copilot-automation`](agent_copilot_automation.py) | `copilot --yolo -p <prompt> --no-ask-user` |
| Cursor | [`agent-cursor-automation`](agent_cursor_automation.py) | `cursor-agent --yolo -p <prompt> --trust --output-format stream-json` |
| Droid | [`agent-droid-automation`](agent_droid_automation.py) | `droid exec --auto high -o stream-json <prompt>` |
| Devin | [`agent-devin-automation`](agent_devin_automation.py) | `devin --permission-mode dangerous --respect-workspace-trust=false -p <prompt>` |
| Kiro | [`agent-kiro-automation`](agent_kiro_automation.py) | `kiro chat --trust-all-tools --no-interactive <prompt>` |
| Docker Agent | [`agent-docker-agent-automation`](agent_docker_agent_automation.py) | `docker-agent run --yolo --exec <prompt>` |

The command is the headless command of the agent's profile in
`fastsandbox.agents`, the one `FastSandbox.agent` and `ctx.agent.prompt(...)`
run in an application; the program and its run options come from the kit
itself (`KitPackage.agent`), the non-interactive flags from the documentation
of each agent, linked from each example. A credential is required, since
nobody can log in: the keys of the table above, or the credential the daemon
holds for the kit, a Claude subscription or a secret stored with
`sbx secret set` for instance; without any, the example warns and the agent
fails. Kiro
has no service secret in `sbx`, so `KIRO_API_KEY` is passed to the agent
process as is and is visible inside the sandbox.

The network of the sandbox is not narrowed to the hosts of the agent: a
sandbox rule cannot override the global `default-allow-all` rule, since deny
rules take precedence over allow rules. The examples report instead what the
agent reached, from the activity log of the proxy.

## `common`

[`common/`](common/__init__.py) holds what several examples share:

| Module | Holds |
|---|---|
| [`__init__.py`](common/__init__.py) | `connect`, `main` (the outcome of an example in one line), `expect`, `report_withheld` (the credentials the daemon withholds from a sandbox it created) |
| [`kit.py`](common/kit.py) | Kit packages through the kit cache of the library, forged without the `sbx` CLI or compiled by it when asked: a kit alone, composed with a mixin, or with kit arguments |
| [`terminal.py`](common/terminal.py) | The local terminal relayed to an interactive session: raw mode, window resizing, end of input |
| [`host.py`](common/host.py) | What `sbx run` passes from the host to an agent session |
| [`program.py`](common/program.py) | The programs of [`programs/`](common/programs/__init__.py) copied into a sandbox |
| [`mcp.py`](common/mcp.py) | The MCP tools of the examples on standard input and output or streamable HTTP, their registration with `sbx`, the in-sandbox client |
| [`agent.py`](common/agent.py) | The flow of the agent examples, with or without the MCP server |
| [`automation.py`](common/automation.py) | The flow of the unattended ones, on the task of [`task/`](common/task) |

The programs run inside a sandbox, [`tools.py`](common/programs/tools.py) (a
web server and an HTTP client through the proxy of the sandbox) and
[`mcp_client.py`](common/programs/mcp_client.py), are scripts of the Python
standard library alone: the `shell` kit ships Python 3, so they are copied and
run as they are, where the examples of `docker-sandbox` build static musl
binaries.
