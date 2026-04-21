"""Pydantic models for Graph DB API request and response validation."""

from pydantic import BaseModel, ConfigDict, Field


class Source(BaseModel):
    """Metadata source information."""

    source: str = Field(..., examples=["dtic"])
    id: str = Field(..., examples=["ADA123456"])


# --- Ingestion Models ---


class AuthorNode(BaseModel):
    """Graph node representing a researcher."""

    id: str = Field(..., description="author_...", examples=["author_cbaacc8e-3d91-5bb6-9c19-f82e83a39150"])
    name: str = Field(..., examples=["Dr. Jane Smith"])
    h_index: int | None = Field(0, examples=[24])
    works_count: int | None = Field(0, examples=[156])
    sources: list[Source] | None = []


class WorkNode(BaseModel):
    """Graph node representing a research publication."""

    id: str = Field(..., description="work_...", examples=["work_9a9268be-c50b-71a6-54dd-fa9ad03e82a1"])
    title: str = Field(..., examples=["Adversarial Machine Learning in Network Security"])
    name: str | None = None
    type: str | None = None
    country: str | None = None
    year: int | None = Field(None, examples=[2024])
    citation_count: int | None = Field(0, examples=[42])
    sources: list[Source] | None = []
    abstract: str | None = Field(None, examples=["This paper discusses..."])
    publication_date: str | None = Field(None, examples=["2024-05-12"])


class OrgNode(BaseModel):
    """Graph node representing an institution."""

    id: str = Field(..., description="org_...", examples=["org_o555555"])
    name: str = Field(..., examples=["Carnegie Mellon University"])
    type: str = Field(..., examples=["institution"])
    country: str | None = Field(None, examples=["US"])
    sources: list[Source] | None = []


class TopicNode(BaseModel):
    """Graph node representing a research topic."""

    id: str = Field(..., description="topic_...", examples=["topic_ai"])
    name: str = Field(..., examples=["Artificial Intelligence"])
    field: str | None = None
    subfield: str | None = None
    domain: str | None = None


# --- Relationship Models ---


class AuthorWorkRel(BaseModel):
    """Link between Author and Work."""

    author_id: str = Field(..., examples=["author_123"])
    work_id: str = Field(..., examples=["work_456"])


class AuthorOrgRel(BaseModel):
    """Link between Author and Org."""

    author_id: str = Field(..., examples=["author_123"])
    org_id: str = Field(..., examples=["org_789"])
    role: str = Field("Researcher", examples=["Principal Investigator"])


class WorkTopicRel(BaseModel):
    """Link between Work and Topic."""

    work_id: str = Field(..., examples=["work_456"])
    topic_id: str = Field(..., examples=["topic_ai"])
    score: float = Field(1.0, examples=[0.95])


# --- NEW: Response Models for Documentation ---


class StatsResponse(BaseModel):
    """Response model for database population counts."""

    author_count: int = Field(..., examples=[17245])


class CollaboratorResponse(BaseModel):
    """Response model for research network analysis."""

    id: str = Field(..., examples=["author_e5f6a7b8"])
    name: str = Field(..., examples=["Dr. Michael Rodriguez"])


class GraphNodeViz(BaseModel):
    """Properties of a node intended for frontend visualization."""

    id: str = Field(..., examples=["author_123"])
    label: str = Field(..., examples=["Dr. Jane Smith"])
    group: str = Field(..., examples=["author"])
    color: str = Field(..., examples=["#ff6b6b"])
    email: str | None = Field(None, examples=["jane.smith@dod.mil"])
    works_count: int | None = Field(None, examples=[42])
    year: str | None = Field(None, examples=["2024"])
    citations: int | None = Field(None, examples=[10])
    full_title: str | None = None  # Added for validation
    abstract: str | None = None


class GraphEdgeViz(BaseModel):
    """Properties of an edge linking two nodes."""

    model_config = ConfigDict(populate_by_name=True)

    source: str = Field(..., alias="from", examples=["author_123"])
    to: str = Field(..., examples=["work_456"])
    label: str = Field(..., examples=["AUTHORED"])


class VizResponse(BaseModel):
    """The full payload required by the frontend Network Explorer."""

    nodes: list[GraphNodeViz]
    edges: list[GraphEdgeViz]


class StatusResponse(BaseModel):
    """Standard success/failure response."""

    status: str = Field(..., examples=["success"])
    id: str | None = None
