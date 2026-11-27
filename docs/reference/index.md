# Reference

The reference of every public name of `fastsandbox`, rendered from the
docstrings and the annotations of the package. Names are given as they are
imported: `fastsandbox.Sandbox`, not the module that defines it. The payloads
are in [`fastsandbox.models`](models.md), the errors in
[`fastsandbox.exceptions`](exceptions.md), the fake daemon in
[`fastsandbox.testing`](testing.md).

| Page | Holds |
|---|---|
| [Client](client.md) | `connect()`, `Client`, `Creation`, the socket and the API version |
| [Sandboxes](sandboxes.md) | `Sandboxes`, the collection, and `Sandbox`, the handle of one sandbox |
| [Sessions and streams](sessions.md) | `Session`, `Interactive`, `Stream`, `SshTunnel` |
| [Daemon services](services.md) | `Daemon`, `Images`, `Policy`, `Mcp`, `Events`, `Prompts` |
| [Kits](kits.md) | `Kit`, `KitPackage`, `KitAgent`, `KitForge`, `KitCompiler`, `KitCache`; mixins written in Python: `Mixin`, `KitDescriptor`, `LifecycleStep` |
| [FastSandbox](applications.md) | `FastSandbox`, `run()`, `Task`, `Context`, `unique_name()` |
| [Agents](agents.md) | `AGENTS`, `AgentProfile`, `AgentRunner`, `AgentRun`, `Credential` |
| [Parameters](params.md) | `Depends`, `WorkspaceDir`, `Mounted`, `Uploaded`, `Network` |
| [Models](models.md) | the Pydantic models of the daemon API |
| [Exceptions](exceptions.md) | `SandboxError` and the errors derived from it |
| [Types](types.md) | `Command`, `VersionPolicy`, `Lifespan`, `ProgressHandler` |
| [Testing](testing.md) | `FakeDaemon`, `PublishedKit`, `fake_package()` |
