import fastsandbox
from fastsandbox.models import PortBinding


async def main() -> None:
    client = await fastsandbox.connect()
    # Published from the start, and again at every start.
    web = PortBinding.tcp(8000, 48000)
    async with client.create(kit="shell", ports=[web]) as sandbox, sandbox.running():
        for port in await sandbox.ports():
            print(f"{port.host_ip or '127.0.0.1'}:{port.host_port} -> {port.sandbox_port}")

        # Published on the running sandbox, then taken back.
        published = await sandbox.publish(PortBinding.tcp(9000, 49000, host_ip="127.0.0.1"))
        print(f"published: {[port.host_port for port in published]}")
        await sandbox.unpublish(*published)


if __name__ == "__main__":
    fastsandbox.run(main())
