"""The base of the models and the shape of requests for the native extension."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, SecretStr, SerializationInfo

__all__ = ["Model", "expose_secret", "wire"]


class Model(BaseModel):
    """Base of every payload model.

    Unknown fields are kept, and fields are settable by their name or their alias.
    """

    model_config = ConfigDict(extra="allow", populate_by_name=True)


def wire(model: BaseModel) -> Any:
    """The JSON shape of a request model, as the native extension expects it.

    Aliases are applied, unset optional fields left out, secrets exposed.
    """
    return model.model_dump(
        mode="json", by_alias=True, exclude_none=True, context={"expose_secrets": True}
    )


def expose_secret(value: SecretStr, info: SerializationInfo) -> str:
    """A secret, exposed only for the native extension."""
    context = info.context or {}
    return value.get_secret_value() if context.get("expose_secrets") else str(value)
