# Ports

A port of a sandbox is reached from the host once it is published on a port
of the host. This page covers the ports published from the start, those
published on a running sandbox, and how a server in a sandbox is reached.

```python title="docs_src/client/ports.py" hl_lines="8 9 14 16"
--8<-- "docs_src/client/ports.py"
```

## Bindings

A [`PortBinding`][fastsandbox.models.PortBinding] maps a `sandbox_port` to a
`host_port`: `PortBinding.tcp(sandbox_port, host_port)` or
`PortBinding.udp(...)`. The daemon binds the host port on `127.0.0.1` unless
`host_ip` says otherwise.

## Published from the start

The `ports` of [`client.create()`][fastsandbox.Client.create] are part of the
*desired* configuration of the sandbox: they are published when it starts,
and again at every start.
[`replace_desired_port(old, new)`][fastsandbox.Sandbox.replace_desired_port]
changes one of them for the next start, leaving the ports published now as
they are; an `old` binding that is not part of the desired configuration
raises [`NotFoundError`][fastsandbox.exceptions.NotFoundError].

## Published on a running sandbox

- [`publish(*ports)`][fastsandbox.Sandbox.publish] publishes ports and returns
  the bindings the daemon applied. A stopped sandbox, or a host port already
  taken, raises [`ConflictError`][fastsandbox.exceptions.ConflictError].
- [`unpublish(*ports)`][fastsandbox.Sandbox.unpublish] takes them back; a port
  that is not published is ignored.
- [`ports()`][fastsandbox.Sandbox.ports] lists the ports published now.

## Reaching a server

A server in a sandbox runs as an [interactive session](interactive.md), which
keeps it running until it exits or the sandbox goes; `exec()` would wait for
its end. Wait until it says it listens, then publish its port:

```python
server = await sandbox.attach(["python3", "-u", "-m", "http.server", "8000"])
published = await sandbox.publish(PortBinding.tcp(8000, 48000))
```

Right after the publication, a connection to the host port may still be
refused or reset: retry it for a few seconds. The `shell-ports` example serves
a page from a sandbox this way (see [Examples](../guides/examples.md)).
