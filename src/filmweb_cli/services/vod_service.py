import asyncio
import math
from collections.abc import AsyncIterator

from pydantic import TypeAdapter

from filmweb_cli.client import FilmwebClient
from filmweb_cli.schemas.vod.vod_providers import ContentVodProvider, VodFilmsPage, VodProvider
from filmweb_cli.services.base_service import BaseService

VOD_ADAPTER = TypeAdapter(list[VodProvider])
CONTENT_VOD_ADAPTER = TypeAdapter(list[ContentVodProvider])
SEARCH_PAGES_PER_BATCH = 3  # films/search ignores every page size param, 10 hits per page is fixed


class VodService(BaseService):
    def __init__(self, client: FilmwebClient) -> None:
        self.client = client

    async def get_vod_providers(self) -> list[VodProvider]:
        vod_response = await self.client.get("/vod/providers/list")
        return VOD_ADAPTER.validate_python(vod_response.json())

    async def get_content_vod_providers(self, content_id: int) -> list[ContentVodProvider]:
        content_vod_response = await self.client.get(f"/vod/film/{content_id}/providers/list")

        self._validate_response(content_vod_response, content_id)

        return CONTENT_VOD_ADAPTER.validate_python(content_vod_response.json())

    async def iter_provider_film_ids(
        self,
        provider_id: int,
        *,
        start_year: int | None = None,
        min_votes: int = 0,
    ) -> AsyncIterator[list[int]]:
        # yields film ids in rate order, a few search pages at a time, so callers can stop early
        params: dict[str, str | int] = {"vodProviders": provider_id, "orderBy": "rate", "descending": "true"}
        if start_year:
            params["startYear"] = start_year
        if min_votes:
            params["startCount"] = min_votes

        first = await self._get_provider_films_page(params, 1)
        if not first.search_hits:
            return
        yield [hit.id for hit in first.search_hits]

        pages = math.ceil(first.total / len(first.search_hits))
        for start in range(2, pages + 1, SEARCH_PAGES_PER_BATCH):
            end = min(start + SEARCH_PAGES_PER_BATCH, pages + 1)
            batch = await asyncio.gather(*(self._get_provider_films_page(params, p) for p in range(start, end)))
            yield [hit.id for page in batch for hit in page.search_hits]

    async def _get_provider_films_page(self, params: dict[str, str | int], page: int) -> VodFilmsPage:
        response = await self.client.get("/films/search", params={**params, "page": page})
        response.raise_for_status()
        return VodFilmsPage.model_validate(response.json())
