"""Pydantic models for Graph DB API request and response validation."""
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field


class Source(BaseModel):
    """Metadata source information."""
    source: str = Field(..., examples=["dtic"])
    id: str = Field(..., examples=["ADA123456"])


# --- Ingestion Models ---

class AuthorNode(BaseModel):
    """Graph node representing a researcher."""
    id: str = Field(..., description="author_...", examples=["author_cbaacc8e-3d91-5bb6-9c19-f82e83a39150"])
    name: str = Field(..., examples=["Dr. Jane Smith"])
    h_index: Optional[int] = Field(0, examples=[24])
    works_count: Optional[int] = Field(0, examples=[156])
    sources: Optional[List[Source]] = []


class WorkNode(BaseModel):
    """Graph node representing a research publication."""
    id: str = Field(..., description="work_...", examples=["work_9a9268be-c50b-71a6-54dd-fa9ad03e82a1"])
    title: str = Field(..., examples=["Adversarial Machine Learning in Network Security"])
    name: Optional[str] = None
    type: Optional[str] = None
    country: Optional[str] = None
    year: Optional[int] = Field(None, examples=[2024])
    citation_count: Optional[int] = Field(0, examples=[42])
    sources: Optional[List[Source]] = []
    abstract: Optional[str] = Field(None, examples=["This paper discusses..."])
    publication_date: Optional[str] = Field(None, examples=["2024-05-12"])


class OrgNode(BaseModel):
    """Graph node representing an institution."""
    id: str = Field(..., description="org_...", examples=["org_o555555"])
    name: str = Field(..., examples=["Carnegie Mellon University"])
    type: str = Field(..., examples=["institution"])
    country: Optional[str] = Field(None, examples=["US"])
    sources: Optional[List[Source]] = []


class TopicNode(BaseModel):
    """Graph node representing a research topic."""
    id: str = Field(..., description="topic_...", examples=["topic_ai"])
    name: str = Field(..., examples=["Artificial Intelligence"])
    field: Optional[str] = None
    subfield: Optional[str] = None
    domain: Optional[str] = None


# --- Relationship Models ---

class AuthorWorkRel(BaseModel):
    author_id: str = Field(..., examples=["author_123"])
    work_id: str = Field(..., examples=["work_456"])


class AuthorOrgRel(BaseModel):
    author_id: str = Field(..., examples=["author_123"])
    org_id: str = Field(..., examples=["org_789"])
    role: str = Field("Researcher", examples=["Principal Investigator"])


class WorkTopicRel(BaseModel):
    work_id: str = Field(..., examples=["work_456"])
    topic_id: str = Field(..., examples=["topic_ai"])
    score: float = Field(1.0, examples=[0.95])


# --- NEW: Response Models for Documentation ---

class StatsResponse(BaseModel):
    author_count: int = Field(..., examples=[17245])


class CollaboratorResponse(BaseModel):
    id: str = Field(..., examples=["author_e5f6a7b8"])
    name: str = Field(..., examples=["Dr. Michael Rodriguez"])


class GraphNodeViz(BaseModel):
    """Properties of a node intended for frontend visualization."""
    id: str = Field(..., examples=["author_123"])
    label: str = Field(..., examples=["Dr. Jane Smith"])
    group: str = Field(..., examples=["author"])
    color: str = Field(..., examples=["#ff6b6b"])
    email: Optional[str] = Field(None, examples=["jane.smith@dod.mil"])
    works_count: Optional[int] = Field(None, examples=[42])
    year: Optional[str] = Field(None, examples=["2024"])
    citations: Optional[int] = Field(None, examples=[10])
    abstract: Optional[str] = None


class GraphEdgeViz(BaseModel):
    """Properties of an edge linking two nodes."""
    source: str = Field(..., alias="from", examples=["author_123"])
    to: str = Field(..., examples=["work_456"])
    label: str = Field(..., examples=["AUTHORED"])

    class Config:
        populate_by_name = True


class VizResponse(BaseModel):
    """The full payload required by the frontend Network Explorer."""
    nodes: List[GraphNodeViz]
    edges: List[GraphEdgeViz]


class StatusResponse(BaseModel):
    status: str = Field(..., examples=["success"])
    id: Optional[str] = None