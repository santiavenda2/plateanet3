import asyncio
import aiohttp


PLATEANET_URL = "https://www.plateanet.com/"

async def fetch_page(client, url):
    async with client.get(url) as response:
        assert response.status == 200
        return await response.read()


def run_loop():
    loop = asyncio.get_event_loop()
    client = aiohttp.ClientSession(loop=loop)
    content = loop.run_until_complete(fetch_page(client, PLATEANET_URL))
    print(content)
    client.close()

if __name__ == '__main__':
    run_loop()