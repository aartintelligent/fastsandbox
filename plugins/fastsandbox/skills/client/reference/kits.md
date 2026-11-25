# Kits

Full page: https://aartintelligent.github.io/fastsandbox/client/kits/

A sandbox is created from a kit: `shell`, the kit of a coding agent, or a
composition of a base kit and mixins. The daemon cannot resolve a kit itself:
the `sbx` CLI does. A **kit package** captures what the CLI sends for a kit,
once; every later sandbox of that kit is created through the socket alone.

## API

### `Kit` (frozen Pydantic model)

`Kit(base: str = "shell", mixins: tuple[str, ...] = (), args: dict[str, str] = {})`:
`base` is an agent (`claude`, `codex`…), `shell`, a kit reference or a local
kit directory; `mixins` are composed in order; `args` are kit arguments, as
`sbx create --kit-arg` takes them. `label` is a readable name, `cache_key` the
cache directory name. `client.create(kit=...)` accepts a name, a `Kit` or a
`KitPackage`.

### `KitCache`

`KitCache(directory=None, *, sbx="sbx", timeout=None)`;
`await cache.package(client, kit: Kit | str) -> KitPackage` compiles a
composition on first use and again when the daemon runs another `sbx` version
than the one it was compiled with. The directory is `$FASTSANDBOX_KIT_CACHE`,
else `$XDG_CACHE_HOME/fastsandbox/kits`, else `~/.cache/fastsandbox/kits`.
`client.kits` is the cache of a client; `await client.package(kit)` goes
through it (a `KitPackage` is returned as is).

### `KitCompiler`

`KitCompiler(client, *, sbx="sbx", work_dir=None, timeout=None)`;
`await compiler.compile(base, output, *, mixins=(), args=None) -> KitPackage`
compiles into the directory `output`, without the cache. It runs the `sbx`
CLI once on a throw-away sandbox behind a capturing proxy. Raises
`KitCompileError` (an argument the kit does not declare…).

### `KitPackage`

| Member | What it is |
|---|---|
| `KitPackage.open(dir)` | opens a compiled package; `KitPackageError` when `dir` holds none |
| `dir`, `compiled_with`, `kit_refs`, `kit_artifacts` | its directory, the `sbx` version, the kit references (base first), what the daemon receives |
| `images: list[PackageImage]` | its image archives (`path`, `reference`) |
| `agent: KitAgent \| None` | the agent the base kit describes |
| `request(name) -> CreateRequest` | the creation request of a sandbox of the kit |
| `await load_images(client) -> int` | loads its images into the daemon |
| `await create(client, name) -> Created` | loads the images and creates a sandbox |
| `await create_with(client, request) -> Created` | the same from an adjusted request |
| `await install_into(sandbox) -> int` | installs the kits in place in a running container (fast; the sandbox's kit list is unchanged, so a recreated container loses them) |
| `await add_to(sandbox) -> SwapOutcome` | commits the container and recreates it with the longer kit list, keeping work and identity |

### `KitAgent`

`KitAgent.from_artifact(artifact)`; `name`, `display_name`, `binary`,
`run_options`, `network`; `command(*args) -> list[str]` (the command line that
runs the agent), `hosts() -> list[str]` (the hosts it needs).

Lower level, for programs that compose kits themselves:
`await sandbox.add_kit_artifact(artifact)` and
`await sandbox.swap_container(request: SwapRequest) -> SwapOutcome`.

From a shell, ahead of a run:

```sh
fastsandbox kits compile claude
fastsandbox kits compile shell --mixin ./kits/my-mixin --arg model=fast
```

## Example

```python
import fastsandbox
from fastsandbox import Kit


async def main() -> None:
    client = await fastsandbox.connect()
    package = await client.package("shell")  # compiled with the sbx CLI on first use
    print(package.kit_refs, package.compiled_with)

    kit = Kit(base="shell", mixins=("./kits/my-mixin",), args={"model": "fast"})
    async with client.create(kit="shell") as sandbox, sandbox.running():
        composed = await client.package(kit)
        await composed.add_to(sandbox)  # the container is recreated
    claude = await client.package("claude")
    if claude.agent is not None:
        print(claude.agent.command("--version"), claude.agent.hosts())


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- The `sbx` CLI must be on `PATH` for the first use of a kit; the first
  compilation of an agent kit can take minutes. Compile ahead of time with
  `fastsandbox kits compile`.
- Each composition (base, mixins, args) is cached apart.
- After `add_to()`, the new container needs a session of its own: open a new
  `async with sandbox.running():` block.
- Tests use packages that need no `sbx` CLI (`fake_package()` of the testing
  module): load the testing skill.
