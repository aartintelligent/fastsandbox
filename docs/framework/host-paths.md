# Host paths

A task often works on files of the host: a repository to test, data to read, a
project for an agent to change. Three markers, given in `Annotated` on a `Path`
input, tell FastSandbox what to do with the directory the caller passes:
[`WorkspaceDir`][fastsandbox.WorkspaceDir] mounts it as the workspace of the
sandbox, [`Mounted`][fastsandbox.Mounted] mounts it as a further directory, and
[`Uploaded`][fastsandbox.Uploaded] copies its contents in. This page covers the
three, and clone mode.

## Mounting and copying

```python title="docs_src/tasks/host_paths.py" hl_lines="12-14 18"
--8<-- "docs_src/tasks/host_paths.py"
```

```sh
fastsandbox run docs_src/tasks/host_paths.py inventory --repo . --data ~/datasets --fixtures tests/fixtures
```

| Marker | What happens to the directory | Inside the sandbox | Changes made in the sandbox |
|---|---|---|---|
| `WorkspaceDir()` | Mounted as the workspace, read-write | At its own absolute path | Reach the host |
| `Mounted(target, read_only=False)` | Mounted as a further directory, or file | At `target`, else at its own absolute path | Reach the host, unless `read_only=True` |
| `Uploaded(target)` | Its contents copied before the task runs | Under `target` | Stay in the sandbox |

- A task has at most one `WorkspaceDir`: a run with two raises
  [`TaskError`][fastsandbox.exceptions.TaskError].
- The paths are expanded (`~`) and resolved to absolute paths on the host
  before they are mounted or copied.
- The parameter keeps the value the caller gave: a relative path such as `.`
  stays relative. To name the workspace inside the sandbox, use its absolute
  path, `repo.resolve()`, as `inventory` does.
- `Uploaded` creates `target` as root, owned by the default user of the kit, so
  that it may lie where that user cannot write, such as `/work`. The copy is the
  sandbox's own, and goes with it.
- An input whose value is `None`, for an optional `Path | None = None`, is
  neither mounted nor copied.

!!! warning "Mounts are shared with the host"
    What the task, or an agent, changes in a mounted directory changes the
    files of the host, during the run. Use `Uploaded`, `Mounted(...,
    read_only=True)` or clone mode when the host must stay as it is.

## Clone mode

`WorkspaceDir(clone=True)` gives the sandbox a private clone of the Git
repository of the directory, with its history, at the same path, instead of the
directory itself; the repository of the host is mounted read-only at
`/run/sandbox/source`. The sandbox can change and commit what it likes, the
repository of the host stays as it was.

The clone goes with the sandbox when the run ends: what the task wants to keep
must leave as its result. Here an agent fixes an issue on the clone, and the
task returns its commits as a patch, for the caller to review and apply with
`git am`:

```python title="docs_src/agents/propose_patch.py" hl_lines="11 15 18-22"
--8<-- "docs_src/agents/propose_patch.py"
```

[`client.create(workspace=..., clone=True)`][fastsandbox.Client.create] gives
the same mode to a sandbox created with the client; the `shell-clone` example
of the repository also fetches the commits of a clone from the host with Git.
