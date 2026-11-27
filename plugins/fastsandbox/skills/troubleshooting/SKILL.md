---
name: troubleshooting
description: Diagnosing and fixing fastsandbox programs that fail or misbehave - the daemon of Docker Sandboxes unreachable or of an unsupported version, kits slow or failing to forge or compile, agent credentials and network, HTTP 403 from the proxy, timeouts, failed commands, validation errors, files of the host changed or work lost, sandboxes that stop, tests answered 501 by the fake daemon, and how to look inside a kept sandbox. Load when an error of fastsandbox (DaemonUnavailableError, UnsupportedVersionError, TaskError, SandboxTimeoutError, CommandFailedError…) or an unexpected behavior shows up.
---

# Troubleshooting

Every error of fastsandbox derives from `SandboxError`, with a `message`, the
`operation` that failed when known, and `transient` (whether the same call may
succeed later). The command line prints it as `fastsandbox: <message>` and
exits with 1. Start every diagnosis with:

```sh
sbx version          # Docker Sandboxes installed, its daemon answering
fastsandbox info     # the socket fastsandbox found, sbx and API versions, kit cache
fastsandbox -v run app.py TASK --input-name value   # what fastsandbox does, logged
```

Full documentation: https://aartintelligent.github.io/fastsandbox/guides/troubleshooting/

## Reaching the daemon

