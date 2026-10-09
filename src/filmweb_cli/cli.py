import asyncio
from typing import TYPE_CHECKING

import click

from .client import FilmwebClient
from .display.character_preview import print_character_preview
from .display.content_preview import print_content_preview
from .display.people_preview import print_person_preview
from .display.search import print_search_results
from .display.top_roles_preview import print_top_roles_preview
from .display.unseen import print_unseen
from .display.vod import print_where_to_watch, print_where_to_watch_compact
from .display.worlds_preview import print_world_preview
from .exceptions.exceptions import (
    ContentNotFoundError,
    FilmwebError,
    InvalidContentError,
    InvalidIdPrefixError,
    InvalidIdTypeError,
)
from .filmweb_types import ValidTypes
from .schemas.info.content_info import TitleInfo
from .schemas.info.rating import ContentRating
from .schemas.vod.vod_providers import VodProvider, WhereToWatch
from .services.info_service import InfoService
from .services.ranking_service import RankingService
from .services.search_service import SearchService
from .services.user_service import UserService
from .services.vod_service import VodService

if TYPE_CHECKING:
    from collections.abc import Sequence

    from .display.search import Displayable

MEDIA_TYPES = {ValidTypes.FILM, ValidTypes.SERIAL, ValidTypes.GAME}
VOD_TYPES = {ValidTypes.FILM, ValidTypes.SERIAL}


@click.group()
@click.pass_context
def main(ctx: click.Context) -> None:
    ctx.obj = FilmwebClient()


@main.command("search")
@click.argument("query")
@click.option("--raw", is_flag=True, hidden=True, help="Output raw format")
@click.pass_obj
def search(client: FilmwebClient, query: str, *, raw: bool) -> None:
    search_service = SearchService(client)
    search_results = asyncio.run(search_service.search(query))

    if raw:
        for type_prefix, category, items in [
            (ValidTypes.FILM.value, "FILM", search_results.get_films()),
            (ValidTypes.SERIAL.value, "SERIAL", search_results.get_series()),
            (ValidTypes.GAME.value, "GAME", search_results.get_games()),
            (ValidTypes.CHARACTER.value, "CHARACTER", search_results.get_characters()),
            (ValidTypes.PERSON.value, "PERSON", search_results.get_movie_people()),
            (ValidTypes.WORLD.value, "WORLD", search_results.get_worlds()),
        ]:
            for item in items:
                click.echo(f"{type_prefix}:{item.get_id()}\t[{category}] {item.display_name()}")
    else:
        categories: list[tuple[str, Sequence[Displayable]]] = [
            ("FILMS", search_results.get_films()),
            ("SERIAL", search_results.get_series()),
            ("GAMES", search_results.get_games()),
            ("CHARACTERS", search_results.get_characters()),
            ("PEOPLE", search_results.get_movie_people()),
            ("WORLDS", search_results.get_worlds()),
        ]
        print_search_results(categories)


@main.command("info")
@click.argument("content_id")
@click.option("--full", "-f", is_flag=True, hidden=True, help="Show full description")
@click.pass_obj
def show_info(client: FilmwebClient, content_id: str, *, full: bool) -> None:
    info_service = InfoService(client)

    try:
        parsed_type, parsed_id = _parse_content_input(content_id)
    except (InvalidIdTypeError, InvalidIdPrefixError) as e:
        click.echo(e, err=True)
        raise SystemExit(1) from e

    try:
        if parsed_type in MEDIA_TYPES:
            content_info, rating_info, critics_rating_info, full_description_info = asyncio.run(
                _fetch_media_info(info_service, parsed_id, full=full),
            )

            print_content_preview(
                content_info,
                rating_info,
                critics_rating_info,
                full_description_info,
                full_desc=full,
            )

        elif parsed_type == ValidTypes.PERSON:
            person_info = asyncio.run(info_service.get_person_preview(parsed_id))
            print_person_preview(person_info)

        elif parsed_type == ValidTypes.CHARACTER:
            character_info, content_info = asyncio.run(_fetch_character_info(info_service, parsed_id))
            print_character_preview(character_info, content_info)

        elif parsed_type == ValidTypes.WORLD:
            person_info = asyncio.run(info_service.get_world_preview(parsed_id))
            print_world_preview(person_info)

        else:
            click.echo(f"Unsupported content type: {parsed_type}")
            raise SystemExit(1)

    except ExceptionGroup as eg:
        _handle_exception_group(eg)
    except ContentNotFoundError as e:
        click.echo(e, err=True)
        raise SystemExit(1) from e
    except InvalidContentError as e:
        click.echo(e, err=True)
        raise SystemExit(1) from e


async def _fetch_media_info(info_service: InfoService, content_id: int, *, full: bool) -> tuple:
    desc_task = None

    async with asyncio.TaskGroup() as tg:
        preview_task = tg.create_task(info_service.get_content_preview(content_id))
        rating_task = tg.create_task(info_service.get_content_rating(content_id))
        critics_rating_task = tg.create_task(info_service.get_critics_content_rating(content_id))

        if full:
            desc_task = tg.create_task(info_service.get_full_description(content_id))

    desc = desc_task.result() if desc_task is not None else None

    return (
        preview_task.result(),
        rating_task.result(),
        critics_rating_task.result(),
        desc,
    )


async def _fetch_character_info(info_service: InfoService, character_id: int) -> tuple:
    async with asyncio.TaskGroup() as tg:
        preview_task = tg.create_task(info_service.get_character_preview(character_id))
        content_task = tg.create_task(info_service.get_character_content(character_id))

    return (preview_task.result(), content_task.result())


