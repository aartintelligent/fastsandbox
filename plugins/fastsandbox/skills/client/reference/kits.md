# Kits

Full page: https://aartintelligent.github.io/fastsandbox/client/kits/

A sandbox is created from a kit: `shell`, the kit of a coding agent, or a
composition of a base kit and mixins. The daemon cannot resolve a kit itself:
a **kit package** holds what the `sbx` CLI would send for a kit, and every
sandbox of that kit is created from it through the socket alone. fastsandbox
forges packages without the CLI, the base kit rebuilt from its published
image; it compiles them with the CLI only when asked.

## API

### `Kit` (frozen Pydantic model)

`Kit(base: str = "shell", mixins: tuple[str, ...] = (), args: dict[str, str] = {})`:
`base` is an agent (`claude`, `codex`…), `shell`, a published kit reference
(`docker.io/sbx/claude:latest`), or, for the CLI only, a local kit directory;
`mixins`, composed in order, are directories, whose `spec.yaml` the forge reads
in the JSON subset of YAML, or `Mixin`s written in Python; `args` are kit
arguments, as `sbx create --kit-arg` takes them. `label` is a readable name, `cache_key` the cache directory name.
`client.create(kit=...)` accepts a name, a `Kit` or a `KitPackage`.

### `KitCache`

`KitCache(directory=None, *, sbx=None, timeout=None)`;
`await cache.package(client, kit: Kit | str) -> KitPackage` makes a
composition on first use and keeps it:

- by default it forges the kit without the CLI (`KitForge`) and keeps the
  package in memory for the process: nothing is written on the host;
- with a `directory` (or `$FASTSANDBOX_KIT_CACHE`), it keeps the packages
  there, for later processes too, and uses one again while the daemon speaks
  the API it was forged for;
- with `sbx="sbx"`, it compiles with the CLI (`KitCompiler`) into its
  directory, `~/.cache/fastsandbox/kits` unless given one, and compiles again
  when the daemon runs another `sbx` version.

`KitCache.default()` is the cache of the process, shared by the clients given
none; `client.kits` is the cache of a client; `await client.package(kit)` goes
through it (a `KitPackage` is returned as is).

### Mixins written in Python (`fastsandbox.mixins`)

Frozen Pydantic models of the v3 descriptor of a mixin, its `spec.yaml`, field
for field under the names of the format: `model_dump_json()` is the descriptor
any program reads, `to_spec()` the text of its `spec.yaml`.

| Member | What it is |
|---|---|
| `LifecycleStep(command=str \| tuple[str, ...], user=, description=, env=, background=)` | a command, a shell command or a program and its arguments; `as_user(user)`, `with_description(text)`, `with_env(*names)`, `with_gateway_env()` (`MCP_GATEWAY_URL`, `MCP_SENTINEL_TOKEN_NAME`), `in_background()` (startup only) |
| `KitDescriptor.mixin(display_name)` | an empty mixin; `with_description`, `with_version`, `with_install(step)` (once, at creation), `with_startup(step)` (each start), `with_network_allow(*hosts)`, `with_network_deny(*hosts)` |
| `KitDescriptor.parse(text)`, `read(path)`, `from_json(value)` | a descriptor read and checked by the crate; `to_json()`, `to_spec()` |
| `Mixin(reference=, descriptor=)` | a descriptor listed under a path whose last part, `name`, names the mixin (`/kits/acme-tools`); need not exist. Checked as it is made: `InvalidKitError` |
| `Mixin.read(dir)` | the mixin of a directory, under its canonical path |
| `Mixin.mcp(agent, *servers)` | the mixin, built by the crate, that registers `McpServer`s in the agent at creation (`claude mcp add`, as `agent`) and allows their hosts; `claude` only, reference `/kits/docker-sandbox-mcp-claude` |
| `McpServer.host(name, port)` | a server of the host on a loopback port, reached at `http://host.docker.internal:<port>/mcp`; its bearer token in `token_env`, `DOCKER_SANDBOX_MCP_<NAME>_TOKEN` |
| `McpServer.remote(name, url)` | a remote server the agent calls; `with_bearer_env(env)` sends the variable `env` as its bearer |
| `server.env(token) -> dict[str, str]` | the variable of the creation request that gives the server its token (`ValueError` without `token_env`) |

`capabilities` holds `LifecycleCapability` (`config: LifecycleConfig`,
`install`, `startup`) and `NetworkCapability` (`config: NetworkConfig`,
`runtime` and `install` `NetworkRules`, `allow`, `deny`).

### `KitForge`

`KitForge(client)`; `await forge.forge(kit: Kit | str, output=None) -> KitPackage`
forges in memory, or into the directory `output`, without the cache. The
daemon pulls and exports the published image of the base kit. Raises
`KitForgeError` for a kit only the CLI resolves (a local base kit, a mixin
given by reference) or one the kit policy of the daemon forbids, and
`InvalidKitError` (`kit`, `reason`) for an argument the kit does not declare,
a value it refuses, or a mixin it cannot take.

