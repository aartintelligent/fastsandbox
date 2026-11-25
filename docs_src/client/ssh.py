import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create(kit="shell") as sandbox, sandbox.running():
        # A byte tunnel to the SSH server of the sandbox, through the socket.
        async with await sandbox.ssh_tunnel() as tunnel:
            greeting = b""
            while b"\n" not in greeting and (data := await tunnel.read()):
                greeting += data
        print(greeting.decode().strip())


if __name__ == "__main__":
    fastsandbox.run(main())
