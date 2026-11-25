"""Credentials and secrets."""

from __future__ import annotations

from fastsandbox.models import (
    CredentialsUpdate,
    CustomSecret,
    wire,
)


def test_secrets_are_exposed_to_the_extension_only() -> None:
    secret = CustomSecret.new(["api.example.com"], "PLACEHOLDER", "dummy-value")
    assert "dummy-value" not in repr(secret)
    assert "dummy-value" not in secret.model_dump_json()
    assert wire(secret)["value"] == "dummy-value"
    assert wire(secret)["target"] == "api.example.com"


def test_sandbox_secrets_are_named_as_sbx_names_them() -> None:
    update = CredentialsUpdate().with_sandbox_secret("job-42", "github", "dummy")
    shape = wire(update)
    assert shape["credential_values"] == [{"service": "github", "value": "dummy"}]
    assert shape["credential_sources"] == {
        "github": {"source": "SANDBOX_STORED_CREDENTIAL_JOB_42_GITHUB", "type": "env"}
    }
