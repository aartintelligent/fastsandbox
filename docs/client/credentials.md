# Credentials

A sandbox reaches services with credentials it never holds: the program pushes
them to the daemon through the socket, and the proxy of the sandbox writes
them into the requests that go to their hosts. Inside, the sandbox only sees
placeholders. This page covers custom secrets, the credentials of the services
`sbx` knows, and their updates.

```python title="docs_src/client/credentials.py" hl_lines="12-16 18 21"
--8<-- "docs_src/client/credentials.py"
```

## Custom secrets

A [`CustomSecret`][fastsandbox.models.CustomSecret] is a value, the hosts it is
for, and a placeholder:
`CustomSecret.new(targets, sentinel, value, env_name=None)`. The program in
the sandbox puts the placeholder where the credential goes, in a header for
instance; the proxy replaces it with the value in the requests to the
`targets`, and leaves it as it is in requests to any other host.

- The value is a Pydantic `SecretStr`: a log, a `repr()` or a JSON dump shows
  it masked, and only the request sent to the daemon carries it.
- The sandbox holds no value: not in its environment, not in its files.
  `env_name` is recorded with the secret, but no such variable is set in the
  environment of a command.
- The secrets stay with the sandbox through a stop and a start, and go with it
  when it is deleted.

[`sandbox.push_credentials(update)`][fastsandbox.Sandbox.push_credentials]
sends a [`CredentialsUpdate`][fastsandbox.models.CredentialsUpdate]. Its
custom secrets replace those of the sandbox, with one exception:

| Update | Custom secrets of the sandbox |
|---|---|
| `CredentialsUpdate().with_custom_secret(secret)` | replaced by the list of the update |
| `CredentialsUpdate()`, or one with service credentials only | left as they are (`custom_secrets` is `None`) |
| `CredentialsUpdate().without_custom_secrets()` | all removed |

## Credentials of services

The services `sbx` knows, `github` or `openai` for instance, have credentials
of their own. [`push_service_secret(service, value)`][fastsandbox.Sandbox.push_service_secret]
gives one to a sandbox as `sbx secret set SERVICE --sandbox` does, and
[`remove_service_secret(service)`][fastsandbox.Sandbox.remove_service_secret]
takes it back as `sbx secret rm` does. The daemon records where each credential
comes from, in [`SandboxInfo.credential_sources`][fastsandbox.models.SandboxInfo];
the sandbox keeps the fixed placeholders it was created with, `GH_TOKEN` for
GitHub, never a value.

The same by hand, with the methods of
[`CredentialsUpdate`][fastsandbox.models.CredentialsUpdate]: a value, and the
source the daemon records for it, an environment variable name as the CLI
declares the credentials it stores:

```python
from fastsandbox.models import CredentialSource, CredentialsUpdate

update = (
    CredentialsUpdate()
    .with_service_credential("openai", value)
    .with_credential_source("openai", CredentialSource.env("MY_OPENAI_SOURCE"))
)
await sandbox.push_credentials(update)
```

`with_sandbox_secret()` and `without_sandbox_secret()` build the updates of
`push_service_secret()` and `remove_service_secret()`; a cleared
[`ServiceCredential`][fastsandbox.models.ServiceCredential] and
`without_credential_source()` take a credential back.

!!! tip
    Push only the credentials a sandbox needs: they are scoped to it and go
    with it. FastSandbox does this for the agents it runs, from the
    environment of the host (see [Agents](../framework/agents.md)).
