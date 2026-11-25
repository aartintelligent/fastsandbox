from fastsandbox import AgentRunner, FastSandbox, Network

app = FastSandbox("agents")


@app.agent("claude", network=Network.allow("pypi.org"))
async def show_command(agent: AgentRunner, prompt: str) -> list[str]:
    """The command `agent.prompt(prompt)` would run, without running it."""
    return agent.command(prompt)
