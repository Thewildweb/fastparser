import asyncio
import os
import json

import pytest
import pytest_check as check
from selectolax.parser import HTMLParser

from fastparser.http_client import HttpClient
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
    assert item.path == "/amsterdam/"
    assert item.url == "https://www.getevents.nl/amsterdam/"
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


def test_item_to_sitemap():
    site = BaseSite("https://www.getevents.nl")
    item = SitemapItem(1, "https://www.getevents.nl/amsterdam/")
    site.item_to_sitemap(item)
    assert site.sitemap[item.url] == item


def update_item_sitemap():
    """Ik weet niet meer wat ik hiermee wilde aantonen"""
    site = BaseSite("https://www.getevents.nl")
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
    async with HttpClient() as client:
        r = await site.get_url("https://www.inspectelement.nl", client)

    assert r.status_code == 200


async def test_basesite_digest():
    site = BaseSite("https://www.getevents.nl")
    item = site.get_unvisited_item()

    async with HttpClient() as client:
        r = await site.get_url(item.url, client)

    site.digest_response(item, r)
    home = site.sitemap[item.url]

    assert home.status_code == 200
    assert (
        home.page.css_first("title").text()
        == "Get Events - De leukste Groepsuitjes en Bedrijfsfeesten"
    )
    assert len(site.sitemap) == 40


async def test_basesite_digest_redirect_home():
    site = BaseSite("https://www.python.org")
    item = site.get_unvisited_item()
    async with HttpClient() as client:
        r = await site.get_url(item.url, client)
        site.digest_response(item, r)
        # add a wrong url to sitemap
        # /download redirects to /downloads
        wrong_item = SitemapItem(1, "https://www.python.org/download/")
        site.item_to_sitemap(wrong_item)
        r2 = await site.get_url(wrong_item.url, client)
        print(r2.redirect)
        print(r2.url)
        site.digest_response(wrong_item, r2)
    print(wrong_item.status_code)
    assert wrong_item.status_code in [301, 302, 308]
    assert wrong_item.url == "https://www.python.org/download/"
    assert site.sitemap.get("https://www.python.org/downloads/")


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
    async with HttpClient() as client:
        await site.build_site(client, max_depth=1, max_pages=100)
    depth_list = [
        item.depth for item in site.sitemap.values() if item.status_code is not None
    ]
    assert 2 not in depth_list


async def test_basesite_max_page():
    site = BaseSite("https://www.moovemarketing.nl")
    async with HttpClient() as client:
        await site.build_site(client, max_depth=1, max_pages=5)
    visited_list = [
        item for item in site.sitemap.values() if item.status_code is not None
    ]
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

    async with HttpClient() as client:
        await site.run_site(client, page_func, max_depth=1, max_pages=5)

    title_list = [item.data.get("title") for item in site.sitemap.values()]
    assert len(title_list)
    assert "(Online) video marketing bureau » Moove Marketing" in title_list


async def test_parse_sitemap():
    site = BaseSite("https://moovemarketing.nl/")
    async with HttpClient() as client:
        await site.parse_sitemap("https://moovemarketing.nl/post-sitemap.xml", client)

    assert len(site.sitemap.keys()) > 15


async def test_func_export():
    path = os.getcwd() + "/export.json"

    def page_func(site, item, response):
        if item.status_code != 200:
            return

        if title := item.page.css_first("title"):
            item.data["title"] = title.text()

        return

    site = BaseSite("https://moovemarketing.nl", export_path=path)
    async with HttpClient() as client:
        await site.parse_sitemap("https://moovemarketing.nl/post-sitemap.xml", client)
        print(site.sitemap)
        await site.run_site(client, page_func, add_links_to_sitemap=False, export=True)

    assert os.path.isfile(path)

    with open(path, "r") as export_file:
        export_list = export_file.read().split("\n")

    first_item = json.loads(export_list[0])
    assert first_item.get("title")
