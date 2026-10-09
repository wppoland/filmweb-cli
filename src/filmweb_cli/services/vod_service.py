import asyncio
import math

from pydantic import TypeAdapter

from filmweb_cli.client import FilmwebClient
from filmweb_cli.schemas.vod.vod_providers import ContentVodProvider, Genre, VodFilmsPage, VodProvider
from filmweb_cli.services.base_service import BaseService

VOD_ADAPTER = TypeAdapter(list[VodProvider])
CONTENT_VOD_ADAPTER = TypeAdapter(list[ContentVodProvider])
GENRES_ADAPTER = TypeAdapter(list[Genre])


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

    async def get_provider_title_ids(
        self,
        provider_ids: list[int],
        *,
        entity_name: str = "film",
        start_year: int | None = None,
        end_year: int | None = None,
        genre_ids: list[int] | None = None,
    ) -> list[int]:
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

        path = f"/{entity_name}s/search"
        first = await self._get_search_page(path, params, 1)
        if not first.search_hits:
            return []

        pages = math.ceil(first.total / len(first.search_hits))
        rest = await asyncio.gather(*(self._get_search_page(path, params, p) for p in range(2, pages + 1)))

        return list(dict.fromkeys(hit.id for page in (first, *rest) for hit in page.search_hits))

    async def _get_search_page(self, path: str, params: dict[str, str | int | list[int]], page: int) -> VodFilmsPage:
        response = await self.client.get(path, params={**params, "page": page})
        response.raise_for_status()
        return VodFilmsPage.model_validate(response.json())
