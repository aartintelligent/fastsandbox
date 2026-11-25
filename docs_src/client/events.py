import asyncio

import fastsandbox
from fastsandbox.models import EventKind


async def main() -> None:
    client = await fastsandbox.connect()
    events = await client.events.subscribe_live()

    async def watch() -> None:
        async for event in events:
            if event.kind is EventKind.SANDBOX_LIFECYCLE:
                print(event.action, event.sandbox_name)

    watcher = asyncio.create_task(watch())
    async with client.create(kit="shell"):
        await asyncio.sleep(1)
    await asyncio.sleep(1)
    watcher.cancel()
    await events.aclose()


if __name__ == "__main__":
    fastsandbox.run(main())
