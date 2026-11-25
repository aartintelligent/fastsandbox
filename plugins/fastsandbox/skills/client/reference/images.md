# Images

Full page: https://aartintelligent.github.io/fastsandbox/client/images/

The daemon holds the images sandboxes start from: those of the kits, and
templates saved from sandboxes. `client.images` is an `Images` handle.

## API

| Call | Gives |
|---|---|
| `await list() -> list[ImageSummary]` | every image, untagged ones included: `repository`, `tag`, `id`, `digest`, `size`, `created_at`, `agent`, `reference` |
| `await exists(reference) -> bool` | whether the daemon holds it |
| `await inspect(reference) -> ImageInspect` | `id`, `agent`, `cmd`, `entrypoint`, `user`, `created_at`; `NotFoundError` when unknown |
| `await local_metadata(reference) -> LocalImageMetadata` | `local_snapshot`; an unknown image gives the defaults, not an error |
| `await pull(reference)` | pulls and waits; `ApiError` when the registry refuses (e.g. 403 `registry_access_denied`), `OperationFailedError` for a failure reported during the pull |
| `await pull_stream(reference) -> Stream[PullProgress]` | pulls, streaming `PullProgress`: `status`, layer `id`, `progress_detail` (`current`, `total`), `error` (always the last line of a failed pull) |
| `await export(reference) -> bytes` | the image as a `docker save` archive; `NotFoundError` when unknown |
| `await load(archive: bytes)` | loads an archive |
| `await load_file(path)` | loads an archive from a host file |
| `await remove(reference)` | removes the image |

## Example

```python
from pathlib import Path

import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    images = client.images
    for image in await images.list():
        print(image.reference, image.size or 0)

    reference = "docker.io/sbx/shell:latest"
    async with await images.pull_stream(reference) as progress:
        async for line in progress:
            if line.error is not None:
                raise RuntimeError(f"pull failed: {line.error}")
            print(line.status)

    details = await images.inspect(reference)
    print(details.user, details.entrypoint)

    # A saved template moves to another daemon as a file.
    Path("snapshot.tar").write_bytes(await images.export(reference))


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- Pulls use the long-operation deadline of the client (15 min by default).
- When the registry refuses a pull, a cached copy is used, as the CLI does.
- The images of a kit are loaded from its package at creation: they need no
  pull.
- A pull stream reports the same layer status many times: show progress, do
  not count lines.
- A saved template is on this daemon only: `export()` it, then `load_file()`
  it on another daemon.
