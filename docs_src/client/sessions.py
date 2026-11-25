import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    async with client.create("docs-sessions", kit="shell") as sandbox:
        info = await sandbox.stop()
        print(f"stopped: {info.status}")

        # Starts the sandbox if needed and keeps it running in the block.
        async with sandbox.running():
            info = await sandbox.inspect()
            print(f"in the block: {info.status}")

        # The same by hand: a session held, then released.
        session = await sandbox.ensure_running()
        try:
            print(f"session held on {session.sandbox}: {session.is_connected}")
        finally:
            session.release()


if __name__ == "__main__":
    fastsandbox.run(main())
