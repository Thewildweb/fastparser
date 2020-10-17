import asyncio
from urllib.parse import urlparse, urlunparse
from typing import List, Tuple, Optional, Dict
from collections.abc import Iterable
import os

from .utilities import _URL
from .base_parser import Ahref, BasePage
from selectolax.parser import Node


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
        url = url.rstrip("/")
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


class BaseSite:
    """Base class for website"""

    def __init__(self, url: _URL):
        parsed_url = urlparse(url)
        if parsed_url.netloc == "":
            raise ValueError(f"{url} is not a valid url.")
        self.domain = parsed_url.netloc
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

    async def get_url(self, url: _URL, client):
        return await client.get(url)

    def digest_response(self, item: SitemapItem, response):
        self.digested += 1
        print(response.history)
        if len(response.history) > 0:
            item.status_code = response.history[0].status_code
            item.redirect = response.url
            # Create a new SitemapItem from the response.url with the same depth as depth
            redirect_item = SitemapItem(depth=item.depth, url=str(response.url))
            self.item_to_sitemap(redirect_item)
            return

        if response.status_code == 200:
            item.page = BasePage(response.text, str(response.url))
            item.status_code = response.status_code
            for a_href in item.page.internal_links:
                new_item = SitemapItem(depth=item.depth + 1, url=a_href.absolute_url)
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
        max_depth: Optional[int] = 2,
        max_pages: Optional[int] = 20,
    ):
        new_item = self.get_unvisited_item(max_depth=max_depth)
        while new_item and self.digested < max_pages:
            r = await self.get_url(new_item.url, client)
            self.digest_response(new_item, r)
            print(new_item.page)
            run = func(self, new_item, r)
            # if func return a value break the loop
            if run:
                break

