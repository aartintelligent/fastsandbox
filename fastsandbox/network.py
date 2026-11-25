"""The network rules of the sandbox of a task."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import RuleChange, RuleChangeResult

if TYPE_CHECKING:
    from collections.abc import Iterable

    from .sandbox import Sandbox

__all__ = ["Network"]


@dataclass(frozen=True)
class Network:
    """The network rules of the sandbox of a task.

    They are scoped to that sandbox and go with it. Combine them with `|`.

    Example:
        >>> Network.allow("pypi.org", "files.pythonhosted.org") | Network.deny("example.org")

    Attributes:
        changes: The rule changes, applied in order once the sandbox runs.

    """

    changes: tuple[RuleChange, ...] = ()

    @classmethod
    def allow(cls, *hosts: str) -> Network:
        """Allows TCP connections to the hosts or patterns."""
        return cls((RuleChange.allow(*hosts),))

    @classmethod
    def deny(cls, *hosts: str) -> Network:
        """Denies TCP and UDP connections to the hosts or patterns."""
        return cls((RuleChange.deny(*hosts),))

    @classmethod
    def allow_http(
        cls, *hosts: str, methods: Iterable[str] = (), path: str | None = None
    ) -> Network:
        """Allows HTTP requests to the hosts, for `methods` and `path` when given."""
        change = RuleChange.allow_http(*hosts).with_methods(*methods)
        return cls((change.with_path(path) if path is not None else change,))

    @classmethod
    def deny_http(
        cls, *hosts: str, methods: Iterable[str] = (), path: str | None = None
    ) -> Network:
        """Denies HTTP requests to the hosts, for `methods` and `path` when given."""
        change = RuleChange.deny_http(*hosts).with_methods(*methods)
        return cls((change.with_path(path) if path is not None else change,))

    def __or__(self, other: Network) -> Network:
        return Network(self.changes + other.changes)

    async def apply(self, sandbox: Sandbox) -> list[RuleChangeResult]:
        """Applies the rules to `sandbox`, scoped to it.

        Raises:
            OperationFailedError: When a change did not apply.
        """
        if not self.changes:
            return []
        scoped = [change.for_sandbox(sandbox.name) for change in self.changes]
        return await sandbox.client.policy.apply_all(*scoped)
