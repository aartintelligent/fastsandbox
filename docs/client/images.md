# Images

The daemon holds the images sandboxes start from: those of the kits, and the
templates saved from sandboxes. [`client.images`][fastsandbox.Images] lists,
pulls, reads, moves and removes them. This page covers each of those.

```python title="docs_src/client/images.py" hl_lines="7 12 18 20"
--8<-- "docs_src/client/images.py"
```

## Listing and reading

| Call | Gives |
|---|---|
| [`list()`][fastsandbox.Images.list] | every image, untagged ones included, as [`ImageSummary`][fastsandbox.models.ImageSummary]; [`reference`][fastsandbox.models.ImageSummary.reference] names it |
| [`exists(reference)`][fastsandbox.Images.exists] | whether the daemon holds it |
| [`inspect(reference)`][fastsandbox.Images.inspect] | its details, an [`ImageInspect`][fastsandbox.models.ImageInspect]: user, entrypoint, command, agent; [`NotFoundError`][fastsandbox.exceptions.NotFoundError] for an image the daemon does not hold |
| [`local_metadata(reference)`][fastsandbox.Images.local_metadata] | whether it is a locally saved snapshot; an unknown image gives the defaults, not an error |

## Pulling

- [`pull(reference)`][fastsandbox.Images.pull] pulls an image and waits for
  the outcome. A pull the registry refuses raises an
  [`ApiError`][fastsandbox.exceptions.ApiError], such as `403
  registry_access_denied`; a failure reported during the pull, an
  [`OperationFailedError`][fastsandbox.exceptions.OperationFailedError]. When
  the registry refuses a pull, a cached copy is used, as the CLI does.
- [`pull_stream(reference)`][fastsandbox.Images.pull_stream] pulls it and
  streams its progress, a [`PullProgress`][fastsandbox.models.PullProgress]
  per line: a `status`, the layer `id`, the byte counts of `progress_detail`,
  and an `error`, always the last line of a failed pull. Layers report the same
  status many times.

Pulls are long operations: their deadline is the long-operation deadline of
the client (see [Deadlines](index.md#deadlines)). The images of a kit are
loaded from its package when a sandbox is created; they need no pull.

## Moving images

An image moves between daemons as an archive, in the `docker save` format:

- [`export(reference)`][fastsandbox.Images.export] gives the archive as bytes
  ([`NotFoundError`][fastsandbox.exceptions.NotFoundError] for an unknown
  image);
- [`load(archive)`][fastsandbox.Images.load] loads one from bytes, and
  [`load_file(path)`][fastsandbox.Images.load_file] from a file of the host;
- [`remove(reference)`][fastsandbox.Images.remove] removes an image.

A template saved from a sandbox (see [Templates](sandboxes.md#templates))
goes to another host this way:

```python
archive = await client.images.export("my-snapshot:v1")
Path("my-snapshot.tar").write_bytes(archive)
# On the other host:
await other.images.load_file("my-snapshot.tar")
```
