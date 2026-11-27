# Kits

A sandbox is created from a kit: `shell`, the kit of a coding agent, or a
composition of a base kit and mixins. The daemon cannot resolve a kit by
itself: a **kit package** holds what the `sbx` CLI would send it for a kit,
and every sandbox of that kit is created from it through the socket alone.
fastsandbox forges packages without the CLI, the base kit rebuilt from its
published image; it compiles them with the CLI only when asked. This page
covers the cache that makes packages, compositions, packages themselves, and
kits added to a running sandbox.

## The kit cache

`client.create(kit="shell")` gets the package of the kit from the cache of the
client, [`client.kits`][fastsandbox.Client.kits], a
[`KitCache`][fastsandbox.KitCache]: by default the one of the process
([`KitCache.default()`][fastsandbox.KitCache.default]), shared by its clients.

- A kit is forged on first use, without the `sbx` CLI: the daemon pulls and
  exports the published image of the base kit, `docker.io/sbx/shell` for
  `shell`, and the forge rebuilds the kit from it. It takes a few seconds once
  the daemon holds the image.
- The package is kept in memory for the process: nothing is written on the
  host. A later process forges it again.
- `KitCache(directory)`, or `FASTSANDBOX_KIT_CACHE`, keeps the packages in a
  directory instead, for later processes too. A forged package is used again
  while the daemon speaks the API it was forged for.

```python title="docs_src/client/kits.py" hl_lines="7 11"
--8<-- "docs_src/client/kits.py"
```

[`client.package(kit)`][fastsandbox.Client.package] gives the package of a
kit, made now unless kept; given a package, it returns it as it is.

### Compiling with the CLI

The forge rebuilds published kits and reads mixins from their directories. A
kit only the CLI resolves raises
[`KitForgeError`][fastsandbox.exceptions.KitForgeError]: the directory of a
local base kit, or a mixin given by reference. A cache given the `sbx` program
compiles kits with it instead:

```python
from fastsandbox import KitCache

package = await KitCache(sbx="sbx").package(client, "./kits/my-local-kit")
sandbox = await client.create(kit=package)
```

A FastSandbox application takes such a cache as `FastSandbox(kits=KitCache(sbx="sbx"))`.
The CLI runs `sbx create` once, on a throw-away sandbox, behind a proxy that
captures what it sends. It can take a few minutes for an agent kit; the kit
images it pulls stay on the daemon, as the cache of the next sandboxes. Such a
cache keeps its packages in `~/.cache/fastsandbox/kits`, or under
`$XDG_CACHE_HOME`, unless given a directory, and compiles a package again when
the daemon runs another `sbx` version. To compile ahead of time, from a shell
or a deployment script:

```sh
fastsandbox kits compile claude
fastsandbox kits compile shell --mixin ./kits/my-mixin --arg model=fast
```

## Compositions

A [`Kit`][fastsandbox.Kit] composes a `base` kit with `mixins`, in order, and
kit `args`, as `sbx create --kit-arg` takes them. The base is an agent or
`shell`, a published kit reference, or, for the CLI only, the directory of a
local kit; a mixin is a directory, whose `spec.yaml` the forge reads when it
is written in the JSON subset of YAML. Each composition is kept apart, under
its [`cache_key`][fastsandbox.Kit.cache_key].

```python
from fastsandbox import Kit

kit = Kit(base="shell", mixins=("./kits/my-mixin",), args={"model": "fast"})
sandbox = await client.create(kit=kit)
```

The forge checks the arguments as the CLI does: an argument the kit does not
declare, or a value it refuses, raises
[`InvalidKitError`][fastsandbox.exceptions.InvalidKitError] before anything
is created, as does a mixin it cannot take. [`KitForge`][fastsandbox.KitForge]
forges without the cache, in memory or into a directory of one's choice;
[`KitCompiler`][fastsandbox.KitCompiler] compiles with the CLI, and raises
[`KitCompileError`][fastsandbox.exceptions.KitCompileError] when the CLI
cannot.

## Packages

A [`KitPackage`][fastsandbox.KitPackage] is held in memory, or is a directory;
[`KitPackage.open(dir)`][fastsandbox.KitPackage.open] opens one, and raises
[`KitPackageError`][fastsandbox.exceptions.KitPackageError] when the directory
holds none. It records:

- `kit_refs`, the kit references, base kit first, and `kit_artifacts`, what
  the daemon receives for them;
- `dir`, its directory, `None` for a package held in memory;
- `compiled_with`, the `sbx` version that compiled it, `None` for a forged
  package, and `compiled_api`, the daemon API it was written for;
- `images`, the image archives of the kits, which
  [`load_images(client)`][fastsandbox.KitPackage.load_images] loads into the
  daemon; those of a package held in memory have no path;
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

The fake daemon serves the published kits `shell` and `claude`, so that kits
are forged against it as against the daemon;
[`fastsandbox.testing.fake_package()`][fastsandbox.testing.fake_package]
writes a package of one's own (see [Testing](../guides/testing.md)).
