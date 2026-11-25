"""Sandboxes: their description, creation, ports, mounts, templates and container swaps."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field

from ._base import Model
from .mcp import McpGateway

__all__ = [
    "CreateEvent",
    "CreateFailure",
    "CreateProgress",
    "CreateRequest",
    "CreateResult",
    "CreateUnknown",
    "Created",
    "HostMount",
    "PortBinding",
    "PullPolicy",
    "RuntimeMount",
    "SandboxInfo",
    "SandboxState",
    "SavedImage",
    "SkillsMode",
    "SwapOutcome",
    "SwapRequest",
    "Workspace",
]


class SandboxState(StrEnum):
    """The runtime states of a sandbox the library names.

    The daemon may report others, kept as plain strings.
    """

    RUNNING = "running"
    STOPPED = "stopped"


class PullPolicy(StrEnum):
    """When kit images are pulled during creation."""

    ALWAYS = "always"
    MISSING = "missing"
    NEVER = "never"


class SkillsMode(StrEnum):
    """How the shared skills store of the host reaches the sandbox."""

    OFF = "off"
    READONLY = "readonly"
    READWRITE = "readwrite"


class PortBinding(Model):
    """A port published from a sandbox to the host.

    Attributes:
        sandbox_port: Port inside the sandbox.
        host_port: Port on the host.
        host_ip: Address bound on the host; the daemon defaults to `127.0.0.1`.
        protocol: Protocol, e.g. `tcp`, `tcp4` or `udp`.
    """

    sandbox_port: int
    host_port: int
    host_ip: str | None = None
    protocol: str | None = None

    @classmethod
    def tcp(cls, sandbox_port: int, host_port: int, host_ip: str | None = None) -> PortBinding:
        """A TCP port."""
        return cls(sandbox_port=sandbox_port, host_port=host_port, host_ip=host_ip, protocol="tcp")

    @classmethod
    def udp(cls, sandbox_port: int, host_port: int, host_ip: str | None = None) -> PortBinding:
        """A UDP port."""
        return cls(sandbox_port=sandbox_port, host_port=host_port, host_ip=host_ip, protocol="udp")


class Workspace(Model):
    """A further host directory or file bind-mounted into a sandbox.

    Attributes:
        dir: Directory or file on the host, by its real absolute path.
        read_only: Whether the sandbox can only read it.
        target: Absolute path inside the sandbox; the path of `dir` when unset.
    """

    dir: str
    read_only: bool = False
    target: str | None = None


class HostMount(Model):
    """A host directory mounted into a sandbox.

    Attributes:
        host_path: Directory on the host.
        container_target: Mount point inside the sandbox.
        read_only: Whether the mount is read-only.
    """

    host_path: str
    container_target: str | None = None
    read_only: bool = False


class RuntimeMount(Model):
    """A host path granted to a running sandbox.

    Attributes:
        host_path: Directory on the host.
    """

    host_path: str


class SandboxInfo(Model):
    """A sandbox, as the daemon describes it.

    Attributes:
        id: Identifier assigned by the daemon; it guards deletion against a
            sandbox that took the same name.
        name: Sandbox name.
        agent: Agent of the base kit, e.g. `shell` or `claude`.
        status: Runtime state, e.g. `running` or `stopped`.
        created_at: Creation time (RFC 3339).
        last_used_at: Time of last use (RFC 3339).
        workspace: Host directory bind-mounted as workspace, empty when none.
        working_dir: Working directory recorded for the sandbox.
        effective_working_dir: Working directory actually used inside it.
        cpus: Number of virtual CPUs, when set explicitly.
        memory: Memory limit, when set explicitly (`sbx` notation, e.g. `2g`).
        host_mounts: Host directories mounted into the sandbox.
        runtime_mounts: Host paths granted at run time.
        ports: Published ports, in single-sandbox answers only.
        labels: Container labels set by `sbx`.
        credential_sources: Service credentials configured, by service.
    """

    id: str
    name: str
    agent: str
    status: str
    created_at: str | None = None
    last_used_at: str | None = None
    workspace: str = ""
    working_dir: str | None = None
    effective_working_dir: str | None = None
    cpus: int | None = None
    memory: str | None = None
    host_mounts: list[HostMount] = []
    runtime_mounts: list[RuntimeMount] = []
    ports: list[PortBinding] = []
    labels: dict[str, str] = {}
    credential_sources: dict[str, Any] = {}

    @property
    def is_running(self) -> bool:
        """Whether the sandbox is running."""
        return self.status == SandboxState.RUNNING


class Created(Model):
    """Outcome of a successful creation.

    Attributes:
        id: Identifier assigned by the daemon.
        name: Sandbox name.
        agent: Agent of the base kit.
        status: Runtime state right after creation.
        workspace: Workspace directory, empty when there is none.
        mcp: MCP gateway of the sandbox.
    """

    id: str
    name: str
    agent: str
    status: str
    workspace: str = ""
    mcp: McpGateway | None = None


class CreateRequest(Model):
    """The creation request of a sandbox.

    A kit package gives the request of its kit (`KitPackage.request`); adjust
    it with `model_copy(update=…)` or the `with_*` methods.

    Attributes:
        name: Sandbox name.
        agent: Agent of the base kit, e.g. `shell`.
        kits: Kit references, base kit first.
        kit_artifacts: Resolved kit artifacts, one per kit; opaque.
        pull_policy: When to pull kit images.
        template: Image the sandbox starts from instead of the image of its
            agent, such as one saved with `Sandbox.save`.
        cpus: Number of virtual CPUs.
        memory: Memory limit in `sbx` notation, e.g. `4g`.
        workspace: Host directory bind-mounted as workspace, at the same path
            inside the sandbox.
        additional_workspaces: Further host directories or files to mount.
        clone: Whether the agent works on a private clone of the Git
            repository of the workspace.
        environment: Environment variables of the sandbox.
        ports: Ports published from the start.
        skills: How the shared skills store reaches the sandbox.
        profile: Governance profile of the sandbox.
        mcp: MCP gateway configuration, e.g. `{"servers": [], "static": True}`.
        bindings_path: Host file recording the credentials the user approved.
        ssh_agent_socket_path: Host SSH agent socket to forward.
        enable_virtiofs_cache: Enables the virtio-fs cache for workspace mounts.
    """

    name: str
    agent: str
    kits: list[str] = []
    kit_artifacts: list[Any] = []
    pull_policy: PullPolicy | None = None
    template: str | None = None
    cpus: int | None = None
    memory: str | None = None
    workspace: str | None = None
    additional_workspaces: list[Workspace] = []
    clone: bool = False
    environment: dict[str, str] = {}
    ports: list[PortBinding] = []
    skills: SkillsMode | None = None
    profile: str | None = None
    mcp: Any = None
    bindings_path: str | None = None
    ssh_agent_socket_path: str | None = None
    enable_virtiofs_cache: bool | None = None

    def with_workspace(self, dir: str) -> CreateRequest:
        """The request, with `dir` of the host mounted as workspace."""
        return self.model_copy(update={"workspace": dir})

    def with_cloned_workspace(self, repository: str) -> CreateRequest:
        """The request, with the agent working on a private Git clone.

        The clone is of the repository `repository` of the host.
        """
        return self.model_copy(update={"workspace": repository, "clone": True})

    def with_additional_workspace(self, workspace: Workspace) -> CreateRequest:
        """The request, with one more mounted directory or file."""
        return self.model_copy(
            update={"additional_workspaces": [*self.additional_workspaces, workspace]}
        )

    def with_port(self, port: PortBinding) -> CreateRequest:
        """The request, with one more port published from the start."""
        return self.model_copy(update={"ports": [*self.ports, port]})

    def with_env(self, **variables: str) -> CreateRequest:
        """The request, with more environment variables."""
        return self.model_copy(update={"environment": {**self.environment, **variables}})

    def with_static_mcp_servers(self, *servers: str) -> CreateRequest:
        """The request, with an MCP gateway fixed to `servers`."""
        return self.model_copy(update={"mcp": {"servers": list(servers), "static": True}})


class CreateProgress(BaseModel):
    """A progress line of a creation.

    Attributes:
        message: What the daemon is doing, e.g. `assembled kit image ready`.
    """

    type: Literal["progress"] = "progress"
    message: str


class CreateResult(BaseModel):
    """The outcome of a creation, the last item of a successful stream.

    Attributes:
        created: The sandbox created.
    """

    type: Literal["result"] = "result"
    created: Created


class CreateFailure(BaseModel):
    """The failure of a creation, the last item of a failed stream.

    Attributes:
        message: Why the creation failed.
    """

    type: Literal["error"] = "error"
    message: str


class CreateUnknown(BaseModel):
    """A line of a creation stream the library does not know.

    Attributes:
        raw: The line, as the daemon sent it.
    """

    type: Literal["unknown"] = "unknown"
    raw: Any = None


CreateEvent = Annotated[
    CreateProgress | CreateResult | CreateFailure | CreateUnknown, Field(discriminator="type")
]
"""An item of the progress stream of a creation."""


class SavedImage(Model):
    """Image a sandbox was saved to.

    Attributes:
        image_id: Image identifier (`sha256:…`).
        tag: Fully qualified tag, e.g. `docker.io/library/snap:v1`.
    """

    image_id: str
    tag: str


class SwapRequest(Model):
    """A container swap: the complete kit list of the new container.

    Attributes:
        docker_name_override: Name of the replacement container.
        kit_artifacts: Resolved artifacts of the complete kit list; opaque.
        kit_refs: References of the complete kit list, base kit first.
    """

    docker_name_override: str
    kit_artifacts: list[Any]
    kit_refs: list[str]


class SwapOutcome(Model):
    """Outcome of a container swap.

    Attributes:
        committed_image_id: Image the previous container was committed to.
        container_id: Identifier of the new container.
        docker_name: Name of the new container.
    """

    committed_image_id: str | None = None
    container_id: str | None = None
    docker_name: str | None = None
