import asyncio

import pytest

from fastparser.http_client import HttpClient, HttpResponse


pytestmark = pytest.mark.asyncio


async def test_get_site():
    url = "https://www.getevents.nl/"
    async with HttpClient() as client:
        r = await client.get(url)

    assert r.url == "https://www.getevents.nl/"
    assert r.status_code == 200
    assert isinstance(r.text, str)
    assert r.redirect == None


async def test_get_site_with_redirect():
    url = "https://www.getevents.nl/ams"
    async with HttpClient() as client:
        r = await client.get(url)

    assert r.url == "https://www.getevents.nl/ams"
    assert r.status_code == 301
    assert r.redirect == "https://www.getevents.nl/uitje/amsterdamse-avond/"