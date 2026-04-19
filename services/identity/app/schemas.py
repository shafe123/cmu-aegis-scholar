"""Pydantic schemas used by the identity service API."""

from pydantic import BaseModel


class UserRecord(BaseModel):
    """A single exact identity record returned from LDAP."""

    username: str
    name: str
    email: str | None = None
    org: str | None = None


class SimilarMatch(BaseModel):
    """A fuzzy-match suggestion returned for a lookup query."""

    name: str
    email: str
    org: str | None = None
    score: float


class LookupResponse(BaseModel):
    """Response payload for name lookups in the identity directory."""

    exact_match: UserRecord | None = None
    similar_records: list[SimilarMatch] | None = None
    message: str
