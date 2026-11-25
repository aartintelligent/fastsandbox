import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()

    # Awaited, the creation gives a sandbox that stays until it is deleted.
    creation = client.create("docs-kept", kit="shell", env={"MODE": "docs"}, cpus=2)
    kept = await creation
    assert creation.created is not None
    print(f"{kept.name} created: {creation.created.status}")

    # As a context manager, it deletes the sandbox on the way out.
    async with client.create("docs-scratch", kit="shell") as scratch:
        names = [info.name for info in await client.sandboxes.list()]
        print(f"sandboxes: {', '.join(names)}")
    print(f"{scratch.name} after the block: {await client.sandboxes.find(scratch.name)}")

    # The identifier returned at creation guards the deletion.
    await kept.delete(force=True, expected_id=creation.created.id)


if __name__ == "__main__":
    fastsandbox.run(main())
