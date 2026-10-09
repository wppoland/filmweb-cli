import unittest
from collections.abc import Callable

import httpx

from filmweb_cli.cli import UnseenFilters, _find_unseen, _match_vod_provider
from filmweb_cli.client import FilmwebClient
from filmweb_cli.exceptions.exceptions import AuthRequiredError, InvalidContentError
from filmweb_cli.schemas.vod.vod_providers import VodProvider
from filmweb_cli.services.user_service import UserService

API = "/api/v1"
PROVIDERS = [
    {"id": 2, "name": "netflix", "displayName": "Netflix"},
    {"id": 15, "name": "apple_tv", "displayName": "Apple TV"},
    {"id": 31, "name": "disney_plus", "displayName": "Disney+"},
]
GENRES = {
    "pl_PL": [{"id": 6, "name": {"text": "Dramat"}}, {"id": 13, "name": {"text": "Komedia"}}],
    "en_US": [{"id": 6, "name": {"text": "Drama"}}, {"id": 13, "name": {"text": "Comedy"}}],
}


def make_client(handler: Callable[[httpx.Request], httpx.Response]) -> FilmwebClient:
    client = FilmwebClient()
    client.client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


class FakeApi:  # answers the endpoints used by `filmweb unseen` and records every search request
    def __init__(
        self,
        *,
        voted: list[int],
        hits: list[int],
        ratings: dict[int, tuple[float | None, int]],
        total: int | None = None,
    ) -> None:
        self.voted = voted
        self.hits = hits
        self.ratings = ratings
        self.total = len(hits) if total is None else total
        self.searches: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:  # noqa: PLR0911
        path = request.url.path.removeprefix(API)
        parts = path.split("/")
        if path == "/users/fsiun/id":
            return httpx.Response(200, json={"name": "fsiun", "userId": 431555})
        if path == "/vod/providers/list":
            return httpx.Response(200, json=PROVIDERS)
        if path == "/genres":
            return httpx.Response(200, json=GENRES[request.headers["x-locale"]])
        if path.endswith("/count"):
            return httpx.Response(200, json={"count": len(self.voted)})
        if path.startswith("/users/431555/votes/"):
            return httpx.Response(
                200,
                json={"votes": [{"id": {"id": i, "name": "x"}, "timestamp": 0} for i in self.voted]},
            )
        if path.endswith("s/search"):
            self.searches.append(request)
            page = int(request.url.params["page"])
            all_hits = self.hits or list(range(1, self.total + 1))
            return httpx.Response(
                200,
                json={"total": self.total, "searchHits": [{"id": i} for i in all_hits[(page - 1) * 10 : page * 10]]},
            )
        if parts[1] == "film" and parts[3] == "rating":
            title_id = int(parts[2])
            if title_id not in self.ratings:
                return httpx.Response(204)
            rate, count = self.ratings[title_id]
            return httpx.Response(200, json={"rate": rate, "count": count})
        if parts[1] == "title":
            return httpx.Response(200, json={"id": int(parts[2]), "title": f"T{parts[2]}"})
        return httpx.Response(404)


def filters(**kwargs: object) -> UnseenFilters:
    base: dict = {"vod_names": ("netflix",), "since": None, "until": None, "genre_names": (), "entity_name": "film"}
    return UnseenFilters(**(base | kwargs))


class MatchVodProviderTest(unittest.TestCase):
    providers = tuple(VodProvider.model_validate(p) for p in PROVIDERS)

    def test_matches_name_display_name_and_id(self) -> None:
        for wanted in ("netflix", "NETFLIX", "apple_tv", "Apple TV", "appletv", "15", "Disney+", "disney plus"):
            with self.subTest(wanted=wanted):
                self.assertIn(_match_vod_provider(list(self.providers), wanted).id, {2, 15, 31})
        self.assertEqual(_match_vod_provider(list(self.providers), "Disney+").id, 31)
        self.assertEqual(_match_vod_provider(list(self.providers), "Apple TV").id, 15)
        self.assertEqual(_match_vod_provider(list(self.providers), "2").id, 2)

    def test_unknown_lists_available(self) -> None:
        with self.assertRaisesRegex(InvalidContentError, "Unknown VOD provider: hbo. Available: Apple TV, Disney"):
            _match_vod_provider(list(self.providers), "hbo")


