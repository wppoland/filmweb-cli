import asyncio
import os

import httpx
from httpx._types import QueryParamTypes

# ponytail: one global cap of 10 in-flight requests, raise it only if filmweb tolerates more
MAX_CONCURRENT_REQUESTS = 10


class FilmwebClient:
    def __init__(self) -> None:
        self.api_base = "https://www.filmweb.pl/api/v1"
        self.ajax_api_base = "https://www.filmweb.pl/ajax"
        cookie = os.environ.get("FILMWEB_COOKIE")
        self.client = httpx.AsyncClient(headers={"Cookie": cookie} if cookie else None)
        self.semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def _get(self, base_url: str, endpoint: str, *, params: QueryParamTypes | None = None) -> httpx.Response:
        async with self.semaphore:
            return await self.client.get(base_url + endpoint, params=params)

    async def get(self, endpoint: str, *, params: QueryParamTypes | None = None) -> httpx.Response:
        return await self._get(self.api_base, endpoint, params=params)

    async def get_ajax(self, endpoint: str, *, params: QueryParamTypes | None = None) -> httpx.Response:
        return await self._get(self.ajax_api_base, endpoint, params=params)
