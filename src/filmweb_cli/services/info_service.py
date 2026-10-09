import asyncio
from typing import Annotated

from pydantic import Field, TypeAdapter

from filmweb_cli.client import FilmwebClient
from filmweb_cli.schemas.info.content_info import FilmInfo, FullDescription, GameInfo, SeriesInfo, TitleInfo
from filmweb_cli.schemas.info.people_characters_info import CharacterContentResponse, CharacterInfo, PersonInfo
from filmweb_cli.schemas.info.rating import ContentRating, Rating
from filmweb_cli.schemas.info.worlds import WorldInfo
from filmweb_cli.services.base_service import BaseService

ContentPreview = Annotated[FilmInfo | SeriesInfo | GameInfo, Field(discriminator="entity_name")]
CONTENT_PREVIEW_ADAPTER = TypeAdapter(ContentPreview)


class InfoService(BaseService):
    def __init__(self, client: FilmwebClient) -> None:
        self.client = client

    async def get_content_preview(self, content_id: int) -> ContentPreview:
        info_response = await self.client.get(f"/film/{content_id}/preview")

        self._validate_response(info_response, content_id)

        return CONTENT_PREVIEW_ADAPTER.validate_python(info_response.json())

    async def get_content_rating(self, content_id: int) -> ContentRating | None:
        rating_response = await self.client.get(f"/film/{content_id}/rating")

        if not self._validate_response(rating_response, content_id, allow_missing=True):
            return None

        return ContentRating.model_validate(rating_response.json())

    async def get_critics_content_rating(self, content_id: int) -> Rating | None:
        critics_rating_response = await self.client.get(f"/film/{content_id}/critics/rating")

        if not self._validate_response(critics_rating_response, content_id, allow_missing=True):
            return None

        return Rating.model_validate(critics_rating_response.json())

    async def get_full_description(self, content_id: int) -> FullDescription | None:
        description_response = await self.client.get(f"/film/{content_id}/description")

        if not self._validate_response(description_response, content_id, allow_missing=True):
            return None

        return FullDescription.model_validate(description_response.json())

    async def get_person_preview(self, person_id: int) -> PersonInfo:
        person_raw_response = await self.client.get(f"/person/{person_id}/preview")

        self._validate_response(person_raw_response, person_id)

        response = PersonInfo.model_validate(person_raw_response.json())

        await self._fetch_person_content(response)

        return response

    async def _fetch_person_content(self, response: PersonInfo) -> None:
        tasks = [self.get_content_preview(content_id) for content_id in response.content_known_for]

        if not tasks:
            return

        details = await asyncio.gather(*tasks)

        titles: list[str] = []

        for item in details:
            if item:
                title = item.title.title if item.title else item.original_title.title
                titles.append(title)

        response.known_for_titles = titles

    async def get_character_preview(self, character_id: int) -> CharacterInfo:
        character_response = await self.client.get(f"/character/{character_id}/preview")

        self._validate_response(character_response, character_id)

        return CharacterInfo.model_validate(character_response.json())

    async def get_character_content(self, character_id: int) -> CharacterContentResponse:
        content_raw_response = await self.client.get_ajax(f"/character/filmIds/{character_id}")
        response = CharacterContentResponse.model_validate(content_raw_response.json())

        await self._fetch_character_content(response)

        return response

    async def _fetch_character_content(self, response: CharacterContentResponse) -> None:
        tasks = []
        category_map = []

        for category, ids_list in response.content_known_for.items():
            for content_id in ids_list:
                tasks.append(self.get_content_preview(content_id))
                category_map.append(category)

        if not tasks:
            return

        results = await asyncio.gather(*tasks)

        titles_dict: dict[str, list[str]] = {}

        for category, item in zip(category_map, results, strict=True):
            if item:
                title = item.title.title if item.title else item.original_title.title

                if category not in titles_dict:
                    titles_dict[category] = []

                titles_dict[category].append(title)

        response.known_for_titles = titles_dict

    async def get_world_preview(self, world_id: int) -> WorldInfo:
        world_response = await self.client.get(f"/world/{world_id}/preview")

        self._validate_response(world_response, world_id)

        return WorldInfo.model_validate(world_response.json())

    async def get_title_info(self, content_id: int) -> TitleInfo:
        title_response = await self.client.get(f"/title/{content_id}/info")

        self._validate_response(title_response, content_id)

        return TitleInfo.model_validate(title_response.json())
