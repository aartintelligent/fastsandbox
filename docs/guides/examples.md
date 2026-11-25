# Examples

The repository holds one complete program per use of the library, under
[`examples/`](https://github.com/aartintelligent/fastsandbox/tree/main/examples):
the examples of [`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox/tree/main/examples),
under the same names, written against the Python API. Where the snippets of
this documentation show one thing at a time, an example runs a whole use end
to end, and checks what it does.

## Running an example

From a checkout of the repository:

```sh
just example base
just example shell-exec
just example agent-claude ~/my-project -- "explain this project"
```

Every example talks to the daemon of the current user, creates the sandboxes it
needs and deletes them when it ends, also on an error or ++ctrl+c++. Run them
as the user owning the daemon, with the `sbx` CLI installed: the first run of a
kit compiles it and caches the package. Each file opens with what it shows,
what was measured on a real daemon, the credentials it reads, and how to run
it; the [README of the examples](https://github.com/aartintelligent/fastsandbox/blob/main/examples/README.md)
describes each of them.

## The basics

| Example | Shows |
|---|---|
| [`base`][base] | Connect, list sandboxes and images, create a sandbox from a kit, run a command, delete it |
| [`daemon`][daemon] | A client configured before it connects; health, settings, log levels, disk usage, diagnostics; CPU and memory limits and VM metrics |
| [`images`][images] | The images of the daemon: list, pull with progress, inspect, an unknown image |

## Shell sandboxes

| Example | Shows |
|---|---|
| [`shell-lifecycle`][shell-lifecycle] | The life of a sandbox: streamed creation, typed errors, sessions, start and stop, ports, working directory, guarded deletion |
| [`shell-exec`][shell-exec] | Commands: outputs and exit codes, `check`, users, working directory, environment, deadlines, standard input |
| [`shell-files`][shell-files] | Files, executable scripts, whole directories in both directions, tar archives |
| [`shell-network`][shell-network] | The network policy of one sandbox: denied hosts, HTTP rules, checks, activity log |
| [`shell-policy`][shell-policy] | The global policy: rules added, checked and removed, host path permissions, approval prompts |
| [`shell-ports`][shell-ports] | A web server in the sandbox, published on a port of the host |
| [`shell-secrets`][shell-secrets] | Custom and service secrets pushed through the socket, injected by the proxy |
| [`shell-ssh`][shell-ssh] | SSH through the socket, with the tunnel of the library and with `fastsandbox ssh-proxy` |
| [`shell-clone`][shell-clone] | Clone mode: the sandbox works on a private clone, the host fetches its commits |
| [`shell-templates`][shell-templates] | A sandbox saved as an image, started again, exported and loaded back |
| [`shell-kits`][shell-kits] | A mixin kit added to running sandboxes, in place and by a container swap |
| [`shell-interactive`][shell-interactive] | An interactive shell relayed to the local terminal, resizing included |
| [`shell-events`][shell-events] | The event stream: the replay of recent state, then live events |

## MCP

| Example | Shows |
|---|---|
| [`mcp-gateway`][mcp-gateway] | A local MCP server loaded into the gateway of a sandbox, called from inside |
| [`mcp-remote`][mcp-remote] | A remote server behind a bearer token the gateway injects |
| [`mcp-static`][mcp-static] | A sandbox created with a static set of MCP servers |
| [`mcp-dynamic`][mcp-dynamic] | The tools of the gateway itself: find, add and call a server from inside |

## Coding agents

One example per agent `sbx` knows, in three variants: interactive, in the local
terminal; `-mcp`, with an MCP server of the example loaded into its gateway;
and `-automation`, unattended on a task whose tests fail, checked afterwards.

| Agent | Interactive | With MCP | Unattended |
|---|---|---|---|
| Claude Code | [`agent-claude`][agent-claude] | [`agent-claude-mcp`][agent-claude-mcp] | [`agent-claude-automation`][agent-claude-automation] |
| Codex | [`agent-codex`][agent-codex] | [`agent-codex-mcp`][agent-codex-mcp] | [`agent-codex-automation`][agent-codex-automation] |
| GitHub Copilot | [`agent-copilot`][agent-copilot] | [`agent-copilot-mcp`][agent-copilot-mcp] | [`agent-copilot-automation`][agent-copilot-automation] |
| Cursor | [`agent-cursor`][agent-cursor] | [`agent-cursor-mcp`][agent-cursor-mcp] | [`agent-cursor-automation`][agent-cursor-automation] |
| Devin | [`agent-devin`][agent-devin] | [`agent-devin-mcp`][agent-devin-mcp] | [`agent-devin-automation`][agent-devin-automation] |
| Docker Agent | [`agent-docker-agent`][agent-docker-agent] | [`agent-docker-agent-mcp`][agent-docker-agent-mcp] | [`agent-docker-agent-automation`][agent-docker-agent-automation] |
| Droid | [`agent-droid`][agent-droid] | [`agent-droid-mcp`][agent-droid-mcp] | [`agent-droid-automation`][agent-droid-automation] |
| Kiro | [`agent-kiro`][agent-kiro] | [`agent-kiro-mcp`][agent-kiro-mcp] | [`agent-kiro-automation`][agent-kiro-automation] |
| OpenCode | [`agent-opencode`][agent-opencode] | [`agent-opencode-mcp`][agent-opencode-mcp] | [`agent-opencode-automation`][agent-opencode-automation] |

[`agent-kit-args`][agent-kit-args] chooses the model and the effort of the
`claude` kit when it is compiled (`Kit(args=…)`), without starting the agent.

[base]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/base.py
[daemon]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/daemon.py
[images]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/images.py
[shell-lifecycle]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_lifecycle.py
[shell-exec]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_exec.py
[shell-files]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_files.py
[shell-network]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_network.py
[shell-policy]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_policy.py
[shell-ports]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_ports.py
[shell-secrets]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_secrets.py
[shell-ssh]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_ssh.py
[shell-clone]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_clone.py
[shell-templates]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_templates.py
[shell-kits]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_kits.py
[shell-interactive]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_interactive.py
[shell-events]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/shell_events.py
[mcp-gateway]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/mcp_gateway.py
[mcp-remote]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/mcp_remote.py
[mcp-static]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/mcp_static.py
[mcp-dynamic]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/mcp_dynamic.py
[agent-claude]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_claude.py
[agent-claude-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_claude_mcp.py
[agent-claude-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_claude_automation.py
[agent-codex]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_codex.py
[agent-codex-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_codex_mcp.py
[agent-codex-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_codex_automation.py
[agent-copilot]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_copilot.py
[agent-copilot-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_copilot_mcp.py
[agent-copilot-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_copilot_automation.py
[agent-cursor]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_cursor.py
[agent-cursor-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_cursor_mcp.py
[agent-cursor-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_cursor_automation.py
[agent-devin]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_devin.py
[agent-devin-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_devin_mcp.py
[agent-devin-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_devin_automation.py
[agent-docker-agent]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_docker_agent.py
[agent-docker-agent-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_docker_agent_mcp.py
[agent-docker-agent-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_docker_agent_automation.py
[agent-droid]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_droid.py
[agent-droid-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_droid_mcp.py
[agent-droid-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_droid_automation.py
[agent-kiro]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_kiro.py
[agent-kiro-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_kiro_mcp.py
[agent-kiro-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_kiro_automation.py
[agent-opencode]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_opencode.py
[agent-opencode-mcp]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_opencode_mcp.py
[agent-opencode-automation]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_opencode_automation.py
[agent-kit-args]: https://github.com/aartintelligent/fastsandbox/blob/main/examples/agent_kit_args.py