| Symptom | Cause | Fix |
|---|---|---|
| `DaemonUnavailableError` (a `ConnectionError`, `path` = the socket tried) | Docker Sandboxes is not installed, its daemon does not run for this user, or the socket is elsewhere | Install Docker Sandboxes (https://aartintelligent.github.io/fastsandbox/get-started/installation/), check `sbx version` as the same user; `DOCKER_SANDBOXES_API` names another socket |
| `UnsupportedVersionError` (`found`, `supported`) | the daemon runs an API version this release was not checked against | upgrade fastsandbox; to go on at your own risk, `client = await fastsandbox.connect(version_policy="warn")` and `FastSandbox(client=client)` |
| the first run of a kit waits for minutes | the daemon pulls the image of the base kit, once; or a cache given the `sbx` CLI compiles the kit | wait for the pull, which later runs skip; compile a kit only the CLI resolves ahead of time, `fastsandbox kits compile <kit>` |
| `KitForgeError` | the kit is one only the `sbx` CLI resolves (a local base kit, a mixin given by reference), or the kit policy of the daemon forbids forging | give the cache the CLI, `KitCache(sbx="sbx")`; a mixin forges once its `spec.yaml` is in the JSON subset of YAML, or written in Python (`Mixin`) |
| `InvalidKitError` (`kit`, `reason`) | the forge refuses a kit argument, its value, or a mixin descriptor; a `Mixin` written in Python is checked as it is made | read `reason`: the values and pattern the kit declares, or what a mixin may not declare |
| `KitCompileError` | the `sbx` CLI, given to the cache, could not compile the kit, or is not on `PATH` | install the `sbx` CLI with Docker Sandboxes; run the compile by hand to see its output |
| `KitPackageError` (`path`) | a kit package directory is missing or invalid | delete it from the kit cache (`fastsandbox info` prints where) and make it again |

## Declaring and running tasks

| Symptom | Cause | Fix |
|---|---|---|
| `pydantic.ValidationError` before anything runs | the inputs do not match the signature (missing, wrong type, unknown name: extra inputs are refused) | the message names the field; on the command line, options are `--name-with-dashes` |
| `pydantic.ValidationError` after the run | the result does not match the return annotation | fix the annotation or the returned value; the sandbox is already deleted |
| `TaskError` when declaring | `*args`/`**kwargs`, two tasks of the same name, an unknown agent, an unreadable `timeout` (`ValueError`) | one task per name; agents are `claude`, `codex`, `copilot`, `cursor`, `devin`, `docker-agent`, `droid`, `kiro`, `opencode`; durations like `"90s"`, `"10m"`, `"1h30m"` |
| `TaskError` when running | unknown task name, two `WorkspaceDir` inputs, a dependency with a plain parameter, an agent kit that describes no agent, `async with app:` entered twice | the message says which |
| `SandboxTimeoutError` (`after`) | the function went over the `timeout` of the task, or a command or `prompt` over its own | raise the deadline; stream or log the work to see where the time goes |
| `CommandFailedError` (`exit_code`, `stdout`, `stderr`) | a command run with `check=True` exited non-zero | read its output from the error |
| `OperationFailedError` | a network rule of the task was not applied by the daemon | check the hosts and patterns of the `Network` value |
| `RuntimeError: asyncio.run() cannot be called from a running event loop` | `app.run_sync` or `fastsandbox.run` called from async code | `await app.run(...)` there |
| `fastsandbox run` says no application found | no `APP` given and no `app.py`, `main.py` or `[tool.fastsandbox] app` | pass `path/to/file.py[:name]` or set `[tool.fastsandbox] app` |

## Agents and the network

| Symptom | Cause | Fix |
|---|---|---|
| the agent fails to authenticate | its key is not in the environment of the process that runs the task, so nothing was pushed | export it in the shell that runs `fastsandbox run` (`ANTHROPIC_API_KEY` for `claude`, see the `agents` skill); without one, a secret stored with `sbx secret set` applies |
| the agent cannot reach its service | the task set `allow_agent_hosts=False`, or denies a host the agent needs | leave `allow_agent_hosts` on, or allow the hosts yourself |
| a host answers HTTP 403 | a rule denies it: the proxy of the sandbox answers in place of the host | read the activity log, `(await client.policy.log()).for_sandbox(name)`, and allow the host if it is needed |
| a host you did not allow is reached | rules add to the policy of the daemon, which may allow everything | deny what must stay out; check with `client.policy.check(...)` |

## Where the work went

| Symptom | Cause | Fix |
|---|---|---|
| files of the host repository changed | `WorkspaceDir()` and read-write `Mounted` are live mounts | use `WorkspaceDir(clone=True)`, `Uploaded` or `Mounted(..., read_only=True)`, and return the work (a patch, a file) |
| the work done in the sandbox is gone | a clone and an upload go with the sandbox, deleted after the run | return what you keep from the task, or `download_dir` it; `keep=True` to inspect |
| a sandbox created with the client stops | the daemon stops a sandbox about 30 seconds after its last session | work in it inside `async with sandbox.running():` |
| `ConflictError` on create | a sandbox of that name exists | another name (`fastsandbox.unique_name("job")`), or delete the old one |

## Tests

| Symptom | Cause | Fix |
|---|---|---|
| HTTP 501 from the fake daemon | attach, agent runs and SSH upgrade the connection, which `FakeDaemon` does not do | test declarations and commands against the fake, agent runs against the real daemon (see the `testing` skill) |
| a test cannot forge a kit (`pull access denied`) | the fake daemon serves only the published `shell` and `claude` kits | add the kit to `daemon.kits` as a `PublishedKit`, write a package with `fake_package(cache / Kit(base="shell").cache_key)` and set `FASTSANDBOX_KIT_CACHE`, or pass `kit=fake_package(...)` |
| `NotFoundError` (404) in a test | a route the fake does not serve | add it with `@daemon.route(method, pattern)` returning a `Response` |

## Looking inside a sandbox

Keep the sandbox of a run and open a shell in it:

```python
from fastsandbox import Context, FastSandbox

app = FastSandbox("debug")


@app.task(kit="shell", keep=True)
async def investigate(ctx: Context) -> str:
    ctx.log(f"kept sandbox: {ctx.sandbox.name}")
    output = await ctx.sandbox.exec("ls -la /tmp")
    return output.stdout
```

```sh
sbx ls                                                       # find the kept sandbox
ssh -o ProxyCommand="fastsandbox ssh-proxy NAME" agent@NAME  # a shell in it, through the socket
```

From Python, `client.sandbox(NAME)` reaches it (`exec`, `read_text`,
`network_rules()`…). It stops once nothing holds a session; delete it when you
are done, with `sbx` or `await client.sandbox(NAME).delete()`. Remove
`keep=True` afterwards.

To report a bug: the output of `fastsandbox info` and the smallest task that
shows it, at https://github.com/aartintelligent/fastsandbox/issues (never paste
secret values).
