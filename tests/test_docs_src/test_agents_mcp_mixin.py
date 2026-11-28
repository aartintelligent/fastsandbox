"""`docs_src/agents/mcp_mixin.py`: its declaration; running the agent needs the real daemon,
a server of the host and a key."""

from __future__ import annotations

from collections.abc import Callable
from types import ModuleType

from fastsandbox import Kit, Mixin


def test_check_docs_gets_the_server_and_its_token(
    load_example: Callable[[str], ModuleType],
) -> None:
    example = load_example("agents/mcp_mixin.py")
    task = example.app.get_task("check_docs")
    assert task.agent is not None
    assert task.agent.name == "claude"
    assert example.tools.url == "http://host.docker.internal:47813/mcp"
    assert task.kit == Kit(base="claude", mixins=(Mixin.mcp("claude", example.tools),))
    assert task.env == {"DOCKER_SANDBOX_MCP_DOCS_TOOLS_TOKEN": example.TOKEN}
    assert task.timeout == 1200
