"""The network policy of the daemon."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter

from .models import (
    CheckResult,
    NetworkCheck,
    NetworkLog,
    NetworkRules,
    RuleChange,
    RuleChangeResult,
    wire,
)

if TYPE_CHECKING:
    from . import _native

__all__ = ["Policy"]

_RESULTS = TypeAdapter(list[RuleChangeResult])


class Policy:
    """The network policy of the daemon."""

    def __init__(self, native: _native.Policy) -> None:
        self._native = native

    async def rules(self) -> NetworkRules:
        """Every network rule."""
        return NetworkRules.model_validate(await self._native.rules())

    async def apply(self, *changes: RuleChange) -> list[RuleChangeResult]:
        """Applies rule changes; each result says whether it applied."""
        return _RESULTS.validate_python(await self._native.apply([wire(c) for c in changes]))

    async def apply_all(self, *changes: RuleChange) -> list[RuleChangeResult]:
        """Applies rule changes and fails on the first that did not apply.

        Raises:
            OperationFailedError: When a change did not apply.
        """
        return _RESULTS.validate_python(await self._native.apply_all([wire(c) for c in changes]))

    async def remove_rule(self, id: str) -> None:
        """Removes the rule `id`."""
        await self._native.remove_rule(id)

    async def check(self, check: NetworkCheck) -> CheckResult:
        """What the policy decides for a host or an HTTP request."""
        return CheckResult.model_validate(await self._native.check(wire(check)))

    async def log(self) -> NetworkLog:
        """The hosts sandboxes reached or were refused."""
        return NetworkLog.model_validate(await self._native.log())

    async def profiles(self) -> list[Any]:
        """The governance profiles."""
        return await self._native.profiles()

    async def setup_needed(self) -> bool:
        """Whether the policy still needs its initial setup."""
        return await self._native.setup_needed()

    async def refresh(self) -> None:
        """Reloads the policy."""
        await self._native.refresh()
