# SSH

The daemon exposes SSH as an API: a request on the socket turns its
connection into a tunnel to the SSH server of a sandbox. No port is published
and no key is needed. This page covers the tunnel of the library and the SSH
client of the system on top of it.

!!! danger "The socket is the boundary"
    The SSH server of a sandbox accepts any user, `root` included, without
    credentials: whoever holds a tunnel is `root` in the sandbox, and whoever
    reaches the socket can open one. A program that relays a tunnel further
    guards it as it guards the socket.

## The tunnel

[`sandbox.ssh_tunnel()`][fastsandbox.Sandbox.ssh_tunnel] opens an
[`SshTunnel`][fastsandbox.SshTunnel], a stream of bytes to the SSH server; the
sandbox must run. The server greets first, with a line starting with
`SSH-2.0-`:

```python title="docs_src/client/ssh.py" hl_lines="8"
--8<-- "docs_src/client/ssh.py"
```

| Call | What it does |
|---|---|
| [`read(size=65536)`][fastsandbox.SshTunnel.read] | reads at most `size` bytes; `b""` is the end of the stream |
| [`write(data)`][fastsandbox.SshTunnel.write] | writes bytes |
| [`close()`][fastsandbox.SshTunnel.close] | closes the tunnel, as leaving its `async with` block does |
| [`proxy_stdio()`][fastsandbox.SshTunnel.proxy_stdio] | relays the tunnel to the standard input and output of the process |

## The SSH client of the system

`fastsandbox ssh-proxy SANDBOX` relays its standard input and output to the
tunnel of a sandbox, which it keeps running meanwhile: the job of an OpenSSH
`ProxyCommand`. The SSH client of the system logs in through it, as `agent`
or as `root` for instance, the users the `shell-ssh` example logs in as:

```sh
ssh -o ProxyCommand="fastsandbox ssh-proxy my-sandbox" agent@my-sandbox uname -a
```

Or once for all, in `~/.ssh/config`:

```text
Host my-sandbox
    User agent
    ProxyCommand fastsandbox ssh-proxy %h
```

Each sandbox has a host key of its own, new when the sandbox is created
again: the client asks to accept it, or refuses a key that changed under a
name it knows. `sbx setup ssh` writes a `ProxyCommand` of the `sbx` CLI into
the SSH configuration of the user; `fastsandbox ssh-proxy` writes nothing.

!!! info "Testing"
    The SSH tunnel upgrades the connection to the daemon, which the fake daemon
    of [`fastsandbox.testing`](../guides/testing.md) does not do: code that uses it is
    tested against the real daemon.
