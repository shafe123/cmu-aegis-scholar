from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class Source(BaseModel):
    source: str
    id: str

# Node Schemas
class AuthorNode(BaseModel):
    id: str = Field(..., description="author_...")
    name: str
    h_index: Optional[int] = 0
    works_count: Optional[int] = 0
    sources: Optional[List[Source]] = []

class WorkNode(BaseModel):
    id: str = Field(..., description="work_...")
    title: str
    year: Optional[int] = None
    citation_count: Optional[int] = 0
    sources: Optional[List[Source]] = []

class OrgNode(BaseModel):
    id: str = Field(..., description="org_...")
    name: str
    type: str  # institution, funder, publisher
    country: Optional[str] = None
    sources: Optional[List[Source]] = []

class TopicNode(BaseModel):
    id: str = Field(..., description="topic_...")
    name: str
    field: Optional[str] = None
    subfield: Optional[str] = None
    domain: Optional[str] = None

# Relationship Schemas (For Bulk Loading)
class AuthorWorkRel(BaseModel):
    author_id: str
    work_id: str

class AuthorOrgRel(BaseModel):
    author_id: str
    org_id: str
    role: str = "Researcher"

class WorkTopicRel(BaseModel):
    work_id: str
    topic_id: str
    score: float = 1.0