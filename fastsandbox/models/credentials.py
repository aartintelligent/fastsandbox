"""Credentials of a sandbox: custom secrets, service credentials and their sources."""

from __future__ import annotations

from pydantic import Field, SecretStr, field_serializer

from ._base import Model, expose_secret

__all__ = [
    "CredentialSource",
    "CredentialsOutcome",
    "CredentialsUpdate",
    "CustomSecret",
    "ServiceCredential",
]


def _env_name_part(name: str) -> str:
    """`name` as part of an environment variable name, as `sbx` builds them."""
    return "".join(c.upper() if c.isascii() and c.isalnum() else "_" for c in name)


class CustomSecret(Model):
    """A secret the sandbox proxy injects into requests to `targets`.

    The sandbox only sees the placeholder `sentinel`.

    Attributes:
        env_name: Environment variable holding the placeholder in the sandbox.
        sentinel: Placeholder visible inside the sandbox.
        target: Primary target host.
        targets: Every host or pattern the real value is sent to.
        value: The real value, never printed.

    """

    env_name: str | None = None
    sentinel: str
    target: str = ""
    targets: list[str]
    value: SecretStr

    _expose = field_serializer("value")(expose_secret)

    @classmethod
    def new(
        cls, targets: list[str], sentinel: str, value: str, env_name: str | None = None
    ) -> CustomSecret:
        """A secret for `targets`, the first being the primary one."""
        return cls(
            env_name=env_name,
            sentinel=sentinel,
            target=targets[0] if targets else "",
            targets=targets,
            value=SecretStr(value),
        )


class ServiceCredential(Model):
    """A credential for a service known to `sbx`.

    Attributes:
        service: Service identifier, e.g. `github`.
        value: The credential, never printed; empty to clear it.
    """

    service: str
    value: SecretStr

    _expose = field_serializer("value")(expose_secret)

    @classmethod
    def cleared(cls, service: str) -> ServiceCredential:
        """Clears the credential of `service`."""
        return cls(service=service, value=SecretStr(""))


class CredentialSource(Model):
    """How a service credential is resolved inside the sandbox.

    Attributes:
        source: Source identifier, e.g. an environment variable name.
        kind: Source kind, e.g. `env`.
    """

    source: str
    kind: str = Field(alias="type")

    @classmethod
    def env(cls, name: str) -> CredentialSource:
        """The environment variable `name`."""
        return cls(source=name, kind="env")


class CredentialsUpdate(Model):
    """An update of the credentials of a sandbox.

    Attributes:
        custom_secrets: Proxy-injected secrets: `None` leaves those of the
            sandbox as they are, a list replaces them.
        credential_values: Credentials for services known to `sbx`.
        credential_sources: How each service credential is resolved.
        removed_credential_sources: Services whose source is removed.
    """

    custom_secrets: list[CustomSecret] | None = None
    credential_values: list[ServiceCredential] = []
    credential_sources: dict[str, CredentialSource] = {}
    removed_credential_sources: list[str] = []

    def with_custom_secret(self, secret: CustomSecret) -> CredentialsUpdate:
        """The update, with one more custom secret."""
        return self.model_copy(update={"custom_secrets": [*(self.custom_secrets or []), secret]})

    def without_custom_secrets(self) -> CredentialsUpdate:
        """The update, removing every custom secret of the sandbox."""
        return self.model_copy(update={"custom_secrets": []})

    def with_service_credential(self, service: str, value: str) -> CredentialsUpdate:
        """The update, with the credential of `service`."""
        credential = ServiceCredential(service=service, value=SecretStr(value))
        return self.model_copy(update={"credential_values": [*self.credential_values, credential]})

    def with_credential_source(self, service: str, source: CredentialSource) -> CredentialsUpdate:
        """The update, resolving the credential of `service` from `source`."""
        return self.model_copy(
            update={"credential_sources": {**self.credential_sources, service: source}}
        )

    def without_credential_source(self, service: str) -> CredentialsUpdate:
        """The update, removing the source of `service`."""
        return self.model_copy(
            update={"removed_credential_sources": [*self.removed_credential_sources, service]}
        )

    def with_sandbox_secret(self, sandbox: str, service: str, value: str) -> CredentialsUpdate:
        """The update, storing `value` as the sandbox secret of `service`.

        As `sbx secret set` does, for the sandbox `sandbox`.
        """
        source = f"SANDBOX_STORED_CREDENTIAL_{_env_name_part(sandbox)}_{_env_name_part(service)}"
        return self.with_service_credential(service, value).with_credential_source(
            service, CredentialSource.env(source)
        )

    def without_sandbox_secret(self, service: str) -> CredentialsUpdate:
        """The update, removing the stored secret of `service`."""
        return self.with_service_credential(service, "").without_credential_source(service)


class CredentialsOutcome(Model):
    """Outcome of a credentials update pushed to a sandbox.

    The daemon accepts an update even when it withholds what it carries: read
    `withheld` to know which services get nothing.

    Attributes:
        message: Human-readable message, e.g. `Credentials updated`.
        withheld: Services whose credential, declared by a kit of the sandbox, the daemon
            does not authorize: the proxy injects nothing for them, a value just pushed
            included.
        credential_source_updates_applied: Whether the credential sources of the update
            were applied; `None` when the update carries none.
    """

    message: str | None = None
    withheld: list[str] = []
    credential_source_updates_applied: bool | None = None
