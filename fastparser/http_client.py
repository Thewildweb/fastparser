import asyncio
from typing import Optional, List, Dict, Union
from dataclasses import dataclass

import aiohttp

from .errors import TerminalError, NonTerminalError


@dataclass
class HttpRedirect:
    url: str
    status_code: int


@dataclass
class HttpResponse:
    url: Optional[str] = None
    encoding: Optional[str] = None
    redirect: Union[bool, HttpRedirect] = False
    status_code: Optional[int] = None
    text: Optional[str] = None
    content: Optional[bytes] = None


class HttpClient:
    def __init__(
        self,
        proxy: Optional[str] = None,
        timeout: int = 15,
        retries: int = 0,
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

    async def get(self, url: str, retries: Optional[int] = None):
        request_args = {"url": url}
        if self.proxy:
            request_args["proxy"] = self.proxy
        if retries is None:
            retries = self.retries
        try:
            resp = await self._client.get(**request_args)
            try:
                text = await resp.text()
            except UnicodeDecodeError:
                text = ""
            content = await resp.read()
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

        return await self._create_response(resp, text, content)

    @staticmethod
    async def _create_response(resp, text: str, content: bytes) -> HttpResponse:
        status = resp.status
        url = str(resp.url)
        if resp.history:
            redirect = HttpRedirect(
                url=str(resp.history[0].url), status_code=resp.history[0].status
            )
        else:
            redirect = False
        encoding = resp.get_encoding()
        return HttpResponse(
            url=url,
            encoding=encoding,
            redirect=redirect,
            status_code=status,
            text=text,
            content=content,
        )
