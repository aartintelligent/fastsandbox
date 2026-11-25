# Security

A sandbox isolates what runs in it from the host; fastsandbox decides what
crosses that boundary: the directories of the host, the network, the
credentials. This page lists where the boundaries are and the defaults to
change for unattended code.

## The socket is the boundary

Whoever can reach the socket of the daemon controls every sandbox of the user:
creates them, runs commands, reads files, changes the network policy. Keep the
socket, and the programs that use fastsandbox, to trusted code.

An [SSH tunnel](../client/ssh.md) is `root` in its sandbox, without credentials:
the SSH server of a sandbox accepts any user, since reaching the socket is
already the authorization.

## Network

The default network policy of `sbx` may allow everything. Rules added by
fastsandbox are added to that policy, they do not replace it:
[`Network.allow("pypi.org")`][fastsandbox.Network.allow] allows `pypi.org`, it
does not deny the rest. To confine a sandbox, check the policy the daemon
applies by default, deny what must stay out, and read the activity log after a
run:

- [`Network`][fastsandbox.Network] on a task, or
  [`allow_hosts()`][fastsandbox.Sandbox.allow_hosts] and
  [`deny_hosts()`][fastsandbox.Sandbox.deny_hosts] on a sandbox: rules scoped
  to that sandbox, which go with it.
- [`client.policy`][fastsandbox.Policy]: the global rules, checks of a host
  against the policy, and the log of what sandboxes reached.

An agent task with network rules also allows the hosts its agent needs (the
hosts its kit declares), unless the task turns that off; see
[Network rules](../framework/network.md).

## Credentials

- **Scoped secrets.** The credentials of an agent are read from the
  environment of the host and pushed as secrets of its sandbox only: the proxy
  of the sandbox injects them into the outgoing requests, the sandbox only sees
  a placeholder, and they go with the sandbox. See
  [Credentials](../client/credentials.md).
- **Global secrets.** Secrets stored with `sbx secret set <service>` are
  injected into every sandbox, those of fastsandbox included; a secret pushed
  for one sandbox takes precedence there.
- Push only the credentials a sandbox needs.

## Host paths

What a task sees of the host is what its parameters say:

| Marker | What the sandbox gets |
|---|---|
| [`WorkspaceDir()`][fastsandbox.WorkspaceDir] | The directory, mounted read-write at its own path: changes reach the host |
| `WorkspaceDir(clone=True)` | A private clone of the Git repository of the directory; the source stays read-only |
| [`Mounted(target, read_only)`][fastsandbox.Mounted] | The directory or file, mounted at `target` (its own path by default), read-write unless `read_only=True` |
| [`Uploaded(target)`][fastsandbox.Uploaded] | A copy of the contents, the sandbox's own |

An unattended agent runs with its approvals turned off (`--yolo` and the like):
the sandbox, its mounts and its network are then the only limits. Prefer a
clone or an upload to a read-write workspace when the result is checked before
it reaches the host.

## The API of the daemon

The `sandboxd` socket API is private to Docker Sandboxes and changes with `sbx`
releases. fastsandbox checks the API version of the daemon when it connects and
refuses one it has not been audited on, unless told otherwise
(`version_policy`); see [The client](../client/index.md).

## Reporting a vulnerability

See the [security policy](../project/security-policy.md)
of the repository.
