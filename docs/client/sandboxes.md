# Sandboxes

A sandbox is a virtual machine the daemon creates from a kit: the `shell` kit,
or the kit of a coding agent. This page covers its life: the creation, the
sessions that keep it running, looking it up, stopping and deleting it, and
saving it as a template.

## Creating a sandbox

[`client.create()`][fastsandbox.Client.create] creates a sandbox from a kit,
`shell` by default, compiled on first use (see [Kits](kits.md)). It returns a
[`Creation`][fastsandbox.Creation], used in one of two ways:

- **awaited**, it gives the [`Sandbox`][fastsandbox.Sandbox], which stays until
  it is deleted;
- **as an async context manager**, it gives the sandbox and deletes it on the
  way out, also on an error or a cancellation: stopped if it runs, then
  deleted.

```python title="docs_src/client/create.py" hl_lines="8 9 14"
--8<-- "docs_src/client/create.py"
```

Once created, [`Creation.created`][fastsandbox.Creation] holds what the daemon
answered, a [`Created`][fastsandbox.models.Created]: the identifier of the
sandbox, its agent, its state and its MCP gateway. A sandbox runs right after
its creation.

The arguments adjust the creation request of the kit:

| Argument | What it sets |
|---|---|
| `name` | The sandbox name; a unique one by default ([`unique_name()`][fastsandbox.unique_name], `fastsandbox-` and a random suffix). |
| `kit` | The kit: a name (`"shell"`, `"claude"`…), a [`Kit`][fastsandbox.Kit] or a [`KitPackage`][fastsandbox.KitPackage]; `None` to create from `request` alone. |
| `request` | A full [`CreateRequest`][fastsandbox.models.CreateRequest]; the other arguments adjust it. |
| `workspace` | A host directory mounted as workspace, at its own path in the sandbox. |
| `clone` | The sandbox works on a private Git clone of `workspace`, the repository of the host mounted read-only. |
| `workspaces` | Further host directories or files to mount, as [`Workspace`][fastsandbox.models.Workspace] (`dir`, `read_only`, `target`). |
| `env` | Environment variables of the sandbox. |
| `ports` | Ports published from the start (see [Ports](ports.md)). |
| `cpus`, `memory` | Virtual CPUs and a memory limit in `sbx` notation, e.g. `"4g"`. |
| `template` | An image to start from, such as one saved with [`Sandbox.save()`][fastsandbox.Sandbox.save]. |
| `pull_policy` | When kit images are pulled: [`PullPolicy`][fastsandbox.models.PullPolicy] `ALWAYS`, `MISSING` or `NEVER`. |

A name already in use raises
[`ConflictError`][fastsandbox.exceptions.ConflictError]; a request the daemon
refuses, an unknown governance `profile` for instance,
[`InvalidInputError`][fastsandbox.exceptions.InvalidInputError], before
anything is created.

## Sessions

The daemon stops a sandbox about 30 seconds after its last session closes. A
session is an open request on the sandbox, which the `sbx` CLI holds for the
duration of each of its commands: a program that works in a sandbox holds one
too.

```python title="docs_src/client/sessions.py" hl_lines="11 16 20"
--8<-- "docs_src/client/sessions.py"
```

- [`sandbox.running()`][fastsandbox.Sandbox.running] starts the sandbox if
  needed and keeps it running for the duration of the block. It is the way to
  work in a sandbox: `async with client.create(...) as sandbox,
  sandbox.running():`.
- [`ensure_running()`][fastsandbox.Sandbox.ensure_running] does the same
  outside a block: it opens a session, pushes an empty credentials update and
  starts the sandbox, as the CLI does, and returns the
  [`Session`][fastsandbox.Session]. Release it with
  [`release()`][fastsandbox.Session.release], or use it as an async context
  manager.
- [`hold_session()`][fastsandbox.Sandbox.hold_session] opens a session without
  starting the sandbox: it keeps a running sandbox running.

A session closed by the daemon is opened again on its own, until it is
released or the sandbox no longer exists;
[`Session.is_connected`][fastsandbox.Session.is_connected] says whether it is
open right now. A command sent to a stopped sandbox raises
[`ConflictError`][fastsandbox.exceptions.ConflictError].

!!! note
    A sandbox created and left without a session keeps running for about
    30 seconds, then stops. It stays on the daemon, stopped, until it is
    deleted: a creation that is awaited is the program's to delete.

## Looking sandboxes up

| Call | Gives |
|---|---|
| [`client.sandboxes.list()`][fastsandbox.Sandboxes.list] | every sandbox, as [`SandboxInfo`][fastsandbox.models.SandboxInfo] |
| [`client.sandboxes.get(name)`][fastsandbox.Sandboxes.get] | one sandbox, or [`NotFoundError`][fastsandbox.exceptions.NotFoundError] |
| [`client.sandboxes.find(name)`][fastsandbox.Sandboxes.find] | one sandbox, or `None` |
| [`client.sandbox(name)`][fastsandbox.Client.sandbox] | the handle of a sandbox, by name; nothing is checked until it is used |
| [`sandbox.inspect()`][fastsandbox.Sandbox.inspect] | the current state of the sandbox |
| [`sandbox.exists()`][fastsandbox.Sandbox.exists] | whether it exists |

