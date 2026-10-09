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

        results = await asyncio.gather(
            *(self._get_votes_page(user_id, entity_name, p) for p in range(1, pages + 1)),
            return_exceptions=True,
        )
        for result in results:
            if isinstance(result, BaseException):
                raise result

        return {vote.entity.id for page in results if isinstance(page, VotesPage) for vote in page.votes}

    async def _get_votes_page(self, user_id: int, entity_name: str, page: int) -> VotesPage:
        # the API rejects page=1, the first page is served without the param
        params = {"page": page} if page > 1 else None
        response = await self.client.get(f"/users/{user_id}/votes/{entity_name}", params=params)

        # later pages need a valid login: Filmweb answers 401, 403 or 500 for a missing, expired or broken cookie
        if page > 1 and response.status_code != httpx.codes.OK:
            msg = (
                "Filmweb serves only the first 100 votes without a valid login (missing or expired cookie). "
                "Set FILMWEB_COOKIE to the JWT cookie of a logged-in session, e.g. FILMWEB_COOKIE='JWT=...'"
            )
            raise AuthRequiredError(msg)

        response.raise_for_status()
        return VotesPage.model_validate(response.json())
