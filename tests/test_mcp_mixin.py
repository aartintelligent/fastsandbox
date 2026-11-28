"""MCP servers given to the agent of a sandbox by a mixin, built and checked by the crate."""

from __future__ import annotations

import pytest

import fastsandbox
from fastsandbox import Kit, KitForge, LifecycleStep, McpServer, Mixin
from fastsandbox.exceptions import InvalidKitError
from fastsandbox.mixins import LifecycleCapability, NetworkCapability
from fastsandbox.testing import FakeDaemon

TOOLS = McpServer.host("project-tools", 47813)
"""A server of the host, reached from the sandbox under the name of the host."""

DOCS = McpServer.remote("docs", "https://mcp.example.com/v1?x#y").with_bearer_env("DOCS_TOKEN")
"""A remote server, sent the content of a variable of the sandbox as its bearer token."""

PATH = 'export PATH="$HOME/.local/bin:$HOME/.claude/local:$PATH"\n'
"""The first line of every command of the mixin: where the kit installs Claude Code."""


def test_a_server_of_the_host_is_reached_under_the_name_of_the_host() -> None:
    assert TOOLS.name == "project-tools"
    assert TOOLS.url == "http://host.docker.internal:47813/mcp"
    assert TOOLS.token_env == "DOCKER_SANDBOX_MCP_PROJECT_TOOLS_TOKEN"
    assert TOOLS.env("a-token") == {"DOCKER_SANDBOX_MCP_PROJECT_TOOLS_TOKEN": "a-token"}
    assert McpServer.model_validate_json(TOOLS.model_dump_json()) == TOOLS


def test_a_remote_server_takes_a_token_only_when_given_one() -> None:
    plain = McpServer.remote("docs", "https://mcp.example.com/mcp")
    assert plain.token_env is None
    with pytest.raises(ValueError, match="docs takes no token"):
        plain.env("a-token")
    assert plain.with_bearer_env("DOCS_TOKEN").env("a-token") == {"DOCS_TOKEN": "a-token"}


def test_the_mixin_registers_each_server_in_claude_and_allows_its_host() -> None:
    plain = McpServer.remote("plain", "https://plain.example.com/mcp")
    mixin = Mixin.mcp("claude", TOOLS, DOCS, plain)
    assert mixin.reference == "/kits/docker-sandbox-mcp-claude"
    assert mixin.name == "docker-sandbox-mcp-claude"
    assert mixin.descriptor.display_name == "MCP servers for claude"
    assert (
        mixin.descriptor.description == "Registers 3 MCP server(s) in the configuration of claude"
    )
    lifecycle, network = mixin.descriptor.capabilities
    assert isinstance(lifecycle, LifecycleCapability)
    assert lifecycle.config.install == (
        LifecycleStep(
            command=PATH + "claude mcp add 'project-tools' 'http://host.docker.internal:47813/mcp'"
            " --transport http --scope user"
            ' --header "Authorization: Bearer $DOCKER_SANDBOX_MCP_PROJECT_TOOLS_TOKEN"',
            user="agent",
            description="Registers the MCP server project-tools",
            env=("DOCKER_SANDBOX_MCP_PROJECT_TOOLS_TOKEN",),
        ),
        LifecycleStep(
            command=PATH + "claude mcp add 'docs' 'https://mcp.example.com/v1?x#y'"
            ' --transport http --scope user --header "Authorization: Bearer $DOCS_TOKEN"',
            user="agent",
            description="Registers the MCP server docs",
            env=("DOCS_TOKEN",),
        ),
        LifecycleStep(
            command=PATH + "claude mcp add 'plain' 'https://plain.example.com/mcp'"
            " --transport http --scope user",
            user="agent",
            description="Registers the MCP server plain",
        ),
    )
    assert isinstance(network, NetworkCapability)
    assert network.config.runtime.allow == (
        "host.docker.internal:47813",
        "mcp.example.com",
        "plain.example.com",
    )


@pytest.mark.parametrize(
    ("agent", "servers", "reason"),
    [
        ("codex", (TOOLS,), "codex has no MCP adapter yet: only claude has one"),
        ("someone", (TOOLS,), "not an agent sbx knows"),
        ("claude", (), "no MCP server to register"),
        ("claude", (TOOLS, TOOLS), "two MCP servers are named project-tools"),
        ("claude", (McpServer.host("a b", 1),), "is not a name of MCP server"),
        ("claude", (McpServer.host("mcp-gateway", 1),), "the gateway of the sandbox"),
        ("claude", (McpServer.remote("f", "ftp://example.com"),), "not an http or https one"),
        ("claude", (McpServer.remote("q", "https://example.com/'"),), "its command cannot carry"),
        ("claude", (McpServer.remote("h", "https:///mcp"),), "names no host"),
        ("claude", (DOCS.with_bearer_env("1BAD"),), "is not the name of an environment variable"),
    ],
    ids=["agent", "unknown", "none", "twice", "name", "gateway", "scheme", "quote", "host", "env"],
)
def test_a_mixin_the_crate_refuses_is_refused_when_made(
    agent: str, servers: tuple[McpServer, ...], reason: str
) -> None:
    with pytest.raises(InvalidKitError) as refused:
        Mixin.mcp(agent, *servers)
    assert reason in refused.value.reason


async def test_a_sandbox_gets_the_servers_and_its_own_token(
    client: fastsandbox.Client, daemon: FakeDaemon
) -> None:
    kit = Kit(base="claude", mixins=(Mixin.mcp("claude", TOOLS, DOCS),))
    assert kit.label == "claude+docker-sandbox-mcp-claude"
    package = await KitForge(client).forge(kit)
    assert package.kit_refs[1:] == ["/kits/docker-sandbox-mcp-claude"]
    async with client.create("job-1", kit=package, env=TOOLS.env("a-token")):
        request = daemon.sandboxes["job-1"]["request"]
        assert request["environment"] == {"DOCKER_SANDBOX_MCP_PROJECT_TOOLS_TOKEN": "a-token"}
        assert request["kits"] == package.kit_refs
