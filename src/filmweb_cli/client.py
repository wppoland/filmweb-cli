import os
from collections.abc import Mapping

import httpx
from httpx._types import QueryParamTypes


class FilmwebClient:
    def __init__(self) -> None:
        self.api_base = "https://www.filmweb.pl/api/v1"
        self.ajax_api_base = "https://www.filmweb.pl/ajax"
        cookie = os.environ.get("FILMWEB_COOKIE")
        self.client = httpx.AsyncClient(headers={"Cookie": cookie} if cookie else None)

    async def _get(
        self,
        base_url: str,
        endpoint: str,
        *,
        params: QueryParamTypes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        return await self.client.get(base_url + endpoint, params=params, headers=headers)

    async def get(
        self,
        endpoint: str,
        *,
        params: QueryParamTypes | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> httpx.Response:
        return await self._get(self.api_base, endpoint, params=params, headers=headers)

    async def get_ajax(self, endpoint: str, *, params: QueryParamTypes | None = None) -> httpx.Response:
        return await self._get(self.ajax_api_base, endpoint, params=params)
