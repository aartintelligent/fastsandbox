"""Kiro in a throw-away sandbox, with the MCP server of the examples.

The example registers itself as a local MCP server (`sbx mcp add`), checks it
against the MCP policy of the daemon, loads it into the gateway of the sandbox,
calls its `sum` tool from inside the sandbox, then starts the agent session:
ask the agent to call the `sum`, `echo` or `host_time` tool. The sandbox and
the registration are removed when the session ends. When `sbx` starts this
script as the MCP server, it serves MCP on its standard input and output
instead of running the example.

It takes the arguments of `agent-kiro`: the directory the agent works on,
mounted read-write at the same path, and arguments for the agent after `--`.

Credentials: none that `sbx` can inject for Kiro, which it knows no service
secret for. Sign in with the device flow the agent offers on first run, or set
`KIRO_API_KEY`, given to the agent process as is: its value is visible inside
the sandbox.

Run it with:

    just example agent-kiro-mcp
    just example agent-kiro-mcp ~/my-project
    just example agent-kiro-mcp ~/my-project -- "explain this project"
"""

from __future__ import annotations

from common import agent

if __name__ == "__main__":
    agent.main("kiro", with_mcp=True)
