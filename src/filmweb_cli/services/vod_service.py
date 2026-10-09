import asyncio
import math

from pydantic import TypeAdapter

from filmweb_cli.client import FilmwebClient
from filmweb_cli.schemas.vod.vod_providers import ContentVodProvider, VodFilmsPage, VodProvider
from filmweb_cli.services.base_service import BaseService

VOD_ADAPTER = TypeAdapter(list[VodProvider])
CONTENT_VOD_ADAPTER = TypeAdapter(list[ContentVodProvider])


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

    async def get_provider_film_ids(self, provider_id: int, *, start_year: int | None = None) -> list[int]:
        params: dict[str, str | int] = {"vodProviders": provider_id, "orderBy": "rate", "descending": "true"}
        if start_year:
            params["startYear"] = start_year

        first = await self._get_provider_films_page(params, 1)
        if not first.search_hits:
            return []

        pages = math.ceil(first.total / len(first.search_hits))
        rest = await asyncio.gather(*(self._get_provider_films_page(params, p) for p in range(2, pages + 1)))

        return [hit.id for page in (first, *rest) for hit in page.search_hits]

    async def _get_provider_films_page(self, params: dict[str, str | int], page: int) -> VodFilmsPage:
        response = await self.client.get("/films/search", params={**params, "page": page})
        response.raise_for_status()
        return VodFilmsPage.model_validate(response.json())
