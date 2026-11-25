"""What a program reads of the daemon to watch it, and the few things it changes on it.

The example connects with a client configured before it connects, then reads
the health and version of the daemon, its settings and log levels, the disk it
uses, the state of the network policy, its internal state and diagnostics, and
the resources and the VM metrics of a sandbox created with limits.

One setting and one log level are changed, then restored to what they were,
also on an error: the settings are those of the user, shared by every sandbox.
The sandbox is deleted when the example ends.

Run it with:

    just example daemon
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

import common
import fastsandbox
from common import kit

if TYPE_CHECKING:
    from fastsandbox import Client, Daemon

CPUS = 1
"""Virtual CPUs of the sandbox of the example."""

MEMORY = "2g"
"""Memory limit of the sandbox of the example, in `sbx` notation."""

WATCHED = (
    "sailor_guest_mem_total_pages",
    "sailor_guest_mem_available_pages",
    "sailor_guest_net_rx_bytes_total",
    "sailor_guest_net_tx_bytes_total",
    "sailor_guest_oom_kill_total",
)
"""Metric families shown, out of the many the VM exposes.

The memory of the guest, its network traffic, the processes the kernel killed
for memory.
"""

SETTING = "sandbox.disk.dockerVolume"
"""The setting changed then restored, as the live tests of the library do."""

SETTING_VALUE = "12g"
"""Its value while it is changed."""

LOG_TARGET = "proxy"
"""The log category changed then restored."""

REQUEST_TIMEOUT = 30.0
"""Deadline of ordinary requests, in seconds."""

LONG_OPERATION_TIMEOUT = 20 * 60.0
"""Deadline of long operations (creations, image pulls), in seconds."""


async def main() -> None:
    """Runs the example."""
    client = await connect()
    await report(client)
    await changed_and_restored(client.daemon)
    await internals(client.daemon)
    await sandbox_with_limits(client)


async def connect() -> Client:
    """Connects with explicit options.

    The socket of the user, the deadlines of requests and of long operations,
    and a refusal of an API version the library was not checked against.

    Raises:
        ExampleError: When there is no state directory to find the socket in.
    """
    socket = fastsandbox.default_socket_path()
    if socket is None:
        raise common.ExampleError("no state directory to find the socket in")
    client = await fastsandbox.connect(
        socket,
        timeout=REQUEST_TIMEOUT,
        long_operation_timeout=LONG_OPERATION_TIMEOUT,
        version_policy="strict",
    )
    common.expect(client.socket_path == socket, "another socket")
    # The socket by name only: its full path holds the home directory.
    print(f"connected to {socket.name} of the state directory of the user")
    return client


async def report(client: Client) -> None:
    """Reads the health, the changed settings, the log levels, the disk usage and the policy."""
    daemon = client.daemon
    # The health answered at connection time, and asked again.
    health = await daemon.health()
    state = "healthy" if health.is_healthy else health.status
    print(f"daemon {health.version} (API {health.api_version}), {state}")

    # The settings that differ from their default, and where they come from:
    # the user, or the remote configuration of Docker.
    settings = await daemon.settings()
    changed = [setting for setting in settings if setting.value != setting.default]
    print(f"{len(settings)} settings, {len(changed)} of them changed from their default:")
    for setting in changed:
        print(f"  {setting.key} = {setting.value} ({setting.source or 'unknown source'})")
    for target, level in (await daemon.log_levels()).items():
        print(f"log level of {target}: {level}")

    for summary in (await daemon.disk_usage()).summaries:
        print(
            f"disk: {summary.resource_type:<14} {summary.total_count:>3} "
            f"({summary.active} in use), {size(summary.size)}, "
            f"{size(summary.reclaimable)} reclaimable"
        )

    policy = client.policy
    setup = "to be set up with the sbx CLI" if await policy.setup_needed() else "set up"
    print(f"network policy: {setup}, {len(await policy.profiles())} profiles")


async def changed_and_restored(daemon: Daemon) -> None:
    """Changes `SETTING` and the log level of `LOG_TARGET`, then restores both.

    Both are restored also when a change fails.

    Raises:
        ExampleError: When the setting or the log levels were not restored.
    """
    before = await daemon.setting(SETTING)
    try:
        changed = await daemon.set_setting(SETTING, SETTING_VALUE)
    finally:
        # A default value is restored by removing the override, any other by
        # setting it again.
        if before.source == "default":
            await daemon.unset_setting(SETTING)
        else:
            await daemon.set_setting(SETTING, before.value)
    after = await daemon.setting(SETTING)
    common.expect(
        (after.value, after.source) == (before.value, before.source),
        f"{SETTING} was not restored",
    )
    print(
        f"{SETTING}: {before.value} ({before.source or '?'}), "
        f"set to {changed.value} ({changed.source or '?'}), "
        f"restored to {after.value} ({after.source or '?'})"
    )

    levels = await daemon.log_levels()
    previous = levels.get(LOG_TARGET)
    if previous is None:
        raise common.ExampleError("no log level for the proxy")
    try:
        await daemon.set_log_level(LOG_TARGET, "debug")
        during = await daemon.log_levels()
    finally:
        await daemon.set_log_level(LOG_TARGET, previous)
    common.expect(await daemon.log_levels() == levels, "log levels not restored")
    print(
        f"log level of {LOG_TARGET}: {previous}, set to {during.get(LOG_TARGET, '?')}, "
        f"restored to {previous}"
    )


async def internals(daemon: Daemon) -> None:
    """Shows the top-level parts of the internal state and of the diagnostics report.

    Their shapes are not stable, and secrets show there as `***`: a program
    reads them for a support report, not for its logic.
    """
    print(f"internal state: {_keys(await daemon.debug_state())}")
    print(f"diagnostics: {_keys(await daemon.diagnostics())}")


async def sandbox_with_limits(client: Client) -> None:
    """Creates a sandbox with CPU and memory limits.

    Then reads what the daemon records of them and what its VM reports.
    """
    package = await kit.package(client, "shell")
    name = fastsandbox.unique_name("example-daemon")
    async with (
        client.create(name, kit=package, cpus=CPUS, memory=MEMORY) as sandbox,
        sandbox.running(),
    ):
        info = await sandbox.inspect()
        cpus = info.cpus if info.cpus is not None else "?"
        print(f"{info.name}: {cpus} CPU, {info.memory or '?'} of memory")

        # Prometheus text: one sample per line, named by its family.
        metrics = await sandbox.vm_metrics()
        samples = [
            line for line in metrics.splitlines() if line.strip() and not line.startswith("#")
        ]
        families = {re.split(r"[{ ]", line, maxsplit=1)[0] for line in samples}
        print(f"VM metrics: {len(samples)} samples in {len(families)} families, among them:")
        for line in samples:
            if line.startswith(WATCHED):
                print(f"  {line}")


def size(count: int) -> str:
    """`count` bytes in the largest binary unit that keeps a whole part."""
    units = ("B", "KiB", "MiB", "GiB", "TiB")
    value, unit = count, 0
    while value >= 1024 and unit < len(units) - 1:
        value //= 1024
        unit += 1
    return f"{value} {units[unit]}"


def _keys(value: Any) -> str:
    """The keys of a JSON object, comma-separated; nothing for another value."""
    return ", ".join(value) if isinstance(value, dict) else ""


if __name__ == "__main__":
    common.main(main)
