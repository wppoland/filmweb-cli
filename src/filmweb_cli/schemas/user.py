from pydantic import BaseModel, Field


class UserId(BaseModel):
    name: str
    user_id: int = Field(alias="userId")


class VoteEntity(BaseModel):
    id: int
    name: str


class Vote(BaseModel):
    entity: VoteEntity = Field(alias="id")
    timestamp: int


class VotesPage(BaseModel):
    votes: list[Vote] = Field(default_factory=list)