### `KitCompiler`

`KitCompiler(client, *, sbx="sbx", work_dir=None, timeout=None)`;
`await compiler.compile(base, output, *, mixins=(), args=None) -> KitPackage`
compiles into the directory `output`, without the cache. It runs the `sbx`
CLI once on a throw-away sandbox behind a capturing proxy. Raises
`KitCompileError`.

### `KitPackage`

| Member | What it is |
|---|---|
| `KitPackage.open(dir)` | opens a package written to a directory; `KitPackageError` when `dir` holds none |
| `dir: Path \| None` | its directory, `None` for a package held in memory |
| `compiled_with`, `compiled_api` | the `sbx` version that compiled it (`None` when forged), the daemon API it was written for |
| `kit_refs`, `kit_artifacts` | the kit references (base first), what the daemon receives |
| `images: list[PackageImage]` | its image archives (`path`, `None` in memory, and `reference`) |
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

From a shell, to compile with the CLI ahead of a run:

```sh
fastsandbox kits compile ./kits/my-local-kit
fastsandbox kits compile claude --mixin ./kits/my-mixin --arg model=claude-haiku-5-5
```

## Example

```python
import secrets

import fastsandbox
from fastsandbox import Kit, KitCache, KitDescriptor, LifecycleStep, McpServer, Mixin


async def main() -> None:
    client = await fastsandbox.connect()
    package = await client.package("shell")  # forged without the sbx CLI, in memory
    print(package.kit_refs, package.compiled_api)

    # `shell` declares no kit argument: the forge would refuse one.
    kit = Kit(base="shell", mixins=("./kits/my-mixin",))
    async with client.create(kit="shell") as sandbox, sandbox.running():
        composed = await client.package(kit)
        await composed.add_to(sandbox)  # the container is recreated
    claude = await client.package("claude")
    if claude.agent is not None:
        print(claude.agent.command("--version"), claude.agent.hosts())

    # A mixin written in Python, checked as it is made.
    step = LifecycleStep(command="echo ready > ~/.ready").as_user("agent")
    descriptor = (
        KitDescriptor.mixin("Ready").with_install(step).with_network_allow("api.example.com:443")
    )
    ready = Mixin(reference="/kits/ready", descriptor=descriptor)
    async with client.create(kit=Kit(base="shell", mixins=(ready,))) as sandbox:
        print(sandbox.name, "holds ~/.ready")

    # An MCP server the host serves on 127.0.0.1:47813, given to Claude Code
    # with a token of the sandbox, which the server checks.
    tools = McpServer.host("project-tools", 47813)
    token = secrets.token_urlsafe(32)
    kit = Kit(base="claude", mixins=(Mixin.mcp("claude", tools),))
    async with client.create(kit=kit, env=tools.env(token)) as sandbox:
        print(sandbox.name, "registers", tools.url)

    # A local kit only the CLI resolves: ask the CLI.
    local = await KitCache(sbx="sbx").package(client, "./kits/my-local-kit")
    print(local.dir, local.compiled_with)


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- Kits are forged without the `sbx` CLI: the first one pulls the image of its
  base kit, then takes seconds. The CLI is needed only for a kit it alone
  resolves, with `KitCache(sbx="sbx")`: then its first compilation of an agent
  kit can take minutes, which `fastsandbox kits compile` does ahead of time.
- A mixin whose `spec.yaml` is written in YAML is refused by the forge
  (`InvalidKitError`): write it in the JSON subset of YAML, write it in Python
  (`Mixin`), or ask the CLI.
- A `Mixin` is refused as it is made, by the rules of the forge: a host the
  CLI refuses, a URL or a path in place of a host, an empty command, an
  install command in the background, an unknown field, a kit argument
  (`${{ }}`). An install command runs in an emptied environment: give it
  variables with `with_env`.
- A server of the host given by `Mixin.mcp()` listens on `127.0.0.1:<port>`:
  the proxy forwards the requests of the sandbox there as `localhost:<port>`,
  which the MCP Python SDK accepts as it is. Only the token tells the sandbox
  apart from the other processes of the host: have the server check it. The
  proxy writes no secret into requests to the host, so the sandbox holds that
  token: make it random. The token is not part of the mixin: one package
  serves sandboxes with tokens of their own.
- Each composition (base, mixins, args) is kept apart.
- After `add_to()`, the new container needs a session of its own: open a new
  `async with sandbox.running():` block.
- Tests forge their kits against the fake daemon, which serves the published
  `shell` and `claude` kits (`FakeDaemon.kits`, `PublishedKit`), or use
  packages written by `fake_package()` of the testing module: load the testing
  skill.