class VotesPagingTest(unittest.IsolatedAsyncioTestCase):
    async def test_first_page_has_no_page_param(self) -> None:
        pages: list[str | None] = []

        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/count"):
                return httpx.Response(200, json={"count": 250})
            pages.append(request.url.params.get("page"))
            return httpx.Response(200, json={"votes": [{"id": {"id": len(pages), "name": "x"}, "timestamp": 0}]})

        voted = await UserService(make_client(handler)).get_voted_ids(431555)

        self.assertCountEqual(pages, [None, "2", "3"])
        self.assertEqual(voted, {1, 2, 3})

    async def test_forbidden_page_raises_auth_required(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/count"):
                return httpx.Response(200, json={"count": 150})
            if request.url.params.get("page") == "2":
                return httpx.Response(403)
            return httpx.Response(200, json={"votes": []})

        with self.assertRaisesRegex(AuthRequiredError, "first 100 votes"):
            await UserService(make_client(handler)).get_voted_ids(431555)


class FindUnseenTest(unittest.IsolatedAsyncioTestCase):
    async def test_filters_and_sorts(self) -> None:
        api = FakeApi(
            voted=[1],
            hits=[1, 2, 3, 4, 5, 5, 6, 7, 8, 9, 10, 11],  # 5 listed twice, as with two providers
            ratings={
                1: (9.9, 5000),  # voted
                2: (9.8, 500),  # below min votes
                3: (None, 5000),  # no rate
                # 4 has no rating at all
                5: (7.0, 2000),
                6: (8.0, 2000),
                7: (6.0, 2000),
                8: (8.5, 1000),
                9: (5.0, 2000),
                10: (7.5, 2000),
                11: (9.0, 2000),  # page 2
            },
        )

        result = await _find_unseen(make_client(api), "fsiun", filters(), min_votes=1000, limit=4)

        self.assertEqual([info.id for info, _ in result], [11, 8, 6, 10])
        self.assertEqual([rating.rate for _, rating in result], [9.0, 8.5, 8.0, 7.5])
        params = api.searches[0].url.params
        self.assertEqual(api.searches[0].url.path, f"{API}/films/search")
        self.assertEqual(params.get_list("vodProviders"), ["2"])
        self.assertEqual((params["orderBy"], params["descending"], params["startCount"]), ("rate", "true", "1000"))
        self.assertNotIn("startYear", params)
        self.assertNotIn("genres", params)

    async def test_stops_scanning_once_enough_found(self) -> None:
        api = FakeApi(voted=[], hits=[], total=100, ratings={i: (5 + i / 100, 2000) for i in range(1, 101)})

        result = await _find_unseen(make_client(api), "fsiun", filters(), min_votes=1000, limit=1)

        # page 1 yields 10, pages 2-4 yield 30 more, which covers limit + buffer, so pages 5-10 are skipped
        self.assertEqual(sorted(int(r.url.params["page"]) for r in api.searches), [1, 2, 3, 4])
        self.assertEqual([info.id for info, _ in result], [40])

    async def test_serial_years_genres_and_providers(self) -> None:
        api = FakeApi(voted=[], hits=[], ratings={})
        unseen_filters = filters(
            vod_names=("Disney+", "15"),
            since=2010,
            until=2020,
            genre_names=("comedy", "Dramat"),
            entity_name="serial",
        )

        result = await _find_unseen(make_client(api), "fsiun", unseen_filters, min_votes=0, limit=5)

        self.assertEqual(result, [])
        request = api.searches[0]
        self.assertEqual(request.url.path, f"{API}/serials/search")
        self.assertEqual(request.url.params.get_list("vodProviders"), ["31", "15"])
        self.assertEqual(request.url.params.get_list("genres"), ["13", "6"])
        self.assertEqual((request.url.params["startYear"], request.url.params["endYear"]), ("2010", "2020"))
        self.assertNotIn("startCount", request.url.params)

    async def test_unknown_genre(self) -> None:
        api = FakeApi(voted=[], hits=[], ratings={})

        with self.assertRaisesRegex(InvalidContentError, "Unknown genre: horror. Available: Dramat, Komedia"):
            await _find_unseen(make_client(api), "fsiun", filters(genre_names=("horror",)), min_votes=0, limit=5)


if __name__ == "__main__":
    unittest.main()
