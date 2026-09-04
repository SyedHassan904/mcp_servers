from fastmcp import Client

client = Client("https://normal-gray-dinosaur.fastmcp.app/mcp")

async def main():
    async with client:
        print("Tools:")
        print(await client.list_tools())

        print("Resources:")
        print(await client.list_resources())

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())