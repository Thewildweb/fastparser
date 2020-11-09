import asyncio
import json
from typing import Optional, List, Dict, Union
from dataclasses import dataclass

import aiohttp

from .utilities import make_absolute, get_domain
from .errors import TerminalError, NonTerminalError


@dataclass
class HttpResponse:
    url: Optional[str] = None
    encoding: Optional[str] = None
    redirect: Optional[str] = None
    status_code: Optional[int] = None
    text: Optional[str] = None
    content: Optional[bytes] = None


class HttpClient:
    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 15,
        retries: int = 5,
        headers: Dict = {},
    ):
        self.proxy = proxy
        timeout = aiohttp.ClientTimeout(total=timeout)
        self.headers = headers
        self._client = aiohttp.ClientSession(timeout=timeout, headers=headers)
        self.retries = retries
        self.proxy = proxy

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._client.close()
        await asyncio.sleep(0.250)

    async def get(
        self, url: str, retries: Optional[int] = None, allow_redirects: bool = False
    ):
        request_args = {"url": url, "allow_redirects": allow_redirects}
        if self.proxy:
            request_args["proxy"] = self.proxy
        if retries is None:
            retries = self.retries
        try:
            async with self._client.get(**request_args) as resp:
                try:
                    text = await resp.text()
                except UnicodeDecodeError:
                    text = ""
                content = await resp.read()
                return await self._create_response(resp, text, content)
        except aiohttp.client_exceptions.ServerDisconnectedError:
            if retries > 0:
                retries -= 1
                return await self.get(url, retries)
        except aiohttp.InvalidURL:
            # return None and continue the program
            return None
        except aiohttp.ClientProxyConnectionError as e:
            raise TerminalError("Proxy error is raised")
        except aiohttp.ClientSSLError as e:
            raise NonTerminalError(f"SSL error. Url: {url}")
        except asyncio.exceptions.TimeoutError:
            if retries > 0:
                retries -= 1
                return await self.get(url, retries)
            else:
                raise NonTerminalError(f"ServerTimeout at: {url}")
        except aiohttp.ClientError as e:
            raise TerminalError("Client error is raised")

    @staticmethod
    async def _create_response(resp, text: str, content: bytes) -> HttpResponse:
        status = resp.status
        url = str(resp.url)
        if 300 < status < 320:
            redirect = make_absolute(resp.headers["location"], get_domain(url))
            print(redirect)
        else:
            redirect = None
        encoding = resp.get_encoding()
        return HttpResponse(
            url=url,
            encoding=encoding,
            redirect=redirect,
            status_code=status,
            text=text,
            content=content,
        )


LUA_SRC = """function main(splash, args)
  splash:set_user_agent("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36")
  assert(splash:go(args.url))
  assert(splash:wait(0.5))
  return {
      html = splash:html(),
      har = splash:har(),
  }
end
"""


class SplashClient:
    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 15,
        retries: int = 3,
        splash_url: str = "http://localhost:8050/execute",
    ):
        self.proxy = proxy
        timeout = aiohttp.ClientTimeout(total=timeout)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36"
        }
        self._client = aiohttp.ClientSession(timeout=timeout, headers=headers)
        self.retries = retries
        self.splash_url = splash_url
        self.splash_script = LUA_SRC
        self.proxy = proxy

    async def __aenter__(
        self,
    ):
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self._client.close()
        await asyncio.sleep(0.250)

    async def get(self, url: str, retries: Optional[int] = None) -> HttpResponse:
        data = {
            "lua_source": self.splash_script,
            "url": url,
        }

        if self.proxy:
            data["proxy"] = self.proxy

        if retries:
            tries = retries
        else:
            tries = self.retries

        try:
            async with self._client.post(self.splash_url, json=data) as resp:
                text = await resp.text()
                return self.http_response(text, url)

        except Exception as e:
            print(e)
            if tries > 0:
                tries -= 1
                return await self.get(url, tries)

    @staticmethod
    def http_response(splash_response, url: str) -> HttpResponse:
        resp_dict = json.loads(splash_response)

        status_code = int(resp_dict["har"]["log"]["entries"][0]["response"]["status"])

        if status_code == 200:
            text = resp_dict["html"]
            content = resp_dict["html"].encode("utf-8")
        else:
            text = ""
            content = b""

        if 300 < status_code < 320:
            redirect = resp_dict["har"]["log"]["entries"][0]["response"]["redirectURL"]
        else:
            redirect = None

        return HttpResponse(
            status_code=status_code,
            text=text,
            content=content,
            redirect=redirect,
            url=url,
        )