def _handle_exception_group(eg: ExceptionGroup) -> None:
    expected_errors, unexpected_errors = eg.split(
        lambda e: isinstance(e, (ContentNotFoundError, InvalidContentError)),
    )

    if unexpected_errors:
        raise unexpected_errors from eg

    if expected_errors:
        exc = expected_errors.exceptions[0]
        click.echo(exc, err=True)
        raise SystemExit(1) from exc


@main.command("vod")
@click.argument("content_id")
@click.option("--compact", "-c", is_flag=True, hidden=True, help="Compact display of vod providers")
@click.pass_obj
def show_vod_providers(client: FilmwebClient, content_id: str, *, compact: bool) -> None:
    try:
        parsed_type, parsed_id = _parse_content_input(content_id)
        if parsed_type not in VOD_TYPES:
            raise SystemExit(0)

        vod_service = VodService(client)

        vod_providers, content_vod_providers = asyncio.run(_fetch_vod_info(vod_service, parsed_id))

        vod_providers_by_id = {p.id: p for p in vod_providers}

        where_to_watch_list: list[WhereToWatch] = [
            WhereToWatch(
                content=cp,
                provider=vod_providers_by_id.get(cp.vod_provider),
            )
            for cp in content_vod_providers
        ]

        if compact:
            print_where_to_watch_compact(where_to_watch_list)
        else:
            print_where_to_watch(where_to_watch_list)

    except InvalidContentError as e:
        click.echo(e, err=True)
        raise SystemExit(1) from e


async def _fetch_vod_info(vod_service: VodService, content_id: int) -> tuple:
    async with asyncio.TaskGroup() as tg:
        vod_task = tg.create_task(vod_service.get_vod_providers())
        content_vod_task = tg.create_task(vod_service.get_content_vod_providers(content_id))

    return (vod_task.result(), content_vod_task.result())


@main.command("top")
@click.argument("content_id")
@click.pass_obj
def show_top_roles(client: FilmwebClient, content_id: str) -> None:
    try:
        parsed_type, parsed_id = _parse_content_input(content_id)
        if parsed_type not in MEDIA_TYPES:
            raise SystemExit(0)

        ranking_service = RankingService(client)

        top_roles = asyncio.run(ranking_service.get_content_top_roles(parsed_id))

        print_top_roles_preview(top_roles or [], max_value=10)

    except InvalidContentError as e:
        click.echo(e, err=True)
        raise SystemExit(1) from e


@main.command("unseen")
@click.argument("user_name")
@click.option("--vod", "vod_name", required=True, help="VOD provider name or id, e.g. 'Apple TV' or netflix")
@click.option("--since", type=int, help="Earliest production year")
@click.option("--min-votes", type=int, default=1000, show_default=True, help="Minimum number of community votes")
@click.option("--limit", type=int, default=20, show_default=True, help="Number of films to show")
@click.pass_obj
def show_unseen(  # noqa: PLR0913, PLR0917
    client: FilmwebClient,
    user_name: str,
    vod_name: str,
    since: int | None,
    min_votes: int,
    limit: int,
) -> None:
    try:
        films = asyncio.run(_find_unseen(client, user_name, vod_name, since, min_votes, limit))
    except FilmwebError as e:
        click.echo(e, err=True)
        raise SystemExit(1) from e

    print_unseen(films)


async def _find_unseen(  # noqa: PLR0913, PLR0917
    client: FilmwebClient,
    user_name: str,
    vod_name: str,
    since: int | None,
    min_votes: int,
    limit: int,
) -> list[tuple[TitleInfo, ContentRating]]:
    user_service = UserService(client)
    vod_service = VodService(client)
    info_service = InfoService(client)

    user_id, providers = await asyncio.gather(user_service.get_user_id(user_name), vod_service.get_vod_providers())
    provider = _match_vod_provider(providers, vod_name)

    voted, film_ids = await asyncio.gather(
        user_service.get_voted_ids(user_id),
        vod_service.get_provider_film_ids(provider.id, start_year=since),
    )
    candidates = [film_id for film_id in film_ids if film_id not in voted]

    ratings = await asyncio.gather(*(info_service.get_content_rating(film_id) for film_id in candidates))
    top = sorted(
        (
            (film_id, rating)
            for film_id, rating in zip(candidates, ratings, strict=True)
            if rating and rating.rate and (rating.count or 0) >= min_votes
        ),
        key=lambda item: item[1].rate or 0,
        reverse=True,
    )[:limit]

    infos = await asyncio.gather(*(info_service.get_title_info(film_id) for film_id, _ in top))

    return [(info, rating) for info, (_, rating) in zip(infos, top, strict=True)]


def _match_vod_provider(providers: list[VodProvider], vod_name: str) -> VodProvider:
    def normalize(value: str) -> str:
        return value.lower().replace(" ", "").replace("_", "").replace("+", "plus")

    wanted = normalize(vod_name)
    for provider in providers:
        if wanted in {str(provider.id), normalize(provider.name), normalize(provider.display_name)}:
            return provider

    available = ", ".join(sorted(p.display_name for p in providers))
    msg = f"Unknown VOD provider: {vod_name}. Available: {available}"
    raise InvalidContentError(msg)


def _parse_content_input(content_id: str) -> tuple[ValidTypes, int]:
    if ":" in content_id:
        type_prefix, numeric_id = content_id.split(":", 1)

        try:
            prefix = ValidTypes(type_prefix)
        except ValueError as err:
            valid_types = ", ".join([t.value for t in ValidTypes])
            msg = f"Invalid prefix: {type_prefix}. Available: {valid_types}"
            raise InvalidIdPrefixError(msg) from err

        if not numeric_id.isdecimal():
            msg = f"Invalid id type: {numeric_id} should be a number"
            raise InvalidIdTypeError(msg)

        return prefix, int(numeric_id)

    return ValidTypes.FILM, int(content_id)
