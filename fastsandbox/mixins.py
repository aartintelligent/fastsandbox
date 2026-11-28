"""Mixins written in Python: kit descriptors, their lifecycle steps, and the mixins they make.

A mixin adds install and startup commands and network rules to a base kit. What it declares is
the descriptor of a v3 kit, the `spec.yaml` that the daemon reads, the `sbx` CLI reads too, and
`docker-sandbox-kit` forges. These models hold it field for field, under the names the format
gives its fields: `model_dump_json()` is the descriptor as any program reads it, and
`to_spec()` the text of its `spec.yaml`. Their `with_*` methods build it as the crate does.

A `Mixin` lists a descriptor under its reference, and the crate checks it when it is made, by
the rules of the forge: an `InvalidKitError` is raised where the mixin is written, not when a
sandbox is created from it.

`Mixin.mcp()` builds, as the crate does, the mixin that gives the agent of a sandbox its
`McpServer`s: it registers them in the configuration of the agent, inside the sandbox, so that
nothing is registered with the daemon or written on the host.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Final, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

from . import _native

if TYPE_CHECKING:
    from collections.abc import Callable

__all__ = [
    "GATEWAY_ENV",
    "LIFECYCLE",
    "NETWORK",
    "Capability",
    "KitDescriptor",
    "LifecycleCapability",
    "LifecycleConfig",
    "LifecycleStep",
    "McpServer",
    "Mixin",
    "NetworkCapability",
    "NetworkConfig",
    "NetworkRules",
]

LIFECYCLE: Final = "com.docker.sandbox/lifecycle@1"
"""The `type` of the capability of install and startup commands."""

NETWORK: Final = "com.docker.sandbox/network-policy@1"
"""The `type` of the capability of network rules."""

GATEWAY_ENV = ("MCP_GATEWAY_URL", "MCP_SENTINEL_TOKEN_NAME")
"""The variables of a sandbox that name its MCP gateway: its address, and the bearer token
the kits of the agents send it."""

SYNTAX_LINE = "# syntax=docker/sandbox-kit:3"
"""The first line of a v3 `spec.yaml`: the BuildKit frontend that reads it."""


def _unset(value: object) -> bool:
    """Whether an optional field is unset, and left out of the descriptor."""
    return value is None


def _empty(value: tuple[object, ...]) -> bool:
    """Whether a list field is empty, and left out of the descriptor."""
    return not value


class _Spec(BaseModel):
    """Base of the descriptor models.

    Frozen, settable and serialized under the names of the v3 format (`displayName`,
    `sourceUrl`…) and settable by their Python names too. Unknown fields are kept, so that the
    crate names them when it refuses them.
    """

    model_config = ConfigDict(
        frozen=True,
        extra="allow",
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
    )


class LifecycleStep(_Spec):
    """A command a mixin runs: once, when the sandbox is created, or at each of its starts.

    Attributes:
        command: A shell command, run with `sh -c`, or a program and its arguments.
        user: The user it runs as, e.g. `agent`, or `0` for root.
        description: What it does, shown as it runs.
        env: The variables of the sandbox it receives: an install command runs in an emptied
            environment otherwise, which keeps only the proxy and certificate variables.
        background: Whether a startup command runs in the background.
    """

    command: str | tuple[str, ...]
    user: str | None = Field(default=None, exclude_if=_unset)
    description: str | None = Field(default=None, exclude_if=_unset)
    env: tuple[str, ...] = Field(default=(), exclude_if=_empty)
    background: bool | None = Field(default=None, exclude_if=_unset)

    def as_user(self, user: str) -> LifecycleStep:
        """The step, run as `user`, e.g. `agent`, or `0` for root."""
        return self.model_copy(update={"user": user})

    def with_description(self, description: str) -> LifecycleStep:
        """The step, described by `description`."""
        return self.model_copy(update={"description": description})

    def with_env(self, *names: str) -> LifecycleStep:
        """The step, given the variables `names` of the sandbox too."""
        return self.model_copy(update={"env": (*self.env, *names)})

    def with_gateway_env(self) -> LifecycleStep:
        """The step, given the MCP gateway of the sandbox: `GATEWAY_ENV`."""
        return self.with_env(*GATEWAY_ENV)

    def in_background(self) -> LifecycleStep:
        """The startup step, run in the background."""
        return self.model_copy(update={"background": True})


class LifecycleConfig(_Spec):
    """The commands of a lifecycle capability.

    Attributes:
        install: Commands run once, when the sandbox is created, before its agent starts.
        startup: Commands run at every start of the sandbox, alongside its agent.
    """

    install: tuple[LifecycleStep, ...] = Field(default=(), exclude_if=_empty)
    startup: tuple[LifecycleStep, ...] = Field(default=(), exclude_if=_empty)


class NetworkRules(_Spec):
    """Hosts allowed and denied, each `host`, `*.domain`, `host:port` or a CIDR prefix.

    Attributes:
        allow: Hosts allowed.
        deny: Hosts denied; a deny wins over any allow, of the sandbox or of its kits.
    """

    allow: tuple[str, ...] = Field(default=(), exclude_if=_empty)
    deny: tuple[str, ...] = Field(default=(), exclude_if=_empty)


def _no_rules(rules: NetworkRules) -> bool:
    """Whether `rules` hold nothing, and are left out of the descriptor."""
    return not (rules.allow or rules.deny or rules.model_extra)


class NetworkConfig(_Spec):
    """The rules of a network capability.

    Attributes:
        runtime: Rules while the sandbox runs.
        install: Hosts allowed while the install commands run.
    """

    runtime: NetworkRules = Field(default=NetworkRules(), exclude_if=_no_rules)
    install: NetworkRules = Field(default=NetworkRules(), exclude_if=_no_rules)


class LifecycleCapability(_Spec):
    """The install and startup commands of a kit (`com.docker.sandbox/lifecycle@1`).

    Attributes:
        type: `LIFECYCLE`.
        name: Name of the capability.
        description: What the capability does.
        optional: Whether the kit works without it.
        config: The commands.
    """

    type: Literal["com.docker.sandbox/lifecycle@1"] = LIFECYCLE
    name: str | None = Field(default=None, exclude_if=_unset)
    description: str | None = Field(default=None, exclude_if=_unset)
    optional: bool | None = Field(default=None, exclude_if=_unset)
    config: LifecycleConfig = LifecycleConfig()


class NetworkCapability(_Spec):
    """The network rules of a kit (`com.docker.sandbox/network-policy@1`).

    Attributes:
        type: `NETWORK`.
        name: Name of the capability.
        description: What the capability does.
        optional: Whether the kit works without it.
        config: The rules.
    """

    type: Literal["com.docker.sandbox/network-policy@1"] = NETWORK
    name: str | None = Field(default=None, exclude_if=_unset)
    description: str | None = Field(default=None, exclude_if=_unset)
    optional: bool | None = Field(default=None, exclude_if=_unset)
    config: NetworkConfig = NetworkConfig()


Capability = Annotated[LifecycleCapability | NetworkCapability, Field(discriminator="type")]
"""A capability a mixin declares, told apart by its `type`."""


class KitDescriptor(_Spec):
    """The v3 descriptor of a mixin, the `spec.yaml` of the kit.

    Build one with `KitDescriptor.mixin()` and the `with_*` methods, or read one with
    `parse()`, `read()` or `from_json()`, which the crate checks as the forge does.

    Attributes:
        schema_version: Version of the descriptor format, `3`.
        kind: Kind of kit, `mixin`.
        display_name: Name shown for the kit.
        description: What the kit is for.
        version: Version of the kit, e.g. `1.0.0`.
        author: Author of the kit, kept as written.
        licenses: Licenses of the kit, kept as written.
        source_url: Where the kit comes from.
        capabilities: What the kit declares, in order.
    """

    schema_version: Literal["3"] = "3"
    kind: Literal["mixin"] = "mixin"
    display_name: str | None = Field(default=None, exclude_if=_unset)
    description: str | None = Field(default=None, exclude_if=_unset)
    version: str | None = Field(default=None, exclude_if=_unset)
    author: Any = Field(default=None, exclude_if=_unset)
    licenses: Any = Field(default=None, exclude_if=_unset)
    source_url: str | None = Field(default=None, exclude_if=_unset)
    capabilities: tuple[Capability, ...] = ()

    @classmethod
    def mixin(cls, display_name: str) -> KitDescriptor:
        """An empty mixin named `display_name`, to build on with the `with_*` methods."""
        return cls(display_name=display_name)

    @classmethod
    def parse(cls, text: str) -> KitDescriptor:
        """The descriptor of the text of a `spec.yaml` written in JSON.

        The comment and blank lines that open it, such as its `# syntax=` line, are skipped.

        Raises:
            InvalidKitError: When the rest is not JSON, or not a v3 mixin the forge takes.
        """
        return cls.model_validate_json(_native.parse_descriptor(text))

    @classmethod
    def read(cls, path: str | os.PathLike[str]) -> KitDescriptor:
        """The descriptor in the `spec.yaml` at `path`.

        Raises:
            OSError: When the file cannot be read.
            InvalidKitError: As `parse()` does.
        """
        return cls.parse(Path(path).read_text())

    @classmethod
    def from_json(cls, value: dict[str, Any]) -> KitDescriptor:
        """The descriptor of its JSON, as `spec.yaml` holds it.

        Raises:
            InvalidKitError: When it is not a v3 mixin the forge takes.
        """
        return cls.parse(json.dumps(value))

    def with_description(self, description: str) -> KitDescriptor:
        """The descriptor, with the description `description`."""
        return self.model_copy(update={"description": description})

    def with_version(self, version: str) -> KitDescriptor:
        """The descriptor, with the kit version `version`, e.g. `1.0.0`."""
        return self.model_copy(update={"version": version})

    def with_install(self, step: LifecycleStep) -> KitDescriptor:
        """The descriptor, with a command run once, when the sandbox is created."""
        return self._lifecycle(lambda config: {"install": (*config.install, step)})

    def with_startup(self, step: LifecycleStep) -> KitDescriptor:
        """The descriptor, with a command run at every start of the sandbox."""
        return self._lifecycle(lambda config: {"startup": (*config.startup, step)})

    def with_network_allow(self, *hosts: str) -> KitDescriptor:
        """The descriptor, allowing `hosts` while the sandbox runs.

        A host is `host`, `*.domain`, `host:port`, a CIDR prefix…, as the CLI takes it; the
        crate checks the hosts when the mixin is made.
        """
        return self._network(lambda rules: {"allow": (*rules.allow, *hosts)})

    def with_network_deny(self, *hosts: str) -> KitDescriptor:
        """The descriptor, denying `hosts` while the sandbox runs.

        A deny wins over any allow, of the sandbox or of its kits.
        """
        return self._network(lambda rules: {"deny": (*rules.deny, *hosts)})

    def to_json(self) -> dict[str, Any]:
        """The descriptor as JSON, as `spec.yaml` holds it."""
        return self.model_dump(mode="json")

    def to_spec(self) -> str:
        """The text of a `spec.yaml` holding the descriptor.

        Its `# syntax=` line, then the descriptor as JSON, which the `sbx` CLI reads as YAML.
        """
        return f"{SYNTAX_LINE}\n{json.dumps(self.to_json(), indent=2, ensure_ascii=False)}\n"

    def _lifecycle(self, change: Callable[[LifecycleConfig], dict[str, Any]]) -> KitDescriptor:
        """The descriptor, with `change` applied to the commands of its lifecycle capability.

        The capability is appended when the descriptor has none.
        """
        for index, capability in enumerate(self.capabilities):
            if isinstance(capability, LifecycleCapability):
                config = capability.config.model_copy(update=change(capability.config))
                return self._replaced(index, capability.model_copy(update={"config": config}))
        config = LifecycleConfig().model_copy(update=change(LifecycleConfig()))
        return self._appended(LifecycleCapability(config=config))

    def _network(self, change: Callable[[NetworkRules], dict[str, Any]]) -> KitDescriptor:
        """The descriptor, with `change` applied to its network rules while the sandbox runs.

        The capability is appended when the descriptor has none.
        """
        for index, capability in enumerate(self.capabilities):
            if isinstance(capability, NetworkCapability):
                runtime = capability.config.runtime
                runtime = runtime.model_copy(update=change(runtime))
                config = capability.config.model_copy(update={"runtime": runtime})
                return self._replaced(index, capability.model_copy(update={"config": config}))
        runtime = NetworkRules().model_copy(update=change(NetworkRules()))
        return self._appended(NetworkCapability(config=NetworkConfig(runtime=runtime)))

    def _replaced(self, index: int, capability: Capability) -> KitDescriptor:
        """The descriptor, its capability at `index` replaced by `capability`."""
        capabilities = list(self.capabilities)
        capabilities[index] = capability
        return self.model_copy(update={"capabilities": tuple(capabilities)})

    def _appended(self, capability: Capability) -> KitDescriptor:
        """The descriptor, with `capability` last."""
        return self.model_copy(update={"capabilities": (*self.capabilities, capability)})


class McpServer(BaseModel):
    """An MCP server for the agent of a sandbox, registered by `Mixin.mcp()`.

    Make one with `McpServer.host()` or `McpServer.remote()`; `Mixin.mcp()` checks it.

    Attributes:
        name: The name the agent knows the server under: letters, digits, `-` and `_`.
        url: The URL of its endpoint, over streamable HTTP.
        token_env: The variable of the sandbox holding its bearer token, if it takes one.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    url: str
    token_env: str | None = None

    @classmethod
    def host(cls, name: str, port: int) -> McpServer:
        """A server a process of the host serves on `port` of its loopback, in any language.

        The sandbox reaches it at `http://host.docker.internal:<port>/mcp`; its proxy forwards
        the requests to the loopback of the host as `localhost:<port>`, so a server guarded
        against DNS rebinding takes them as it takes those of the host. Its bearer token is
        read from the variable `token_env`, `DOCKER_SANDBOX_MCP_<NAME>_TOKEN`, which the
        creation request sets (`env(token)`) and the server checks: the token, not the origin
        of a request, tells the sandbox apart from the other processes of the host. The proxy
        writes no secret into the requests to the host: the sandbox holds that token, which is
        to be random and its own.
        """
        name, url, token_env = _native.mcp_host_server(name, port)
        return cls(name=name, url=url, token_env=token_env)

    @classmethod
    def remote(cls, name: str, url: str) -> McpServer:
        """A remote server at `url`, called by the agent itself.

        It takes no token until `with_bearer_env()`.
        """
        return cls(name=name, url=url)

    def with_bearer_env(self, env: str) -> McpServer:
        """The server, sent the content of the variable `env` of the sandbox as its bearer token.

        For a key the sandbox must not hold, give the sandbox a `CustomSecret` for the host of
        the server whose `env_name` is `env`: the variable holds its placeholder, which the
        proxy replaces with the key.
        """
        return self.model_copy(update={"token_env": env})

    def env(self, token: str) -> dict[str, str]:
        """The variables of a creation request that give the server its bearer token `token`.

        Raises:
            ValueError: When the server takes no token.
        """
        if self.token_env is None:
            raise ValueError(f"the MCP server {self.name} takes no token")
        return {self.token_env: token}


