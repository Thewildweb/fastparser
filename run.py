import os
import asyncio

from fastparser.http_client import HttpClient
from fastparser.base_site import BaseSite


async def test_func_export():
    path = os.getcwd() + "/export.json"

    def page_func(site, item, response):
        print(item.url)
        print(item.status_code)
        if item.status_code != 200:
            return

        if title := item.page.css_first("title"):
            print(title)
            item.data["title"] = title.text()

        return

    site = BaseSite("https://www.oudaen-advocatuur.nl/", export_path=path)
    async with HttpClient() as client:
        await site.parse_sitemap(
            "https://www.oudaen-advocatuur.nl/post-sitemap.xml", client
        )
        print(site.sitemap)
        await site.run_site(client, page_func, add_links_to_sitemap=False, export=True)

    assert os.path.isfile(path)


if __name__ == "__main__":
    asyncio.run(test_func_export())