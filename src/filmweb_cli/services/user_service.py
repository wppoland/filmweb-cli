import asyncio
import math

import httpx

from filmweb_cli.client import FilmwebClient
from filmweb_cli.exceptions.exceptions import AuthRequiredError, ContentNotFoundError
from filmweb_cli.schemas.user import UserId, VotesPage

from .base_service import BaseService

VOTES_PAGE_SIZE = 100


class UserService(BaseService):
    def __init__(self, client: FilmwebClient) -> None:
        self.client = client

    async def get_user_id(self, user_name: str) -> int:
        response = await self.client.get(f"/users/{user_name}/id")

        if response.status_code == httpx.codes.NO_CONTENT:
            msg = f"User not found: {user_name}"
            raise ContentNotFoundError(msg)

        response.raise_for_status()
        return UserId.model_validate(response.json()).user_id

    async def get_voted_ids(self, user_id: int, entity_name: str = "film") -> set[int]:
        count_response = await self.client.get(f"/users/{user_id}/votes/{entity_name}/count")
        count_response.raise_for_status()
        pages = math.ceil(count_response.json()["count"] / VOTES_PAGE_SIZE)

        results = await asyncio.gather(*(self._get_votes_page(user_id, entity_name, p) for p in range(1, pages + 1)))

        return {vote.entity.id for page in results for vote in page.votes}

    async def _get_votes_page(self, user_id: int, entity_name: str, page: int) -> VotesPage:
        # the API rejects page=1, the first page is served without the param
        params = {"page": page} if page > 1 else None
        response = await self.client.get(f"/users/{user_id}/votes/{entity_name}", params=params)

        if response.status_code == httpx.codes.FORBIDDEN:
            msg = (
                "Filmweb serves only the first 100 votes without a login. "
                "Set FILMWEB_COOKIE to the JWT cookie of a logged-in session, e.g. FILMWEB_COOKIE='JWT=...'"
            )
            raise AuthRequiredError(msg)

        response.raise_for_status()
        return VotesPage.model_validate(response.json())
