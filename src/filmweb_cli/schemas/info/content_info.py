from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from filmweb_cli.schemas.people import Person


class TitleLocale(BaseModel):
    title: str
    country: str | None = None
    language: str | None = Field(default=None, alias="lang")
    original: bool = False


class Genre(BaseModel):
    id: int
    name: str

    @field_validator("name", mode="before")
    @classmethod
    def extract_text(cls, v: Any) -> str:  # noqa: ANN401
        if isinstance(v, dict) and "text" in v:
            return v["text"]
        return v


class FullDescription(BaseModel):  # not all information from api response is parsed here
    id: int
    text: str = Field(alias="synopsis")


class ContentInfo(BaseModel):  # not all information from api response is parsed here
    main_cast: list[Person] = Field(default_factory=list, alias="mainCast")
    directors: list[Person] = Field(default_factory=list)
    year: int
    title: TitleLocale | None = None
    original_title: TitleLocale = Field(alias="originalTitle")
    genres: list[Genre]
    duration: int | None = None
    description: str = Field(alias="plotOrDescriptionSynopsis")


class FilmInfo(ContentInfo):
    entity_name: Literal["film"] = Field(alias="entityName")
    sub_type: Literal["film_cinema", "film_tv", "film_video"] = Field(alias="subType")


class SeriesInfo(ContentInfo):
    entity_name: Literal["serial"] = Field(alias="entityName")
    sub_type: Literal["serial_tv", "mini_serial", "episode_anthology", "telenovela"] = Field(alias="subType")


class GameInfo(ContentInfo):
    entity_name: Literal["videogame"] = Field(alias="entityName")


class TitleInfo(BaseModel):  # not all information from api response is parsed here
    id: int
    title: str
    original_title: str | None = Field(default=None, alias="originalTitle")
    year: int | None = None