class Mixin(BaseModel):
    """A mixin written in Python: a descriptor, listed under a reference.

    The crate checks it when it is made, as the forge checks the mixins it reads from their
    directories: the hosts of its rules, its commands, the fields it names. `Kit.mixins` takes
    it as it takes a directory; the forge sends it to the daemon as it is, and a kit cache
    given the `sbx` CLI writes it into a directory for the CLI.

    Attributes:
        reference: A path, as the CLI lists a local kit, whose last part names the mixin,
            e.g. `/kits/acme-tools`. The daemon finds the mixin by its image, so the path
            need not exist.
        descriptor: What the mixin declares.

    Raises:
        InvalidKitError: When the forge would refuse the mixin.
    """

    model_config = ConfigDict(frozen=True)

    reference: str
    descriptor: KitDescriptor

    @model_validator(mode="after")
    def _forgeable(self) -> Mixin:
        """Checks the mixin as the forge checks it."""
        _native.check_mixin(self.reference, self.descriptor.model_dump_json())
        return self

    @property
    def name(self) -> str:
        """The name of the mixin, the last part of its reference."""
        return self.reference.rstrip("/").rsplit("/", 1)[-1]

    @classmethod
    def read(cls, directory: str | os.PathLike[str]) -> Mixin:
        """The mixin of `directory`, described by its `spec.yaml` written in JSON.

        It is listed under the canonical path of the directory.

        Raises:
            InvalidKitError: When the forge would refuse its descriptor.
            HostFileError: When the directory or its `spec.yaml` cannot be read.
        """
        reference, descriptor = _native.read_mixin(os.fspath(directory))
        return cls(reference=reference, descriptor=KitDescriptor.model_validate_json(descriptor))

    @classmethod
    def mcp(cls, agent: str, *servers: McpServer) -> Mixin:
        """The mixin that registers `servers` in the configuration of the agent `agent`.

        Built by the crate. Its install commands register the servers inside the sandbox, as
        the kit of the agent registers its MCP gateway: `claude mcp add`, as the user `agent`,
        for `claude`. It allows their hosts. The tokens are not part of it: they are given at
        creation, in the variables `token_env` of the servers (`McpServer.env()`), so that one
        package serves sandboxes with tokens of their own. Its reference is
        `/kits/docker-sandbox-mcp-<agent>`.

        Raises:
            InvalidKitError: For an agent without an MCP adapter (all but `claude` for now),
                no server, two servers of the same name, a name or a variable that is not
                one, or a URL that is not an http or https one or holds a character a shell
                command cannot carry.
        """
        reference, descriptor = _native.mcp_mixin(
            agent, [(server.name, server.url, server.token_env) for server in servers]
        )
        return cls(reference=reference, descriptor=KitDescriptor.model_validate_json(descriptor))
