import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    pending = []
    async with await client.prompts.subscribe() as prompts:
        async for prompt in prompts:
            if prompt.is_synced:
                break
            pending.append(prompt)
    print(f"{len(pending)} prompts pending")


if __name__ == "__main__":
    fastsandbox.run(main())
