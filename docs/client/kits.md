# Kits

A sandbox is created from a kit: `shell`, the kit of a coding agent, or a
composition of a base kit and mixins. The daemon cannot resolve a kit by
itself: a **kit package** holds what the `sbx` CLI would send it for a kit,
and every sandbox of that kit is created from it through the socket alone.
fastsandbox forges packages without the CLI, the base kit rebuilt from its
published image; it compiles them with the CLI only when asked. This page
covers the cache that makes packages, compositions, mixins written in Python,
MCP servers given to the agent by a mixin, packages themselves, and kits added
to a running sandbox.

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
is written in the JSON subset of YAML, or a mixin
[written in Python](#mixins-written-in-python). Each composition is kept
apart, under its [`cache_key`][fastsandbox.Kit.cache_key].

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

## Mixins written in Python

A mixin need not be a directory. A [`KitDescriptor`][fastsandbox.KitDescriptor]
holds what it declares, the v3 descriptor of its `spec.yaml`, built in Python;
a [`Mixin`][fastsandbox.Mixin] lists it under a reference, and `Kit.mixins`
takes it as it takes a directory:

```python title="docs_src/client/kit_mixins.py" hl_lines="4-15"
--8<-- "docs_src/client/kit_mixins.py"
```

- A [`LifecycleStep`][fastsandbox.LifecycleStep] is a command, a shell command
  or a program and its arguments: run once, when the sandbox is created
  (`with_install`), or at each of its starts (`with_startup`, in the
  background with `in_background()`), as a user of the sandbox (`as_user`).
  An install command runs in an emptied environment, which keeps only the
  proxy and certificate variables: `with_env(*names)` gives it variables of
  the sandbox, `with_gateway_env()` those that name its MCP gateway.
- `with_network_allow(*hosts)` and `with_network_deny(*hosts)` add rules while
  the sandbox runs, each host in a form the CLI takes (`host`, `*.domain`,
  `host:port`, a CIDR prefix); a deny wins over any allow.
- The models hold the format field for field, under the names it gives its
  fields: `model_dump_json()` is the descriptor as any program reads it, and
  [`to_spec()`][fastsandbox.KitDescriptor.to_spec] the text of its
  `spec.yaml`, which the CLI reads too.
  [`KitDescriptor.parse()`][fastsandbox.KitDescriptor.parse], `read()` and
  `from_json()` read a descriptor, [`Mixin.read(dir)`][fastsandbox.Mixin.read]
  the mixin of a directory.
- A mixin is checked when it is made, by the rules of the forge, which
  `docker-sandbox-kit` holds: a host the CLI refuses, a URL or a path in place
  of a host, a command without a word, an install command in the background,
  a field the format does not have, or a kit argument raise
  [`InvalidKitError`][fastsandbox.exceptions.InvalidKitError] where the mixin
  is written, not when a sandbox is created from it.
- The reference is a path, as the CLI lists a local kit, whose last part names
  the mixin: the kit list of the sandbox shows it. The daemon finds the mixin
  by its image, so the path need not exist. A cache given the CLI writes the
  mixin into a directory named after it, for the CLI, which lists the mixin
  under that directory.

### MCP servers for the agent

[`Mixin.mcp(agent, *servers)`][fastsandbox.Mixin.mcp] is a mixin the crate
builds: it registers [`McpServer`][fastsandbox.McpServer]s in the
configuration of the agent when the sandbox is created, `claude mcp add` for
Claude Code, the one agent it has an adapter for, and allows their hosts. A
server of the host ([`McpServer.host(name, port)`][fastsandbox.McpServer.host])
is reached from the sandbox at `host.docker.internal`, with a bearer token the
creation request gives:

```python
from fastsandbox import Kit, McpServer, Mixin

tools = McpServer.host("project-tools", 47813)
kit = Kit(base="claude", mixins=(Mixin.mcp("claude", tools),))
sandbox = await client.create(kit=kit, env=tools.env(token))
```

See [Give it tools](../agents/tools.md#a-server-given-by-a-mixin) for the
token, the remote servers and what the server of the host is to accept.

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
