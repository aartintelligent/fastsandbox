# SSH

Full page: https://aartintelligent.github.io/fastsandbox/client/ssh/

The daemon turns a request on its socket into a tunnel to the SSH server of a
sandbox: no published port, no key.

## API

`await sandbox.ssh_tunnel() -> SshTunnel` (the sandbox must run). The server
greets first, with a line starting with `SSH-2.0-`.

| `SshTunnel` member | What it does |
|---|---|
| `await read(size=65536) -> bytes` | reads at most `size` bytes; `b""` is the end |
| `await write(data: bytes)` | writes bytes |
| `await close()` | closes the tunnel, as leaving `async with` does |
| `await proxy_stdio()` | relays the tunnel to the process's standard input and output |

The command line wraps it for the SSH client of the system:
`fastsandbox ssh-proxy SANDBOX` holds the sandbox running and relays stdio,
the job of an OpenSSH `ProxyCommand`.

```sh
ssh -o ProxyCommand="fastsandbox ssh-proxy my-sandbox" agent@my-sandbox uname -a
```

## Example

```python
import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        async with await sandbox.ssh_tunnel() as tunnel:
            greeting = b""
            while b"\n" not in greeting and (data := await tunnel.read()):
                greeting += data
        print(greeting.decode().strip())


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- The SSH server accepts any user, `root` included, without credentials:
  whoever holds a tunnel, or reaches the socket, is `root` in the sandbox.
  Never relay a tunnel to untrusted code or over the network.
- Each sandbox has its own host key, new when it is created again: the SSH
  client asks to accept it, or refuses a changed key under a known name.
- `fastsandbox ssh-proxy` writes no SSH configuration; add a `Host` block with
  `ProxyCommand fastsandbox ssh-proxy %h` yourself if wanted.
- The fake daemon answers the SSH route with 501: test this code against the
  real daemon.
