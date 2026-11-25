"""What `sbx run` passes from the host to an agent session.

`sandboxd` starts the agent with the environment of the session request only,
and the CLI fills it from the host (`run --name` in the `sessions` suite of the
audit of `docker-sandbox`): the terminal type, so that the agent draws its
interface with the right capabilities and colors; the time zone, which is UTC
otherwise; and the desktop session of the host as `SBX_HOST_*` variables,
through which the sandbox reaches it (opening a URL in the browser of the
host). The SSH agent of the host is forwarded as well, unless the
`ssh.agentForwardingEnabled` setting turns it off.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from fastsandbox import SandboxError
from fastsandbox.models import AgentSessionSpec, TerminalSize

if TYPE_CHECKING:
    from collections.abc import Sequence

    from fastsandbox import Client

__all__ = ["agent_session", "session_env", "ssh_agent_socket"]

TERMINAL = ("TERM", "COLORTERM")
"""Variables of the terminal, passed as they are."""

DESKTOP = (
    "DBUS_SESSION_BUS_ADDRESS",
    "DISPLAY",
    "WAYLAND_DISPLAY",
    "XAUTHORITY",
    "XDG_RUNTIME_DIR",
)
"""Variables of the desktop session, passed as `SBX_HOST_<NAME>`."""

LOCALTIME = Path("/etc/localtime")
"""Zone file of the host, read when `TZ` is not set."""


async def agent_session(
    client: Client, size: tuple[int, int], args: Sequence[str] = ()
) -> AgentSessionSpec:
    """The agent session `sbx run` would open from this terminal, of `size`.

    Args:
        client: The client of the daemon, whose settings say whether the SSH
            agent is forwarded.
        size: The `(width, height)` of the terminal.
        args: Arguments of the agent, as `sbx run AGENT -- ARGS` passes them.
    """
    width, height = size
    return AgentSessionSpec(
        args=list(args),
        tty=True,
        terminal_size=TerminalSize(width=width, height=height),
        env=session_env(),
        ssh_agent_socket_path=await ssh_agent_socket(client),
    )


def session_env() -> dict[str, str]:
    """`TERM`, `COLORTERM`, `TZ`, and the desktop session as `SBX_HOST_*` variables.

    As far as the host has them.
    """
    env = {name: value for name in TERMINAL if (value := _var(name))}
    if zone := _time_zone():
        env["TZ"] = zone
    env.update({f"SBX_HOST_{name}": value for name in DESKTOP if (value := _var(name))})
    return env


async def ssh_agent_socket(client: Client) -> str | None:
    """The SSH agent socket `sbx` forwards.

    None when the `ssh.agentForwardingEnabled` setting is off, else the
    `ssh.agentSocketPath` setting, else `$SSH_AUTH_SOCK`.
    """
    try:
        enabled = await client.daemon.setting("ssh.agentForwardingEnabled")
    except SandboxError:
        enabled = None
    if enabled is not None and enabled.value is False:
        return None
    try:
        path = await client.daemon.setting("ssh.agentSocketPath")
    except SandboxError:
        path = None
    if path is not None and isinstance(path.value, str) and path.value:
        return path.value
    return _var("SSH_AUTH_SOCK")


def _time_zone() -> str | None:
    """The time zone of the host as a POSIX `TZ` rule.

    `$TZ`, else the rule that ends the zone file of the host (`TZif` version 2
    and later), daylight saving time included.
    """
    if zone := _var("TZ"):
        return zone
    try:
        return tz_rule(LOCALTIME.read_bytes())
    except OSError:
        return None


def tz_rule(zone_file: bytes) -> str | None:
    """The POSIX `TZ` rule of a `TZif` file: its last line, from version 2 on."""
    if not zone_file.startswith(b"TZif") or len(zone_file) < 5 or zone_file[4:5] < b"2":
        return None
    if not zone_file.endswith(b"\n"):
        return None
    rule = zone_file[:-1].rpartition(b"\n")[2]
    try:
        return rule.decode() or None
    except UnicodeDecodeError:
        return None


def _var(name: str) -> str | None:
    """The value of the environment variable `name`, when set and not empty."""
    return os.environ.get(name) or None
