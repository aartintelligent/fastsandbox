import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        upper = await sandbox.attach(["tr", "a-z", "A-Z"])
        output = await upper.collect("piped through the sandbox\n")
        print(output.stdout.decode(), end="")

        greeter = await sandbox.attach("read name; echo hello $name")
        await greeter.write("sandbox\n")
        await greeter.close_stdin()
        async for chunk in greeter:
            print(chunk.text, end="")


if __name__ == "__main__":
    fastsandbox.run(main())
