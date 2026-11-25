# Files

Full page: https://aartintelligent.github.io/fastsandbox/client/files/

Files move through the socket as tar archives the daemon extracts and builds.
The sandbox must run: a transfer with a stopped sandbox raises
`ConflictError`. To share a host directory without copying it, mount it at
creation (`workspace`, `workspaces`, see [sandboxes](sandboxes.md)).

## API

| Call | What it does |
|---|---|
| `await sandbox.write_file(path, contents: bytes \| str, *, mode: int \| None = None)` | writes a string (UTF-8) or bytes to the absolute `path`, replacing a file; created as root, mode `0644` unless `mode` (e.g. `0o755`) |
| `await sandbox.read_file(path) -> bytes` | reads a regular file |
| `await sandbox.read_text(path, encoding="utf-8") -> str` | reads and decodes it |
| `await sandbox.upload_dir(host_dir, dir)` | copies a host directory into the existing `dir`, **under its own name**: `upload_dir("./project", "/work")` gives `/work/project/...`; symlinks copied as links |
| `await sandbox.download_dir(path, host_dir)` | copies a directory or file of the sandbox into `host_dir` (created when missing), under its own name: `download_dir("/work/out", "./results")` gives `./results/out/...`; entries escaping `host_dir` are skipped |
| `await sandbox.download_archive(path) -> bytes` | a tar archive of `path`, entries named after its last component |
| `await sandbox.upload_archive(dir, archive: bytes)` | extracts a tar archive into the existing `dir` |

| Error | When |
|---|---|
| `ApiError` (status 500) | writing into a directory that does not exist: create it first |
| `NotFoundError` | reading a path that does not exist |
| `ArchiveError` | `read_file()` on a directory; an archive that cannot be built or extracted |
| `HostFileError` (an `OSError`, with `path`) | a host directory that cannot be read or written |
| `ConflictError` | the sandbox is stopped |

## Example

```python
import sys
from pathlib import Path

import fastsandbox


async def main(project: Path) -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        await sandbox.exec(["mkdir", "-p", "/work"], check=True)
        await sandbox.write_file("/work/check.sh", '#!/bin/sh\nls -R "$1"\n', mode=0o755)
        await sandbox.upload_dir(project, "/work")
        await sandbox.exec(["/work/check.sh", f"/work/{project.name}"], check=True)
        print(await sandbox.read_text("/work/check.sh"), end="")
        await sandbox.download_dir(f"/work/{project.name}", project.parent / "results")


if __name__ == "__main__":
    fastsandbox.run(main(Path(sys.argv[1])))
```

## Gotchas

- The target directory must exist: `exec(["mkdir", "-p", dir], check=True)`
  first; the daemon answers a missing one with a 500, which a retry does not
  fix.
- To copy the contents of a directory without its name, send an archive of
  those contents with `upload_archive()`.
- Files written by `write_file()` belong to root; `chown` them with `exec()`
  when the kit's user must write them.
- Paths in the sandbox are absolute; host paths accept `str` or `PathLike`.
