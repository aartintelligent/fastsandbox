"""The approval prompts of the daemon."""

from __future__ import annotations

from ._base import Model

__all__ = ["PromptEvent"]


class PromptEvent(Model):
    """One line of the prompt stream; every field but `action` and `id` is kept as an extra field.

    Attributes:
        action: What happened, e.g. `synced` once the pending prompts are
            delivered.
        id: Identifier of the prompt, to answer it with.

    """

    action: str | None = None
    id: str | None = None

    @property
    def is_synced(self) -> bool:
        """Whether this line marks the end of the pending prompts."""
        return self.action == "synced"
