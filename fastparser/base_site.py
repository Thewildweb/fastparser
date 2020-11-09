import asyncio
from urllib.parse import urlparse, urlunparse
from typing import Optional, Dict
import json
import os

from lxml import etree

from .http_client import HttpResponse
from .utilities import _URL
from .base_parser import BasePage


class SitemapItem:
    def __init__(
        self,
        depth: int,
        url: _URL,
        status_code: Optional[int] = None,
        page: Optional[BasePage] = None,
        redirect: Optional[_URL] = None,
    ):
        self._depth = depth
        # Trailing slashes will be trimmed
        parsed = urlparse(url)
        self.path = parsed.path
        self.url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))
        self.entry = None
        self.status_code = status_code
        self.page = page
        self.redirect = redirect
        self.data = {}

    def __hash__(self) -> int:
        return hash(self.path)

    def __eq__(self, other) -> bool:
        return self.__class__ == other.__class__ and self.path == other.path

    def __repr__(self):
        return f"<SitemapItem: {self.url}>"

    @property
    def depth(self):
        return self._depth

    @depth.setter
    def depth(self, depth: int):
        if depth < self._depth:
            self._depth = depth

    @property
    def json(self):
        export_dict = {"path": self.url, "status_code": self.status_code}
        export_dict.update(self.data)
        return json.dumps(export_dict)


class BaseSite:
    """Base class for website"""

    def __init__(self, url: _URL, export_path: Optional[str] = None):
        parsed_url = urlparse(url)
        if parsed_url.netloc == "":
            raise ValueError(f"{url} is not a valid url.")
        self.domain = parsed_url.netloc
        self.export_path = export_path if export_path else f"{self.domain}.json"
        self.scheme = parsed_url.scheme
        home_item = SitemapItem(0, f"{self.scheme}://{self.domain}")
        self.sitemap: Dict = {home_item.url: home_item}
        self.digested: int = 0

    @property
    def home_page(self):
        return f"{self.scheme}://{self.domain}"

    @property
    def pages(self):
        return [item.page for item in self.sitemap if item.page is not None]

    def __repr__(self) -> str:
        return f"<BaseSite: {self.domain}>"

    def item_to_sitemap(self, item: SitemapItem) -> None:
        if not self.sitemap.get(item.url):
            self.sitemap[item.url] = item

    def get_unvisited_item(self, max_depth: Optional[int] = None) -> SitemapItem:
        if max_depth:
            for sitemap_item in self.sitemap.values():
                if sitemap_item.status_code is None:
                    if sitemap_item.depth <= max_depth:
                        return sitemap_item
        else:
            for sitemap_item in self.sitemap.values():
                if sitemap_item.status_code is None:
                    return sitemap_item

    async def get_url(self, url: _URL, client) -> HttpResponse:
        return await client.get(url)

    def digest_response(
        self,
        item: SitemapItem,
        response: HttpResponse,
        add_links_to_sitemap: bool = True,
    ):
        self.digested += 1
        if 300 < response.status_code < 320:
            item.status_code = response.status_code
            redirect_item = SitemapItem(url=response.redirect, depth=item.depth)
            self.item_to_sitemap(redirect_item)
            return

        if response.status_code == 200:
            item.page = BasePage(response.text, response.url)
            item.status_code = response.status_code

            if add_links_to_sitemap:
                for a_href in item.page.internal_links:
                    if a_href.absolute_url and not a_href.absolute_url.endswith(".pdf"):
                        new_item = SitemapItem(
                            depth=item.depth + 1, url=a_href.absolute_url
                        )
                        self.item_to_sitemap(new_item)

        else:
            item.status_code = response.status_code

    async def build_site(
        self,
        client,
        max_depth: Optional[int] = 2,
        max_pages: Optional[int] = 20,
    ):
        new_page = self.get_unvisited_item(max_depth=max_depth)
        while new_page and self.digested < max_pages:
            r = await self.get_url(new_page.url, client)
            self.digest_response(new_page, r)
            new_page = self.get_unvisited_item(max_depth=max_depth)

    async def run_site(
        self,
        client,
        func,
        max_depth: Optional[int] = None,
        max_pages: Optional[int] = 20,
        add_links_to_sitemap: bool = True,
        export: bool = False,
        sleep: float = 0.5,
        delete_pages: bool = False,
    ):
        new_item = self.get_unvisited_item(max_depth=max_depth)
        while new_item and self.digested < max_pages:
            await asyncio.sleep(sleep)

            r = await self.get_url(new_item.url, client)

            self.digest_response(new_item, r, False)

            # gets the new_item or redirected item back
            self.digest_response(new_item, r, add_links_to_sitemap)

            if new_item.page:
                run = func(self, new_item, r)
            else:
                run = None
                print("No page to func")
                print(r.url)

            # export the page data
            if export and new_item is not None:
                self.export_page(new_item)

            if run:
                return

            # for big sites it is better to delete the pages
            if delete_pages:
                new_item.page = None

            new_item = self.get_unvisited_item(max_depth=max_depth)
            if not new_item:
                print("no new item")
                print(self.sitemap)

    async def parse_sitemap(
        self, sitemap_url: str, client, in_url: Optional[str] = None
    ):
        resp = await self.get_url(sitemap_url, client)
        if not resp:
            return

        parser = etree.XMLParser(recover=True)
        tree = etree.fromstring(resp.content, parser=parser)
        urlset = tree.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")

        for url in urlset:
            link = url.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc")

            if in_url:
                if in_url not in link.text:
                    continue

            new_item = SitemapItem(url=link.text, depth=10)
            self.item_to_sitemap(new_item)

    def export_page(self, item: SitemapItem):
        if not os.path.isfile(self.export_path):
            with open(self.export_path, "w") as export_file:
                export_file.write(item.json)
                export_file.write("\n")
            return

        with open(self.export_path, "a") as export_file:
            export_file.write(item.json)
            export_file.write("\n")