import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    # Forged without the `sbx` CLI on first use, then kept in memory.
    package = await client.package("shell")
    print(f"{', '.join(package.kit_refs)}, forged for the API {package.compiled_api}")

    # The package creates sandboxes through the socket alone.
    async with client.create(kit=package) as sandbox:
        print(f"{sandbox.name}: agent {(await sandbox.inspect()).agent}")


if __name__ == "__main__":
    fastsandbox.run(main())
