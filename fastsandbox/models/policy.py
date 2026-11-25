"""The network policy: rules, changes, checks and activity."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import Field

from ..exceptions import OperationFailedError
from ._base import Model

__all__ = [
    "CheckKind",
    "CheckResult",
    "CreatedRule",
    "Decision",
    "HostActivity",
    "HttpTarget",
    "NetworkCheck",
    "NetworkLog",
    "NetworkRule",
    "NetworkRules",
    "Protocol",
    "RuleAction",
    "RuleChange",
    "RuleChangeResult",
]


class Decision(StrEnum):
    """The outcomes of a rule the library names; others are plain strings."""

    ALLOW = "allow"
    DENY = "deny"


class RuleAction(StrEnum):
    """What a rule change does."""

    ALLOW = "allow"
    DENY = "deny"
    ALLOW_HTTP = "http-allow"
    DENY_HTTP = "http-deny"
    REMOVE = "remove-resource"
    REMOVE_RULE = "remove-id"


class Protocol(StrEnum):
    """Transport protocol of a network rule."""

    TCP = "tcp"
    UDP = "udp"


class CheckKind(StrEnum):
    """Kind of a network check."""

    NETWORK = "network"
    HTTP = "http"


class NetworkCheck(Model):
    """A target to check against the network policy.

    Attributes:
        kind: Kind of target.
        target: Host, `host:port` or URL.
        method: HTTP method of an HTTP check.
    """

    kind: CheckKind = Field(alias="type")
    target: str
    method: str | None = None

    @classmethod
    def host(cls, target: str) -> NetworkCheck:
        """A connection to `target`, a host or `host:port`."""
        return cls(kind=CheckKind.NETWORK, target=target)

    @classmethod
    def http(cls, method: str, url: str) -> NetworkCheck:
        """An HTTP request `method` to `url`."""
        return cls(kind=CheckKind.HTTP, target=url, method=method)


class CheckResult(Model):
    """Decision of the policy for a network check.

    Attributes:
        allowed: Whether the target is allowed.
        rule: Rule that decided.
        action: Action checked, e.g. `net:connect:tcp`.
        resource_type: Kind of resource matched, e.g. `net:domain`.
        resource_value: Resource matched, e.g. `api.anthropic.com:443`.
        target: Normalized target.
        context: Scope of the decision, e.g. `global`.
        governance: Organization governance state.
    """

    allowed: bool
    rule: str | None = None
    action: str | None = None
    resource_type: str | None = None
    resource_value: str | None = None
    target: str | None = None
    context: str | None = None
    governance: Any = None


class HostActivity(Model):
    """Traffic of one sandbox to one host.

    Attributes:
        host: Host and port, e.g. `api.anthropic.com:443`.
        vm_name: Sandbox the traffic came from.
        count_since: Number of connections since `since`.
        since: Start of the count (RFC 3339).
        last_seen: Last connection (RFC 3339).
        proxy_type: How the proxy handled the traffic, e.g. `forward`.
        rule: Rule that decided, when one did.
        reason: Why the traffic was blocked, for a blocked host.
    """

    host: str
    vm_name: str | None = None
    count_since: int = 0
    since: str | None = None
    last_seen: str | None = None
    proxy_type: str | None = None
    rule: str | None = None
    reason: str | None = None


class NetworkLog(Model):
    """Hosts the sandboxes reached or were refused.

    Attributes:
        allowed_hosts: Hosts that were allowed.
        blocked_hosts: Hosts that were blocked.
    """

    allowed_hosts: list[HostActivity] = []
    blocked_hosts: list[HostActivity] = []

    def for_sandbox(self, name: str) -> NetworkLog:
        """The traffic of the sandbox `name` only."""
        return NetworkLog(
            allowed_hosts=[h for h in self.allowed_hosts if h.vm_name == name],
            blocked_hosts=[h for h in self.blocked_hosts if h.vm_name == name],
        )


class HttpTarget(Model):
    """Host and path of an HTTP rule.

    Attributes:
        host: Host.
        path: Path pattern, e.g. `/v1/**`.
    """

    host: str
    path: str | None = None


class NetworkRule(Model):
    """A rule of the policy: network, HTTP or file system access.

    Attributes:
        id: Rule identifier.
        name: Rule name, the identifier for added rules.
        decision: `allow`, `deny` or another decision of the daemon.
        actions: Actions the rule governs, e.g. `net:connect:tcp`.
        resources: Hosts or patterns it applies to; `**` matches everything.
        resource_type: Kind of resource: `network`, `http`, `filesystem:read`, …
        scope: `global`, or `sandbox:<name>` for a sandbox-scoped rule.
        applies_to: What the rule applies to: `all`, or `sandbox:<name>`.
        sandbox_id: Sandbox of a sandbox-scoped rule.
        methods: HTTP methods of an HTTP rule.
        http_targets: Hosts and paths of an HTTP rule.
        editable: Whether the rule can be changed or removed.
        origin: Where the rule comes from: `local`, `scoped`, …
        layer: Policy layer of the rule.
        policy_id: Policy the rule belongs to.
        status: Rule state, e.g. `active`.
        provenance: How the rule was created.
    """

    id: str
    name: str = ""
    decision: str
    actions: list[str] = []
    resources: list[str] = []
    resource_type: str | None = None
    scope: str | None = None
    applies_to: str | None = None
    sandbox_id: str | None = None
    methods: list[str] = []
    http_targets: list[HttpTarget] = []
    editable: bool = False
    origin: str | None = None
    layer: str | None = None
    policy_id: str | None = None
    status: str | None = None
    provenance: Any = None

    def is_for_sandbox(self, name: str) -> bool:
        """Whether the rule is scoped to the sandbox `name`."""
        return self.sandbox_id == name


class NetworkRules(Model):
    """The rules in force.

    Attributes:
        governance_active: Whether an organization policy governs the rules.
        rules: Every rule, global and sandbox-scoped.
    """

    governance_active: bool = False
    rules: list[NetworkRule] = []


class RuleChange(Model):
    """A change to the network rules.

    Build one with the class methods, then scope it with `for_sandbox`.

    Attributes:
        action: What the change does.
        resources: Hosts or patterns it applies to.
        id: Rule removed by `remove_rule`.
        protocols: Protocols of an allow or deny rule.
        methods: HTTP methods of an HTTP rule.
        path: Path pattern of an HTTP rule.
        sandbox_id: Sandbox the change is scoped to; global when unset.
    """

    action: RuleAction
    resources: list[str] = []
    id: str | None = None
    protocols: list[Protocol] = []
    methods: list[str] = []
    path: str | None = None
    sandbox_id: str | None = None

    @classmethod
    def allow(cls, *resources: str) -> RuleChange:
        """Allows TCP connections to the hosts or patterns."""
        return cls(action=RuleAction.ALLOW, resources=list(resources), protocols=[Protocol.TCP])

    @classmethod
    def deny(cls, *resources: str) -> RuleChange:
        """Denies TCP and UDP connections to the hosts or patterns."""
        return cls(
            action=RuleAction.DENY,
            resources=list(resources),
            protocols=[Protocol.TCP, Protocol.UDP],
        )

    @classmethod
    def allow_http(cls, *resources: str) -> RuleChange:
        """Allows HTTP requests to the hosts or patterns."""
        return cls(action=RuleAction.ALLOW_HTTP, resources=list(resources))

    @classmethod
    def deny_http(cls, *resources: str) -> RuleChange:
        """Denies HTTP requests to the hosts or patterns."""
        return cls(action=RuleAction.DENY_HTTP, resources=list(resources))

    @classmethod
    def remove(cls, *resources: str) -> RuleChange:
        """Removes the rules added for the resources."""
        return cls(action=RuleAction.REMOVE, resources=list(resources))

    @classmethod
    def remove_rule(cls, id: str) -> RuleChange:
        """Removes the rule `id`."""
        return cls(action=RuleAction.REMOVE_RULE, id=id)

    def for_sandbox(self, name: str) -> RuleChange:
        """The change, scoped to the sandbox `name`."""
        return self.model_copy(update={"sandbox_id": name})

    def with_protocols(self, *protocols: Protocol | str) -> RuleChange:
        """The change, for the given protocols."""
        return self.model_copy(update={"protocols": [Protocol(p) for p in protocols]})

    def with_methods(self, *methods: str) -> RuleChange:
        """The HTTP change, for the given methods."""
        return self.model_copy(update={"methods": list(methods)})

    def with_path(self, path: str) -> RuleChange:
        """The HTTP change, for the given path pattern."""
        return self.model_copy(update={"path": path})


class CreatedRule(Model):
    """A rule created by a rule change.

    Attributes:
        rule_id: Identifier of the new rule.
        resource: Resource the rule covers.
        protocols: Protocols of the rule.
    """

    rule_id: str
    resource: str
    protocols: list[str] = []


class RuleChangeResult(Model):
    """Outcome of one rule change.

    Attributes:
        action: Action that was applied, as the daemon names it.
        error: Why the change failed, e.g. an unknown rule identifier.
        id: Rule identifier of a removal by identifier.
        resources: Resources it was applied to.
        sandbox_id: Sandbox it was scoped to.
        created: Rules created by the change.
    """

    action: str = ""
    error: str | None = None
    id: str | None = None
    resources: list[str] = []
    sandbox_id: str | None = None
    created: list[CreatedRule] = []

    @property
    def is_applied(self) -> bool:
        """Whether the change applied."""
        return self.error is None

    def check(self) -> RuleChangeResult:
        """The result itself, or `OperationFailedError` when it did not apply."""
        if self.error is not None:
            raise OperationFailedError(
                f"network rule change failed: {self.error}", operation="network rule change"
            )
        return self
