# Kits

A sandbox is created from a kit: `shell`, the kit of a coding agent, or a
composition of a base kit and mixins. The daemon cannot resolve a kit by
itself: the `sbx` CLI does, then sends the daemon what it resolved. A **kit
package** captures what the CLI sends for a kit, once; every later sandbox of
that kit is created from it through the socket alone. This page covers the
cache that compiles packages, compositions, packages themselves, and kits
added to a running sandbox.

## The kit cache

`client.create(kit="shell")` gets the package of the kit from the cache of the
client, [`client.kits`][fastsandbox.Client.kits], a
[`KitCache`][fastsandbox.KitCache]:

- a kit is compiled on first use, with the `sbx` CLI on `PATH`: the CLI runs
  `sbx create` once, on a throw-away sandbox, behind a proxy that captures what
  it sends. It can take a few minutes for an agent kit; the kit images it
  pulls stay on the daemon, as the cache of the next sandboxes;
- a package is compiled again when the daemon runs another `sbx` version than
  the one it was compiled with;
- the cache is in `~/.cache/fastsandbox/kits`, or under `$XDG_CACHE_HOME`;
  `FASTSANDBOX_KIT_CACHE` names another directory.

```python title="docs_src/client/kits.py" hl_lines="7 11"
--8<-- "docs_src/client/kits.py"
```

[`client.package(kit)`][fastsandbox.Client.package] gives the package of a
kit, compiled now unless cached; given a package, it returns it as it is. To
compile ahead of time, from a shell or a deployment script:

```sh
fastsandbox kits compile claude
fastsandbox kits compile shell --mixin ./kits/my-mixin --arg model=fast
```

## Compositions

A [`Kit`][fastsandbox.Kit] composes a `base` kit (an agent, `shell`, a kit
reference or the directory of a local kit) with `mixins`, in order, and kit
`args`, as `sbx create --kit-arg` takes them. Each composition is cached apart,
under its [`cache_key`][fastsandbox.Kit.cache_key].

```python
from fastsandbox import Kit

kit = Kit(base="shell", mixins=("./kits/my-mixin",), args={"model": "fast"})
sandbox = await client.create(kit=kit)
```

A kit the CLI cannot compile, an argument the kit does not declare for
instance, raises [`KitCompileError`][fastsandbox.exceptions.KitCompileError].
[`KitCompiler`][fastsandbox.KitCompiler] compiles into a directory of one's
choice, without the cache.

## Packages

A [`KitPackage`][fastsandbox.KitPackage] is a directory;
[`KitPackage.open(dir)`][fastsandbox.KitPackage.open] opens one, and raises
[`KitPackageError`][fastsandbox.exceptions.KitPackageError] when the directory
holds none. It records:

- `kit_refs`, the kit references, base kit first, and `kit_artifacts`, what
  the daemon receives for them;
- `compiled_with`, the `sbx` version it was compiled with;
- `images`, the image archives of the kits, which
  [`load_images(client)`][fastsandbox.KitPackage.load_images] loads into the
  daemon;
- `agent`, the [`KitAgent`][fastsandbox.KitAgent] the base kit describes, if
  any: its program, its run options, the command line that runs it
  ([`command(*args)`][fastsandbox.KitAgent.command]) and the hosts it needs
  ([`hosts()`][fastsandbox.KitAgent.hosts]).

[`request(name)`][fastsandbox.KitPackage.request] gives the creation request
of a sandbox of the kit, which [`create_with(client, request)`][fastsandbox.KitPackage.create_with]
creates once adjusted, loading the images first; `client.create()` does both.

## Kits added to a running sandbox

A package of a composition adds its mixins to a sandbox created from the base
kit alone, in one of two ways:

| Call | How | The kit list of the sandbox |
|---|---|---|
| [`install_into(sandbox)`][fastsandbox.KitPackage.install_into] | runs the install of the kits in the running container: fast | stays as it was, so a container created again would lose the kits |
| [`add_to(sandbox)`][fastsandbox.KitPackage.add_to] | commits the container to an image, then creates it again with the longer kit list: the work in progress is kept, the sandbox keeps its identity | holds the new kits |

After a swap, the new container needs a session of its own: open a new
`async with sandbox.running():` block. A program that composes kits itself
uses the parts of the package with
[`Sandbox.add_kit_artifact()`][fastsandbox.Sandbox.add_kit_artifact] and
[`Sandbox.swap_container()`][fastsandbox.Sandbox.swap_container].

## In tests

[`fastsandbox.testing.fake_package()`][fastsandbox.testing.fake_package]
writes a package that needs no `sbx` CLI, for the fake daemon (see
[Testing](../guides/testing.md)).
