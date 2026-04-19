from pydantic import BaseModel


class UserRecord(BaseModel):
    username: str
    name: str
    email: str | None = None
    org: str | None = None


class SimilarMatch(BaseModel):
    name: str
    email: str
    org: str | None = None
    score: float


class LookupResponse(BaseModel):
    exact_match: UserRecord | None = None
    similar_records: list[SimilarMatch] | None = None
    message: str
