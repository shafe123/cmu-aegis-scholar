"""Pydantic models for API request and response validation."""
# pylint: disable=too-few-public-methods

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Source(BaseModel):
    """Source identifier from external databases."""

    source: Literal["ror", "openalex", "crossref", "dtic", "orcid", "other"]
    id: str


class Organization(BaseModel):
    """Research institutions, funders, and publishers."""

    id: str = Field(pattern=r"^org_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name: str
    country: str | None = None
    type: Literal["institution", "funder", "publisher", "other"] | None = None
    sources: list[Source] | None = None
    last_updated: datetime | None = None


class Author(BaseModel):
    """Individual researchers and authors."""

    id: str = Field(pattern=r"^author_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name: str
    org_ids: list[str] | None = None
    h_index: int | None = Field(default=None, ge=0)
    citation_count: int | None = Field(default=None, ge=0)
    works_count: int | None = Field(default=None, ge=0)
    sources: list[Source] | None = None
    last_updated: datetime | None = None


class Topic(BaseModel):
    """Research topics and subject areas."""

    id: str = Field(pattern=r"^topic_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name: str
    field: str | None = None
    subfield: str | None = None
    domain: str | None = None
    sources: list[Source] | None = None
    last_updated: datetime | None = None


class WorkAuthor(BaseModel):
    """Author information within a work."""

    author_id: str
    org_id: str | None = None


class WorkOrg(BaseModel):
    """Organization information within a work."""

    org_id: str
    role: Literal["funder", "publisher", "affiliation", "other"]


class WorkTopic(BaseModel):
    """Topic information within a work."""

    topic_id: str
    score: float | None = Field(default=None, ge=0.0, le=1.0)


class Work(BaseModel):
    """Published research works, papers, and reports."""

    id: str = Field(pattern=r"^work_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    title: str
    abstract: str | None = None
    publication_date: date | None = None
    citation_count: int | None = Field(default=None, ge=0)
    authors: list[WorkAuthor] | None = None
    orgs: list[WorkOrg] | None = None
    topics: list[WorkTopic] | None = None
    sources: list[Source] | None = None
    venue: str | None = None
    doi: str | None = None
    url: str | None = None
    last_updated: datetime | None = None


# ---------------------------------------------------------------------------
# Search-result wrappers
# ---------------------------------------------------------------------------
# These extend the base entity models with a relevance_score so that search
# results carry ranking information without altering the core data models.


class AuthorSearchResult(Author):
    """An Author result enriched with a search relevance score."""

    relevance_score: float | None = Field(
        default=None,
        ge=0.0,
        description=("Semantic similarity score derived from vector distance. Higher is more relevant. Range 0-1."),
    )


# ---------------------------------------------------------------------------
# Response models for search endpoints
# ---------------------------------------------------------------------------


class SearchResponse(BaseModel):
    """Generic search response with results and metadata."""

    query: str
    total: int
    limit: int
    offset: int
    results: list[Any]


class AuthorSearchResponse(SearchResponse):
    """Search response for authors."""

    results: list[AuthorSearchResult]


class OrgSearchResponse(SearchResponse):
    """Search response for organizations."""

    results: list[Organization]


class TopicSearchResponse(SearchResponse):
    """Search response for topics."""

    results: list[Topic]


class WorkSearchResponse(SearchResponse):
    """Search response for works."""

    results: list[Work]


# ---------------------------------------------------------------------------
# Response models for Identity /lookup Endpoint
# ---------------------------------------------------------------------------


class UserRecord(BaseModel):
    """A single exact identity record returned from LDAP."""

    username: str
    name: str
    email: str | None = None
    org: str | None = None


class SimilarMatch(BaseModel):
    """A fuzzy-match suggestion returned for a lookup query."""

    name: str
    email: str | None = None
    org: str | None = None
    score: float


class LookupResponse(BaseModel):
    """Response payload for name lookups in the identity directory."""

    exact_match: UserRecord | None = None
    similar_records: list[SimilarMatch] | None = None
    message: str
