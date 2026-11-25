# The daemon

Full page: https://aartintelligent.github.io/fastsandbox/client/daemon/

`client.daemon` is a `Daemon` handle: health, version, settings, log levels,
disk usage, support reports.

## API

| Call | Gives |
|---|---|
| `await health() -> Health` | `status` (`is_healthy` when `"healthy"`), `version` of `sbx` (e.g. `v0.54.1`), `api_version`, `revision`, `release`; `client.health` keeps the one from connection time |
| `await info() -> DaemonInfo` | version and build information, `api_socket` |
| `await settings() -> list[Setting]` | every setting: `key`, `value`, `default`, `source` (`default`, `override`…), `value_type`, `description` |
| `await setting(key) -> Setting` | one setting |
| `await set_setting(key, value) -> Setting` | overrides it with any JSON value |
| `await unset_setting(key)` | removes the override; the default applies again |
| `await log_levels() -> dict[str, str]` | e.g. `{"general": "info", "proxy": "info"}` |
| `await set_log_level(target, level)` | `target`: `general`, `proxy` or `all`; `level`: `debug`, `info`, `warn`, `error` |
| `await disk_usage() -> DiskUsage` | `summaries: list[DiskUsageSummary]` (`resource_type`, `total_count`, `active`, `size`, `reclaimable`, bytes), then `images`, `containers`, `volumes` as reported |
| `await debug_state() -> Any`, `await diagnostics() -> Any` | support reports; unstable shapes, secrets shown as `***` |

The resources of a sandbox are set at creation (`cpus=2`, `memory="4g"`), read
back in `SandboxInfo`, and measured by `await sandbox.vm_metrics()`
(Prometheus text).

## Example

```python
import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    daemon = client.daemon
    health = await daemon.health()
    print(f"sbx {health.version}, API {health.api_version}, healthy {health.is_healthy}")

    for setting in await daemon.settings():
        if setting.value != setting.default:
            print(f"{setting.key} = {setting.value} ({setting.source})")

    # A change to shared state is restored, also on an error.
    previous = (await daemon.log_levels()).get("proxy", "info")
    await daemon.set_log_level("proxy", "debug")
    try:
        ...
    finally:
        await daemon.set_log_level("proxy", previous)

    for summary in (await daemon.disk_usage()).summaries:
        print(f"{summary.resource_type}: {summary.size} bytes, {summary.reclaimable} reclaimable")


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- Settings and log levels are those of the user, shared with every sandbox
  and the `sbx` CLI: restore what you change, with `unset_setting()` when the
  source was `default`, with `set_setting()` and the previous value otherwise.
- Read `debug_state()` and `diagnostics()` for support reports, not for
  program logic.
- The library exposes no reset or shutdown of the daemon; never send those
  requests to the socket by other means.
