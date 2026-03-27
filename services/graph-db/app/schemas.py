
from pydantic import BaseModel, Field


class Source(BaseModel):
    """Metadata source information."""
    source: str
    id: str


class AuthorNode(BaseModel):
    """Graph node representing a researcher."""
    id: str = Field(..., description="author_...")
    name: str
    h_index: int | None = 0
    works_count: int | None = 0
    sources: list[Source] | None = []


class WorkNode(BaseModel):
    """Graph node representing a research publication."""
    id: str = Field(..., description="work_...")
    title: str
    year: int | None = None
    citation_count: int | None = 0
    sources: list[Source] | None = []


class OrgNode(BaseModel):
    """Graph node representing an institution."""
    id: str = Field(..., description="org_...")
    name: str
    type: str  # institution, funder, publisher
    country: str | None = None
    sources: list[Source] | None = []


class TopicNode(BaseModel):
    """Graph node representing a research topic."""
    id: str = Field(..., description="topic_...")
    name: str
    field: str | None = None
    subfield: str | None = None
    domain: str | None = None


class AuthorWorkRel(BaseModel):
    """Relationship model for authoring a work."""
    author_id: str
    work_id: str


class AuthorOrgRel(BaseModel):
    """Relationship model for institutional affiliation."""
    author_id: str
    org_id: str
    role: str = "Researcher"


class WorkTopicRel(BaseModel):
    """Relationship model for topic coverage."""
    work_id: str
    topic_id: str
    score: float = 1.0