[`SandboxInfo`][fastsandbox.models.SandboxInfo] carries the identifier, the
agent of the kit, the `status` (`running`, `stopped`, or another state the
daemon reports) and [`is_running`][fastsandbox.models.SandboxInfo.is_running],
the workspace and mounts, the CPUs and memory set at creation, the published
ports (in single-sandbox answers only) and the service credentials configured.

## Starting, stopping, deleting

- [`start()`][fastsandbox.Sandbox.start] starts the sandbox; starting a running
  sandbox does nothing. Without a session, it stops again about 30 seconds
  later.
- [`stop()`][fastsandbox.Sandbox.stop] stops it at once, sessions or not.
- [`wait_running()`][fastsandbox.Sandbox.wait_running] polls until the sandbox
  runs, every `interval` seconds for at most `timeout` (0.5 s and 60 s by
  default), then raises
  [`SandboxTimeoutError`][fastsandbox.exceptions.SandboxTimeoutError].
- [`delete()`][fastsandbox.Sandbox.delete] deletes it; `force=True` stops it
  first when it runs. [`force_delete()`][fastsandbox.Sandbox.force_delete] is
  `delete(force=True)`.

A name is free again once its sandbox is deleted. `expected_id`, the
identifier returned at creation, guards a deletion against a sandbox that
someone else recreated under the same name: the daemon refuses it with a
[`ConflictError`][fastsandbox.exceptions.ConflictError].

```python
await sandbox.delete(force=True, expected_id=created.id)
```

## Following a creation

[`client.sandboxes.create_stream()`][fastsandbox.Sandboxes.create_stream]
creates a sandbox from a [`CreateRequest`][fastsandbox.models.CreateRequest]
and streams what the daemon does. Each item is a
[`CreateEvent`][fastsandbox.models.CreateEvent]: progress lines
([`CreateProgress`][fastsandbox.models.CreateProgress]), then the result
([`CreateResult`][fastsandbox.models.CreateResult]) or the failure
([`CreateFailure`][fastsandbox.models.CreateFailure]). A failure is an item of
the stream, not an exception: the daemon answers it with HTTP 200.

```python title="docs_src/client/create_stream.py" hl_lines="9 10 12"
--8<-- "docs_src/client/create_stream.py"
```

The request comes from the kit package,
[`KitPackage.request(name)`][fastsandbox.KitPackage.request], adjusted with the
`with_*` methods of the request or `model_copy(update=...)`. Unlike
`client.create()`, the collection creates from images already on the daemon:
load those of the package first, with
[`load_images()`][fastsandbox.KitPackage.load_images].
[`client.sandboxes.create()`][fastsandbox.Sandboxes.create] takes the same
request and waits for the result instead.

A creation request is plain data: an application can store it as JSON, with
`model_dump_json()`, and replay it under another name with
`CreateRequest.model_validate_json()` and `client.create(request=...)`.

## Templates

[`sandbox.save(tag)`][fastsandbox.Sandbox.save] saves a sandbox as an image,
the template of new sandboxes; stop it first, so that its file system is at
rest. A new sandbox starts from it with `template`; the image is on this
daemon only, so it is not pulled:

```python
from fastsandbox.models import PullPolicy

await sandbox.stop()
saved = await sandbox.save("my-snapshot:v1")
copy = await client.create(kit="shell", template="my-snapshot:v1", pull_policy=PullPolicy.NEVER)
```

[`SavedImage`][fastsandbox.models.SavedImage] holds the identifier of the image
and its fully qualified tag. An image moves to another daemon as a file:
[`client.images.export()`][fastsandbox.Images.export] then
[`load_file()`][fastsandbox.Images.load_file] there (see [Images](images.md)).

## Working directory, host paths, metrics

- [`set_working_dir(dir)`][fastsandbox.Sandbox.set_working_dir] sets the
  working directory of new sessions; `SandboxInfo.working_dir` records it.
- [`allow_host_path(path)`][fastsandbox.Sandbox.allow_host_path] grants a
  running sandbox access to an existing path of the host, by its real path,
  and [`revoke_host_path(path)`][fastsandbox.Sandbox.revoke_host_path] takes it
  back. A grant is listed with the `runtime_mounts` of the sandbox; it is not a
  mount. To mount directories, use `workspace` and `workspaces` at creation.
- [`vm_metrics()`][fastsandbox.Sandbox.vm_metrics] gives the metrics of the
  virtual machine, in the Prometheus text format.
