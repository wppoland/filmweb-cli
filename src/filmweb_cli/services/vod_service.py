import asyncio
import math
from collections.abc import AsyncIterator

from pydantic import TypeAdapter

from filmweb_cli.client import FilmwebClient
from filmweb_cli.schemas.vod.vod_providers import ContentVodProvider, Genre, VodFilmsPage, VodProvider
from filmweb_cli.services.base_service import BaseService

VOD_ADAPTER = TypeAdapter(list[VodProvider])
CONTENT_VOD_ADAPTER = TypeAdapter(list[ContentVodProvider])
GENRES_ADAPTER = TypeAdapter(list[Genre])
SEARCH_PAGES_PER_BATCH = 3  # the search API ignores every page size param, 10 hits per page is fixed


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

    async def get_genres(self, locale: str = "pl_PL") -> list[Genre]:
        response = await self.client.get("/genres", headers={"x-locale": locale})
        response.raise_for_status()
        return GENRES_ADAPTER.validate_python(response.json())

    async def iter_provider_title_ids(  # noqa: PLR0913
        self,
        provider_ids: list[int],
        *,
        entity_name: str = "film",
        start_year: int | None = None,
        end_year: int | None = None,
        genre_ids: list[int] | None = None,
        min_votes: int = 0,
    ) -> AsyncIterator[list[int]]:
        # yields title ids in rate order, a few search pages at a time, so callers can stop early
        params: dict[str, str | int | list[int]] = {
            "vodProviders": provider_ids,
            "orderBy": "rate",
            "descending": "true",
        }
        if start_year:
            params["startYear"] = start_year
        if end_year:
            params["endYear"] = end_year
        if genre_ids:
            params["genres"] = genre_ids
        if min_votes:
            params["startCount"] = min_votes

        path = f"/{entity_name}s/search"
        first = await self._get_search_page(path, params, 1)
        if not first.search_hits:
            return
        yield [hit.id for hit in first.search_hits]

        pages = math.ceil(first.total / len(first.search_hits))
        for start in range(2, pages + 1, SEARCH_PAGES_PER_BATCH):
            end = min(start + SEARCH_PAGES_PER_BATCH, pages + 1)
            batch = await asyncio.gather(*(self._get_search_page(path, params, p) for p in range(start, end)))
            yield [hit.id for page in batch for hit in page.search_hits]

    async def _get_search_page(self, path: str, params: dict[str, str | int | list[int]], page: int) -> VodFilmsPage:
        response = await self.client.get(path, params={**params, "page": page})
        response.raise_for_status()
        return VodFilmsPage.model_validate(response.json())
