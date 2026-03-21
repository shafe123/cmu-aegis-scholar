"""Pydantic models for API request and response validation."""
from typing import List, Optional, Literal
from datetime import datetime, date
from pydantic import BaseModel, Field


class Source(BaseModel):
    """Source identifier from external databases."""
    source: Literal["ror", "openalex", "crossref", "dtic", "orcid", "other"]
    id: str


class Organization(BaseModel):
    """Research institutions, funders, and publishers."""
    id: str = Field(pattern=r"^org_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name: str
    country: Optional[str] = None
    type: Optional[Literal["institution", "funder", "publisher", "other"]] = None
    sources: Optional[List[Source]] = None
    last_updated: Optional[datetime] = None


class Author(BaseModel):
    """Individual researchers and authors."""
    id: str = Field(pattern=r"^author_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name: str
    org_ids: Optional[List[str]] = None
    h_index: Optional[int] = Field(default=None, ge=0)
    citation_count: Optional[int] = Field(default=None, ge=0)
    works_count: Optional[int] = Field(default=None, ge=0)
    sources: Optional[List[Source]] = None
    last_updated: Optional[datetime] = None


class Topic(BaseModel):
    """Research topics and subject areas."""
    id: str = Field(pattern=r"^topic_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    name: str
    field: Optional[str] = None
    subfield: Optional[str] = None
    domain: Optional[str] = None
    sources: Optional[List[Source]] = None
    last_updated: Optional[datetime] = None


class WorkAuthor(BaseModel):
    """Author information within a work."""
    author_id: str
    org_id: Optional[str] = None


class WorkOrg(BaseModel):
    """Organization information within a work."""
    org_id: str
    role: Literal["funder", "publisher", "affiliation", "other"]


class WorkTopic(BaseModel):
    """Topic information within a work."""
    topic_id: str
    score: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class Work(BaseModel):
    """Published research works, papers, and reports."""
    id: str = Field(pattern=r"^work_[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
    title: str
    abstract: Optional[str] = None
    publication_date: Optional[date] = None
    citation_count: Optional[int] = Field(default=None, ge=0)
    authors: Optional[List[WorkAuthor]] = None
    orgs: Optional[List[WorkOrg]] = None
    topics: Optional[List[WorkTopic]] = None
    sources: Optional[List[Source]] = None
    venue: Optional[str] = None
    doi: Optional[str] = None
    url: Optional[str] = None
    last_updated: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Search-result wrappers
# ---------------------------------------------------------------------------
# These extend the base entity models with a relevance_score so that search
# results carry ranking information without altering the core data models.

class AuthorSearchResult(Author):
    """An Author result enriched with a search relevance score."""
    relevance_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        description=(
            "Semantic similarity score derived from vector distance. "
            "Higher is more relevant. Range 0-1."
        ),
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
    results: List[dict]


class AuthorSearchResponse(SearchResponse):
    """Search response for authors."""
    results: List[AuthorSearchResult]


class OrgSearchResponse(SearchResponse):
    """Search response for organizations."""
    results: List[Organization]


class TopicSearchResponse(SearchResponse):
    """Search response for topics."""
    results: List[Topic]


class WorkSearchResponse(SearchResponse):
    """Search response for works."""
    results: List[Work]
