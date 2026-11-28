# Troubleshooting

What usually goes wrong when an agent sandbox is set up, and what to do about
it. Every error of fastsandbox derives from
[`SandboxError`][fastsandbox.exceptions.SandboxError], and the command line
prints it as `fastsandbox: <message>`; the [Errors](../client/errors.md) page
lists them all.

## Reaching the daemon

| Symptom | Cause | What to do |
|---|---|---|
| [`DaemonUnavailableError`][fastsandbox.exceptions.DaemonUnavailableError] | Docker Sandboxes is not installed, its daemon does not run for this user, or its socket is elsewhere. | [Install Docker Sandboxes](../get-started/installation.md#install-docker-sandboxes), and check that `sbx version` answers, as the same user. `fastsandbox info` prints the socket it tried; `DOCKER_SANDBOXES_API` names another one. |
| [`UnsupportedVersionError`][fastsandbox.exceptions.UnsupportedVersionError] | The daemon runs an API version this release was not checked against. | Upgrade fastsandbox. To go on at your own risk, connect with `connect(version_policy="warn")` and give the client to the application, `FastSandbox(client=...)`. |
| The first run waits for minutes | The daemon pulls the image of the base kit, once; or a cache given the `sbx` CLI compiles the kit with it. | Wait for the pull, which later runs skip; compile a kit only the CLI resolves ahead of time: `fastsandbox kits compile ./kits/my-local-kit`. |
| `KitForgeError` | The kit is one only the `sbx` CLI resolves (the directory of a local kit, a mixin given by reference), or the kit policy of the daemon forbids forging it. | Give the cache the CLI, `KitCache(sbx="sbx")`; a mixin forges once its `spec.yaml` is written in the JSON subset of YAML, or written in Python (`Mixin`). |
| `InvalidKitError` | The forge refuses a kit argument, its value, or a mixin descriptor; a `Mixin` written in Python, `Mixin.mcp()` included, is checked, and refused, as it is made. | Read `kit` and `reason`: the values and the pattern the kit declares, or what the mixin may not declare. |
| A kit fails to compile | The `sbx` CLI is not on `PATH`, for a cache that compiles with it. | Install it with Docker Sandboxes; the cache needs it once per kit and `sbx` version. |

## Running the agent

| Symptom | Cause | What to do |
|---|---|---|
| [`TaskError`][fastsandbox.exceptions.TaskError]: unknown agent | The name is not one of the agents `sbx` knows. | Use the name of its kit: `claude`, `codex`, `copilot`, `cursor`, `devin`, `docker-agent`, `droid`, `kiro`, `opencode`. |
| The agent fails to authenticate | Its key is not in the environment of the process that runs the task, so nothing was pushed. | Export the key in the shell that runs `fastsandbox run`; the [agents page](../framework/agents.md#the-agents) names the variable of each agent. Without one, a secret stored with `sbx secret set` applies. |
| The agent cannot reach its service | The task turned `allow_agent_hosts` off, or denies a host the agent needs. | Leave `allow_agent_hosts` on, or allow the hosts of the agent yourself; read the [activity log](../agents/network.md#3-read-what-it-reached). |
| A host answers HTTP 403 | A rule denies it: the proxy answers in place of the host. | Read the activity log of the run, and allow the host if the agent needs it. |
| The agent does not get the tools of a server of the host | The server, given by `Mixin.mcp()`, does not serve streamable HTTP at `/mcp` on the port given to `McpServer.host()`, on the loopback, or refuses the token the sandbox sends. | Serve on `127.0.0.1:<port>/mcp`, and create the sandbox with `env=server.env(token)` for the token the server checks; inside the sandbox, `~/.claude.json` shows what was registered. |
| [`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError] | The run went over the `timeout` of the task, or of `prompt(timeout=...)`. | Raise the deadline, or [stream the events](../agents/follow.md) of the agent to see where the time goes. |
| [`CommandFailedError`][fastsandbox.exceptions.CommandFailedError] | A command run with `check=True` exited with a non-zero code. | Its `exit_code`, `stdout` and `stderr` say why. |
| `pydantic.ValidationError` | The inputs do not match the signature of the task, or the result its return annotation. | The message names the field. |

## Where the work went

| Symptom | Cause | What to do |
|---|---|---|
| Files of your repository changed | `WorkspaceDir()` mounts your directory read-write. | Use `WorkspaceDir(clone=True)`, and take the work back as a patch (see [Give it a repository](../agents/repository.md)). |
| The work of the agent is gone | A clone and an upload go with the sandbox. | Return what you keep from the task: a patch, a file, a report. To look at what was left, keep the sandbox with `keep=True`. |
| A sandbox created with the client stops | A sandbox stops about 30 seconds after its last session. | Work in it inside `async with sandbox.running():` (see [Sessions](../client/sandboxes.md#sessions)). |

## Testing

| Symptom | Cause | What to do |
|---|---|---|
| A test against the fake daemon gets HTTP 501 | Agent runs, interactive sessions and SSH tunnels upgrade the connection, which the fake daemon does not do. | Test the declaration of the task and its commands against the fake daemon, the agent run against the real one (see [Testing](testing.md#agents)). |

## Looking inside

When the cause is not in this list, keep the sandbox of a run with `keep=True`,
then open a shell in it:

```sh
ssh -o ProxyCommand="fastsandbox ssh-proxy NAME" agent@NAME
```

and delete it when you are done. To report a bug, open an
[issue](https://github.com/aartintelligent/fastsandbox/issues) with the output
of `fastsandbox info` and the smallest task that shows it.
