# The daemon

[`client.daemon`][fastsandbox.Daemon] reaches the daemon itself: its health and
version, its settings, its log levels, the disk it uses, and the reports it
gives for support. This page covers what a program reads to watch the daemon,
and the few things it changes on it.

```python title="docs_src/client/daemon.py" hl_lines="7 11 15 18"
--8<-- "docs_src/client/daemon.py"
```

## Health and version

[`health()`][fastsandbox.Daemon.health] asks for the current
[`Health`][fastsandbox.models.Health]: the `status`
([`is_healthy`][fastsandbox.models.Health.is_healthy] when it is `healthy`),
the `sbx` release `version` and the `api_version` of the socket.
[`Client.health`][fastsandbox.Client.health] keeps the one reported at
connection time. [`info()`][fastsandbox.Daemon.info] gives the version and
build information, the path of the API socket among them.

## Settings

| Call | What it does |
|---|---|
| [`settings()`][fastsandbox.Daemon.settings] | every [`Setting`][fastsandbox.models.Setting]: its `key`, `value`, `default`, `source` (`default`, `override`…), type and description |
| [`setting(key)`][fastsandbox.Daemon.setting] | one setting |
| [`set_setting(key, value)`][fastsandbox.Daemon.set_setting] | overrides it with any JSON value, and returns the setting |
| [`unset_setting(key)`][fastsandbox.Daemon.unset_setting] | removes the override: the default applies again |

!!! warning
    The settings are those of the user, shared by every sandbox and by the
    `sbx` CLI. A program that changes one restores it when it is done, also on
    an error: with `unset_setting()` when its source was `default`, with
    `set_setting()` and the previous value otherwise.

## Log levels

[`log_levels()`][fastsandbox.Daemon.log_levels] gives the level of each
category, e.g. `{"general": "info", "proxy": "info"}`, and
[`set_log_level(target, level)`][fastsandbox.Daemon.set_log_level] sets one:
`target` is `general`, `proxy` or `all`, `level` is `debug`, `info`, `warn` or
`error`. The levels are shared too: restore them.

## Disk usage

[`disk_usage()`][fastsandbox.Daemon.disk_usage] gives a
[`DiskUsage`][fastsandbox.models.DiskUsage]: a summary per resource type
(images, containers, volumes), with the count, the count in use, the size and
the size that could be reclaimed, in bytes, then the details of each resource
as the daemon reports them.

## Reports for support

[`debug_state()`][fastsandbox.Daemon.debug_state] gives the internal state of
the daemon, and [`diagnostics()`][fastsandbox.Daemon.diagnostics] the
diagnostics it collects. Their shapes are not stable, and secrets show there
as `***`: read them for a support report, not for the logic of a program.

## The resources of a sandbox

The CPUs and memory of a sandbox are set at its creation (`cpus=2`,
`memory="4g"`, see [Creating a sandbox](sandboxes.md#creating-a-sandbox)), and
read back in its [`SandboxInfo`][fastsandbox.models.SandboxInfo];
[`vm_metrics()`][fastsandbox.Sandbox.vm_metrics] gives the metrics of its
virtual machine, in the Prometheus text format.
