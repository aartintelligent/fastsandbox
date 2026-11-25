# Files

Files move between the host and a sandbox through the socket, as tar archives
the daemon extracts and builds. This page covers single files, whole
directories and archives. To give a sandbox a host directory without copying
it, mount it at creation instead (`workspace` and `workspaces`, see
[Creating a sandbox](sandboxes.md#creating-a-sandbox)).

```python title="docs_src/client/files.py" hl_lines="11 12 17 21"
--8<-- "docs_src/client/files.py"
```

The sandbox must run (see [Sessions](sandboxes.md#sessions)): a transfer to or
from a stopped sandbox raises
[`ConflictError`][fastsandbox.exceptions.ConflictError].

## Single files

- [`write_file(path, contents, mode=None)`][fastsandbox.Sandbox.write_file]
  writes a string (as UTF-8) or bytes to the absolute `path`, replacing an
  existing file. Files are created as root, with mode `0644` unless `mode`
  says otherwise (`0o755` for a script).
- [`read_file(path)`][fastsandbox.Sandbox.read_file] reads a regular file as
  bytes; [`read_text(path, encoding="utf-8")`][fastsandbox.Sandbox.read_text]
  decodes it.

!!! warning "The directory must exist"
    The daemon extracts into an existing directory. A file written into a
    directory that does not exist fails with a server error
    ([`ApiError`][fastsandbox.exceptions.ApiError], status 500): create the
    directory first, with `sandbox.exec(["mkdir", "-p", dir])`.

Reading a path that does not exist raises
[`NotFoundError`][fastsandbox.exceptions.NotFoundError]; reading a directory
with `read_file()`, [`ArchiveError`][fastsandbox.exceptions.ArchiveError].

## Directories

- [`upload_dir(host_dir, dir)`][fastsandbox.Sandbox.upload_dir] copies a host
  directory into the existing directory `dir` of the sandbox, **under its own
  name**: `upload_dir("./project", "/work")` gives `/work/project/...`.
  Symbolic links are copied as links.
- [`download_dir(path, host_dir)`][fastsandbox.Sandbox.download_dir] copies a
  directory or a file of the sandbox into `host_dir`, created when missing,
  under its own name too: `download_dir("/work/out", "./results")` gives
  `./results/out/...`. Entries that would land outside `host_dir` are skipped.

A host directory that cannot be read, or written, raises
[`HostFileError`][fastsandbox.exceptions.HostFileError], an `OSError` with the
`path`.

## Archives

A program that stores or streams archives itself moves them as they are:

- [`download_archive(path)`][fastsandbox.Sandbox.download_archive] gives a tar
  archive of `path`, its entries named after the last component of the path;
- [`upload_archive(dir, archive)`][fastsandbox.Sandbox.upload_archive] extracts
  a tar archive into the existing directory `dir`.

To copy the contents of a directory without its name, send an archive of
those contents with `upload_archive()`.

```python
archive = await sandbox.download_archive("/work/project")  # entries: project/...
await sandbox.exec(["mkdir", "-p", "/backup"], check=True)
await sandbox.upload_archive("/backup", archive)  # /backup/project/...
```
