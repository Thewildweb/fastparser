import asyncio
import re
import os

import pytest
import pytest_check as check
from selectolax.parser import HTMLParser
import httpx

from fastparser.utilities import make_absolute
from fastparser.base_parser import Ahref, BasePage
from fastparser.base_site import BaseSite, SitemapItem


pytestmark = pytest.mark.asyncio


def test_create_sitemapitem():
    item = SitemapItem(depth=0, url="https://www.getevents.nl")
    assert item.path == ""
    assert item.url == "https://www.getevents.nl"
    assert item.depth == 0


def test_create_sitemapitem_path():
    item = SitemapItem(depth=1, url="https://www.getevents.nl/amsterdam/")
    assert item.path == "/amsterdam"
    assert item.url == "https://www.getevents.nl/amsterdam"
    assert item.depth == 1


def test_sitemapitem_trim_url():
    item = SitemapItem(depth=1, url="https://www.getevents.nl/ams?uitje=ja")
    assert item.path == "/ams"


def test_sitemapitem_update():
    item1 = SitemapItem(depth=2, url="https://www.getevents.nl/amsterdam")
    item1.depth = 1
    item1.status_code = 200
    assert item1.depth == 1
    assert item1.status_code == 200
    # depth cannot increase
    item1.depth = 2
    assert item1.depth == 1


def test_sitemapitem_eq():
    item1 = SitemapItem(depth=1, url="https://www.getevents.nl/amsterdam")
    item2 = SitemapItem(
        depth=2, url="https://www.getevents.nl/amsterdam?uitje=vrijgezellenfeest"
    )
    assert item1 == item2


def test_base_site_setup():
    site = BaseSite("https://www.getevents.nl")
    assert site.domain == "www.getevents.nl"
    assert site.scheme == "https"


def test_not_valid_url():
    with pytest.raises(ValueError):
        site = BaseSite("getevents.nl")


def item_to_sitemap():
    site = BaseSite("https://www.getevents.nl")
    item = SitemapItem(1, "https://www.getevents.nl/amsterdam/")
    site.append_to_sitemap(item)
    site.sitemap[item.url] == item


def update_item_sitemap():
    site = BaseBsite("https://www.getevents.nl")
    item = SitemapItem(2, "https://www.getevents.nl/amsterdam/")
    site.item_to_sitemap(item)
    item2 = site.sitemap[item2.path]
    item2.status_code = 301
    item2.redirect = "https://www.getevents.nl/ams/"
    assert item.status_code == 301
    assert item.redirect == "https://www.getevent.nl/ams/"


def test_get_unvisited_item():
    site = BaseSite("https://www.moovemarketing.nl")
    item = site.get_unvisited_item()
    assert item.url == "https://www.moovemarketing.nl"
    item = site.get_unvisited_item(0)
    assert item.url == "https://www.moovemarketing.nl"
    item = site.get_unvisited_item(1)
    assert item.url == "https://www.moovemarketing.nl"


def test_get_unvitied_url_max_depth():
    site = BaseSite("https://www.getevents.nl")
    item = SitemapItem(2, "https://www.getevents.nl/amsterdam")
    site.item_to_sitemap(item)
    home = site.sitemap["https://www.getevents.nl"]
    # simulate a visit with status code 200
    home.status_code = 200

    # get items with more depth than item
    get_item = site.get_unvisited_item(max_depth=1)
    assert get_item is None

    # get items with the same depth as item
    get_item2 = site.get_unvisited_item(max_depth=2)
    assert get_item2.path == "/amsterdam"

    # simulate a visit with status_doe 404
    get_item2.status_code = 404
    get_item2 = site.get_unvisited_item(max_depth=2)
    assert get_item2 is None


async def test_basesite_get():
    site = BaseSite("https://www.inspectelement.nl")
    client = httpx.AsyncClient()
    r = await site.get_url("https://www.inspectelement.nl", client)
    await client.aclose()
    assert r.status_code == 200


async def test_basesite_digest():
    site = BaseSite("https://www.getevents.nl")
    item = site.get_unvisited_item()
    client = httpx.AsyncClient()
    r = await site.get_url(item.url, client)
    await client.aclose()
    site.digest_response(item, r)
    home = site.sitemap[item.url]
    assert home.status_code == 200
    assert (
        home.page.css_first("title").text()
        == "Get Events - De leukste Groepsuitjes en Bedrijfsfeesten"
    )
    assert len(site.sitemap) == 39


async def test_basesite_digest_redirect_home():
    site = BaseSite("https://www.python.org")
    item = site.get_unvisited_item()
    client = httpx.AsyncClient()
    r = await site.get_url(item.url, client)
    site.digest_response(item, r)
    # add a wrong url to sitemap
    # /download redirects to /downloads
    wrong_item = SitemapItem(1, "https://www.python.org/download/")
    site.item_to_sitemap(wrong_item)
    r2 = await site.get_url(wrong_item.url, client)
    print(r2.history)
    print(r2.url)
    site.digest_response(wrong_item, r2)
    await client.aclose()
    print(wrong_item.status_code)
    assert wrong_item.status_code in [301, 302, 308]
    assert wrong_item.redirect == "https://www.python.org/downloads/"
    assert site.sitemap.get("https://www.python.org/downloads")


async def test_basesite_unvisited_url_depth():
    site = BaseSite("https://www.moovemarketing.nl")
    item = site.get_unvisited_item()
    item.status_code = 200
    new_item = SitemapItem(depth=2, url="https://www.moovemarketing.nl/video")
    site.sitemap[new_item.url] = new_item
    assert site.get_unvisited_item(max_depth=1) is None
    assert site.get_unvisited_item(max_depth=2)


async def test_basesite_build_site():
    site = BaseSite("https://pypi.org/")
    client = httpx.AsyncClient()
    await site.build_site(client, max_depth=1, max_pages=100)
    await client.aclose()
    depth_list = [
        item.depth for item in site.sitemap.values() if item.status_code is not None
    ]
    assert 2 not in depth_list


async def test_basesite_max_page():
    site = BaseSite("https://www.moovemarketing.nl")
    client = httpx.AsyncClient()
    await site.build_site(client, max_depth=1, max_pages=5)
    await client.aclose()
    visited_list = [item for item in site.sitemap.values() if item.status_code is not None]
    assert len(visited_list) == 5


async def test_run_basesite_function():
    site = BaseSite("https://moovemarketing.nl")

    def page_func(site, item, response):
        if item.status_code != 200:
            print(item.status_code)
            return

        if title := item.page.css_first("title"):
            item.data["title"] = title.text()
        return

    client = httpx.AsyncClient()
    await site.run_site(client, page_func, max_depth=1, max_pages=5)
    await client.aclose()
    title_list = [item.data.get("title") for item in site.sitemap.values()]
    assert len(title_list)
    assert "(Online) video marketing bureau » Moove Marketing" in title_list
