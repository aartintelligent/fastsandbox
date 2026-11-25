import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        output = await sandbox.exec("uname -sm")
        print(output.stdout, end="")

        await sandbox.write_file("/tmp/hello.txt", "hello from the host\n")
        print(await sandbox.read_text("/tmp/hello.txt"), end="")

        await sandbox.deny_hosts("example.org")


if __name__ == "__main__":
    fastsandbox.run(main())
