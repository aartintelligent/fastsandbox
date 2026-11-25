# Sandboxes

Full page: https://aartintelligent.github.io/fastsandbox/client/sandboxes/

## API

### Creating

```text
Client.create(
    name: str | None = None,                    # unique_name() by default: "fastsandbox-<hex>"
    *,
    kit: Kit | KitPackage | str | None = "shell",  # None: create from `request` alone
    request: CreateRequest | None = None,       # a full request; the other arguments adjust it
    workspace: str | os.PathLike[str] | None = None,  # host dir mounted read-write at its own path
    clone: bool = False,                        # work on a private Git clone of `workspace`
    workspaces: Sequence[Workspace] = (),       # further mounts
    env: Mapping[str, str] | None = None,
    ports: Sequence[PortBinding] = (),          # published at every start
    cpus: int | None = None,
    memory: str | None = None,                  # sbx notation, e.g. "4g"
    template: str | None = None,                # an image to start from, e.g. a saved sandbox
    pull_policy: PullPolicy | None = None,      # PullPolicy.ALWAYS / MISSING / NEVER
) -> Creation
```

`Creation` (not a coroutine; nothing happens until it is used):

| Use | Gives |
|---|---|
| `sandbox = await client.create(...)` | the `Sandbox`; it stays until deleted |
| `async with client.create(...) as sandbox:` | the `Sandbox`, force-deleted on exit, also on an error or a cancellation (a sandbox already gone is ignored) |
| `creation.created` | the `Created` answer once created (`id`, `name`, `agent`, `status`, `workspace`, `mcp`), else `None` |
| `creation.name` | the name it creates |

The kit is compiled on first use (see [kits](kits.md)). A sandbox runs right
after its creation. Errors: `ConflictError` for a name in use,
`InvalidInputError` for a request the daemon refuses (an unknown governance
`profile`…), `ValueError` when `kit=None` and no `request`, `KitCompileError`
when the kit cannot be compiled.

`Workspace(dir: str, read_only: bool = False, target: str | None = None)`
mounts a further host directory or file (at `target`, else at its own path).

### Sessions

The daemon stops a sandbox about 30 s after its last session closes.

| Call | What it does |
|---|---|
| `async with sandbox.running():` | starts the sandbox if needed and holds a session for the block (yields the sandbox) |
| `await sandbox.ensure_running() -> Session` | opens a session, pushes an empty credentials update and starts the sandbox, as the CLI does |
| `await sandbox.hold_session() -> Session` | opens a session without starting: keeps a running sandbox running |
| `Session.release()` | closes the session; `Session` is also an async context manager |
| `Session.is_connected`, `Session.sandbox` | whether it is open now; the sandbox name |

A session the daemon closes is reopened on its own until it is released or
the sandbox no longer exists.

### Looking up

| Call | Gives |
|---|---|
| `await client.sandboxes.list() -> list[SandboxInfo]` | every sandbox |
| `await client.sandboxes.get(name) -> SandboxInfo` | one sandbox, or `NotFoundError` |
| `await client.sandboxes.find(name) -> SandboxInfo \| None` | one sandbox, or `None` |
| `client.sandbox(name) -> Sandbox` | a handle by name, checked when used |
| `await sandbox.inspect() -> SandboxInfo` | its current state |
| `await sandbox.exists() -> bool` | whether it exists |

`SandboxInfo`: `id`, `name`, `agent`, `status` (`"running"`, `"stopped"` or
another daemon state; `is_running`), `created_at`, `last_used_at`,
`workspace`, `working_dir`, `effective_working_dir`, `cpus`, `memory`,
`host_mounts`, `runtime_mounts`, `ports` (filled in single-sandbox answers
only), `labels`, `credential_sources`.

### Life cycle

| Call | Behavior |
|---|---|
| `await sandbox.start(*, ssh_agent_socket=None) -> SandboxInfo` | starts it; idempotent; stops again ~30 s later without a session |
| `await sandbox.stop() -> SandboxInfo` | stops it now, sessions or not |
| `await sandbox.wait_running(timeout=60.0, interval=0.5) -> SandboxInfo` | polls until it runs, else `SandboxTimeoutError` |
| `await sandbox.delete(*, force=False, expected_id=None)` | deletes it; `force=True` stops it first; `expected_id` (from `Created.id`) refuses to delete a sandbox recreated under the same name (`ConflictError`) |
| `await sandbox.force_delete()` | `delete(force=True)` |

### Following a creation

`await client.sandboxes.create_stream(request) -> Stream[CreateEvent]` creates
from a `CreateRequest` and streams `CreateProgress(message)`, then
`CreateResult(created)` or `CreateFailure(message)` (a failure is an item, not
an exception), or `CreateUnknown(raw)` for a line the library does not know.
`await client.sandboxes.create(request) -> Created` waits for the result
instead. Both create from images already on the daemon: call
`await package.load_images(client)` first (`client.create()` does it for you).

`CreateRequest` (`from fastsandbox.models import CreateRequest`) is plain data,
from `package.request(name)`: fields `name`, `agent`, `kits`,
`kit_artifacts`, `pull_policy`, `template`, `cpus`, `memory`, `workspace`,
`additional_workspaces`, `clone`, `environment`, `ports`, `skills`, `profile`,
`mcp`…; builders `with_workspace(dir)`, `with_cloned_workspace(repository)`,
`with_additional_workspace(workspace)`, `with_port(port)`,
`with_env(**variables)`, `with_static_mcp_servers(*servers)`. Store it with
`model_dump_json()`, replay it with `CreateRequest.model_validate_json()` and
`client.create(request=...)`.

### Templates, working directory, host paths, metrics

| Call | What it does |
|---|---|
| `await sandbox.save(tag) -> SavedImage` | saves the sandbox as image `tag` (`image_id`, `tag`); stop it first |
| `client.create(template=tag, pull_policy=PullPolicy.NEVER)` | starts from the saved image (on this daemon only) |
| `await sandbox.set_working_dir(dir)` | working directory of new sessions |
| `await sandbox.allow_host_path(path)` / `revoke_host_path(path)` | grants or revokes access to an existing host path (listed in `runtime_mounts`; not a mount) |
| `await sandbox.vm_metrics() -> str` | VM metrics, Prometheus text format |

## Example

```python
import fastsandbox
from fastsandbox.models import PullPolicy, Workspace


async def main() -> None:
    client = await fastsandbox.connect()
    creation = client.create(
        "build-box",
        kit="shell",
        workspaces=[Workspace(dir="/srv/data", read_only=True, target="/data")],
        env={"MODE": "ci"},
        cpus=2,
        memory="4g",
    )
    sandbox = await creation
    assert creation.created is not None
    try:
        async with sandbox.running():
            await sandbox.exec(["ls", "/data"], check=True)
        await sandbox.stop()
        await sandbox.save("build-box:v1")
        async with client.create(
            kit="shell", template="build-box:v1", pull_policy=PullPolicy.NEVER
        ) as copy:
            print((await copy.inspect()).status)
    finally:
        await sandbox.delete(force=True, expected_id=creation.created.id)


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- An awaited creation is the program's to delete; a sandbox left without a
  session stops after ~30 s but stays on the daemon.
- `client.create()` returns a `Creation`: `await` it or use `async with`; do
  not `async with await client.create(...)`.
- A sandbox swapped by `KitPackage.add_to()` needs a new `running()` block.
- `workspace=` mounts the host directory read-write: changes reach the host
  during the run. Use `clone=True`, a read-only `Workspace` or an upload when
  the host must stay as it is.
- A name is free again once its sandbox is deleted.
