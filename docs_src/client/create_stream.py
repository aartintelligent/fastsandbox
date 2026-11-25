import fastsandbox
from fastsandbox.models import CreateFailure, CreateProgress, CreateResult


async def main() -> None:
    client = await fastsandbox.connect()
    package = await client.package("shell")
    # A request from the kit package, adjusted; its images loaded first.
    request = package.request("docs-stream").with_env(MODE="docs")
    await package.load_images(client)

    async with await client.sandboxes.create_stream(request) as events:
        async for event in events:
            match event:
                case CreateProgress(message=message):
                    print(f"progress: {message.strip()}")
                case CreateResult(created=created):
                    print(f"created {created.name}: {created.status}")
                case CreateFailure(message=message):
                    raise RuntimeError(f"creation failed: {message}")

    await client.sandbox("docs-stream").force_delete()


if __name__ == "__main__":
    fastsandbox.run(main())
