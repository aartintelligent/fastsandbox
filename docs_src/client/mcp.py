import fastsandbox
from fastsandbox.models import McpServerCheck


async def main() -> None:
    client = await fastsandbox.connect()
    mode = await client.mcp.gateway_mode()
    print(f"gateway: {mode.decision}")

    # Whether the MCP policy lets `sbx mcp add` register this server.
    server = McpServerCheck.remote("docs-tools", "https://mcp.example.com/mcp")
    check = await client.mcp.check_registration(server)
    print(f"{check.name} may be registered: {check.allowed}")

    async with client.create(kit="shell") as sandbox, sandbox.running():
        # A server registered on the host with `sbx mcp add docs-tools ...`.
        await sandbox.load_mcp_server("docs-tools")
        gateway = await sandbox.mcp_gateway()
        print(f"{gateway.url} serves {gateway.servers}")
        await sandbox.unload_mcp_server("docs-tools")


if __name__ == "__main__":
    fastsandbox.run(main())
