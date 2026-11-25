import fastsandbox


async def main() -> None:
    client = await fastsandbox.connect()
    images = client.images
    for image in await images.list():
        print(f"{image.reference} {image.size or 0} bytes")

    # A pull followed as it happens; `images.pull()` waits for its end instead.
    reference = "docker.io/sbx/shell:latest"
    async with await images.pull_stream(reference) as progress:
        async for line in progress:
            if line.error is not None:
                raise RuntimeError(f"pull failed: {line.error}")
            print(f"pull: {line.status}")

    details = await images.inspect(reference)
    print(f"{reference}: user {details.user}, entrypoint {details.entrypoint}")
    print(f"unknown image held: {await images.exists('docker.io/library/no-such:image')}")


if __name__ == "__main__":
    fastsandbox.run(main())
