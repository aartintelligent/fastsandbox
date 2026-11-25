# Credentials

Full page: https://aartintelligent.github.io/fastsandbox/client/credentials/

A sandbox reaches services with credentials it never holds: the program
pushes them to the daemon, and the proxy of the sandbox writes them into the
requests to their hosts. Inside, the sandbox only sees placeholders.

## API

| Call | What it does |
|---|---|
| `await sandbox.push_credentials(update: CredentialsUpdate)` | sends custom secrets, service credentials and their sources |
| `await sandbox.push_service_secret(service, value)` | the secret of a service `sbx` knows (`github`, `openai`…) for this sandbox, as `sbx secret set SERVICE --sandbox` |
| `await sandbox.remove_service_secret(service)` | takes it back, as `sbx secret rm` |

`CustomSecret.new(targets: list[str], sentinel: str, value: str,
env_name: str | None = None)`: the proxy replaces the placeholder `sentinel`
with `value` in requests to `targets` only. `value` is a Pydantic
`SecretStr`: masked in logs, `repr()` and JSON dumps.

`CredentialsUpdate` (immutable builders, each returns a new update):

| Builder | Effect |
|---|---|
| `with_custom_secret(secret)` | the custom secrets of the update replace those of the sandbox |
| `without_custom_secrets()` | removes every custom secret of the sandbox |
| `with_service_credential(service, value)` | a credential value for a service |
| `with_credential_source(service, CredentialSource.env(name))` | the source the daemon records for it |
| `without_credential_source(service)` | removes a recorded source |
| `with_sandbox_secret(sandbox, service, value)` | what `push_service_secret()` sends |
| `without_sandbox_secret(service)` | what `remove_service_secret()` sends |

An update without custom secrets (`custom_secrets` is `None`, the default)
leaves the sandbox's custom secrets as they are. `ServiceCredential.cleared(service)`
clears one credential. `SandboxInfo.credential_sources` records where each
service credential comes from, never a value.

## Example

```python
import os

import fastsandbox
from fastsandbox.models import CredentialsUpdate, CustomSecret


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        secret = CustomSecret.new(
            ["api.example.com"],
            sentinel="example-placeholder",
            value=os.environ.get("EXAMPLE_TOKEN", "dummy-token"),
        )
        await sandbox.push_credentials(CredentialsUpdate().with_custom_secret(secret))
        # The program in the sandbox sends the placeholder; the proxy swaps it.
        await sandbox.exec(
            'curl -s -H "Authorization: Bearer example-placeholder" https://api.example.com/v1/me'
        )
        await sandbox.push_service_secret("github", os.environ.get("GH_TOKEN", "dummy"))
        print(sorted((await sandbox.inspect()).credential_sources))
        await sandbox.remove_service_secret("github")
        await sandbox.push_credentials(CredentialsUpdate().without_custom_secrets())


if __name__ == "__main__":
    fastsandbox.run(main())
```

## Gotchas

- Never print, log or write a secret value; never read the secrets stored
  with `sbx secret set`: the socket does not expose them, and a program does
  not ask for them.
- `env_name` is recorded with a custom secret, but no such variable is set in
  the environment of a command.
- Secrets stay through a stop and a start, and go with the sandbox when it is
  deleted. Push only what a sandbox needs.
- In tests, push dummy values only.
- Agent tasks push the credentials of their agent from the environment
  themselves: load the agents skill.
