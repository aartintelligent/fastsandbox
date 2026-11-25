# Security policy

## Supported versions

Only the latest version of the package receives security fixes.

## Reporting a vulnerability

Please do **not** open a public issue for security problems.

Use GitHub's private vulnerability reporting on this repository
(*Security* tab → *Report a vulnerability*). You will get an acknowledgement
within 72 hours and a fix or mitigation plan within 14 days for confirmed
issues.

Vulnerabilities of the Rust library belong to
[`docker-sandbox`](https://github.com/aartintelligent/docker-sandbox); those of
Docker Sandboxes (`sbx`, `sandboxd`) themselves to Docker, Inc., through
Docker's own vulnerability disclosure process.

## Scope notes

- The `sandboxd` socket has no authentication: whoever can open it controls
  every sandbox of the user. fastsandbox adds none; run the programs that use
  it as that user, and never expose the socket to other accounts.
- An SSH tunnel (`Sandbox.ssh_tunnel`, `fastsandbox ssh-proxy`) is `root` in
  its sandbox without credentials.
- Credentials pushed to a sandbox (agent keys, custom secrets) travel in clear
  text over the socket to the daemon, which keeps them out of the sandbox
  behind placeholders. The models hold them as `SecretStr`: they are never
  printed, and exposed only to the native extension.
