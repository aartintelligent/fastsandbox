import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    # Compiled with the `sbx` CLI on first use, then read from the cache.
    package = await client.package("shell")
    print(f"{', '.join(package.kit_refs)}, compiled with sbx {package.compiled_with}")

    # The package creates sandboxes through the socket alone.
    async with client.create(kit=package) as sandbox:
        print(f"{sandbox.name}: agent {(await sandbox.inspect()).agent}")


if __name__ == "__main__":
    fastsandbox.run(main())
