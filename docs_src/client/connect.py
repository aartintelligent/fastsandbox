import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect(timeout=10, long_operation_timeout=600)
    health = client.health
    print(f"sbx {health.version}, API {health.api_version}, {health.status}")

    low, high = fastsandbox.SUPPORTED_API
    print(f"supported API: from {low} up to {high}, excluded")

    sandboxes = await client.sandboxes.list()
    print(f"{len(sandboxes)} sandboxes")


if __name__ == "__main__":
    fastsandbox.run(main())
