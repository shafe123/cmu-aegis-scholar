"""Pydantic models for API request and response validation."""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any


# Request Models

class VectorSearchRequest(BaseModel):
    """Request model for vector search."""
    query_vector: List[float] = Field(
        ..., 
        description="Query vector for similarity search",
        json_schema_extra={"example": [0.023, -0.145, 0.089] + [0.0] * 381}  # 384-dim vector
    )
    collection_name: Optional[str] = Field(
        None, 
        description="Collection to search in",
        json_schema_extra={"example": "aegis_vectors"}
    )
    limit: int = Field(
        10, 
        ge=1, 
        le=100, 
        description="Maximum number of results to return per page",
        json_schema_extra={"example": 10}
    )
    offset: int = Field(
        0, 
        ge=0, 
        description="Number of results to skip for pagination",
        json_schema_extra={"example": 0}
    )
    output_fields: Optional[List[str]] = Field(
        None, 
        description="Fields to include in results",
        json_schema_extra={"example": ["author_id", "author_name", "num_abstracts"]}
    )
    filter_expr: Optional[str] = Field(
        None, 
        description="Filter expression for search",
        json_schema_extra={"example": "num_abstracts > 10"}
    )


class TextSearchRequest(BaseModel):
    """Request model for text-based search."""
    query_text: str = Field(
        ..., 
        min_length=1, 
        description="Query text to search for",
        json_schema_extra={"example": "adversarial machine learning network security"}
    )
    model_name: Optional[str] = Field(
        None,
        description="Embedding model to use for encoding the query (uses default if not specified)",
        json_schema_extra={"example": "sentence-transformers/all-MiniLM-L6-v2"}
    )
    collection_name: Optional[str] = Field(
        None, 
        description="Collection to search in",
        json_schema_extra={"example": "aegis_vectors"}
    )
    limit: int = Field(
        10, 
        ge=1, 
        le=100, 
        description="Maximum number of results to return per page",
        json_schema_extra={"example": 5}
    )
    offset: int = Field(
        0, 
        ge=0, 
        description="Number of results to skip for pagination",
        json_schema_extra={"example": 0}
    )
    output_fields: Optional[List[str]] = Field(
        None, 
        description="Fields to include in results",
        json_schema_extra={"example": ["author_id", "author_name", "num_abstracts"]}
    )
    filter_expr: Optional[str] = Field(
        None, 
        description="Filter expression for search",
        json_schema_extra={"example": "num_abstracts >= 5"}
    )


class CreateAuthorEmbeddingRequest(BaseModel):
    """Request model for creating or updating author embedding from abstracts."""
    author_id: str = Field(
        ..., 
        description="Unique identifier for the author",
        json_schema_extra={"example": "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a"}
    )
    author_name: str = Field(
        ..., 
        description="Name of the author",
        json_schema_extra={"example": "Dr. Sarah Chen"}
    )
    abstracts: List[str] = Field(
        ..., 
        min_length=1, 
        description="List of paper abstracts by the author",
        json_schema_extra={"example": [
            "This paper presents a comprehensive study of adversarial attacks against machine learning-based network security systems. We demonstrate novel attack vectors and propose robust defense mechanisms.",
            "We explore the application of deep neural networks for real-time intrusion detection in enterprise networks. Our models achieve 98.7% accuracy with low false positive rates."
        ]}
    )
    model_name: Optional[str] = Field(
        None,
        description="Embedding model to use for encoding abstracts (uses default if not specified)",
        json_schema_extra={"example": "sentence-transformers/all-MiniLM-L6-v2"}
    )
    collection_name: Optional[str] = Field(
        None, 
        description="Collection to store the embedding in",
        json_schema_extra={"example": "aegis_vectors"}
    )
    citation_count: Optional[int] = Field(
        None,
        description="Author's citation count",
        json_schema_extra={"example": 8924}
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional metadata for the author",
        json_schema_extra={"example": {"h_index": 42, "works_count": 156}}
    )


class CreateAuthorVectorRequest(BaseModel):
    """Request model for creating or updating author with pre-computed vector."""
    author_id: str = Field(
        ..., 
        description="Unique identifier for the author",
        json_schema_extra={"example": "author_e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b"}
    )
    author_name: str = Field(
        ..., 
        description="Name of the author",
        json_schema_extra={"example": "Dr. Michael Rodriguez"}
    )
    embedding: List[float] = Field(
        ..., 
        description="Pre-computed embedding vector for the author",
        json_schema_extra={"example": [0.025, -0.134, 0.078] + [0.0] * 381}  # 384-dim vector
    )
    model_name: Optional[str] = Field(
        None,
        description="Model name that was used to generate the embedding (for dimension validation)",
        json_schema_extra={"example": "sentence-transformers/all-MiniLM-L6-v2"}
    )
    num_abstracts: Optional[int] = Field(
        None, 
        description="Number of abstracts used to compute the embedding",
        json_schema_extra={"example": 132}
    )
    collection_name: Optional[str] = Field(
        None, 
        description="Collection to store the embedding in",
        json_schema_extra={"example": "aegis_vectors"}
    )
    citation_count: Optional[int] = Field(
        None,
        description="Author's citation count",
        json_schema_extra={"example": 7234}
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, 
        description="Additional metadata for the author",
        json_schema_extra={"example": {"h_index": 38, "works_count": 132}}
    )


# Response Models

class VectorSearchResult(BaseModel):
    """Single search result with flattened entity fields."""
    distance: float = Field(
        ...,
        description="Distance/similarity score from query",
        json_schema_extra={"example": 0.4523}
    )
    author_id: str = Field(
        ...,
        description="Unique identifier for the author",
        json_schema_extra={"example": "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a"}
    )
    author_name: str = Field(
        ...,
        description="Name of the author",
        json_schema_extra={"example": "Dr. Sarah Chen"}
    )
    num_abstracts: int = Field(
        ...,
        description="Number of abstracts used for this embedding",
        json_schema_extra={"example": 124}
    )
    citation_count: Optional[int] = Field(
        None,
        description="Author's citation count",
        json_schema_extra={"example": 8924}
    )
    
    class Config:
        extra = "allow"  # Allow additional fields from output_fields


class PaginationMetadata(BaseModel):
    """Pagination metadata."""
    offset: int = Field(
        ...,
        json_schema_extra={"example": 0}
    )
    limit: int = Field(
        ...,
        json_schema_extra={"example": 10}
    )
    returned: int = Field(
        ...,
        json_schema_extra={"example": 5}
    )
    has_more: bool = Field(
        ...,
        json_schema_extra={"example": True}
    )


class VectorSearchResponse(BaseModel):
    """Response model for vector search."""
    results: List[VectorSearchResult] = Field(
        ...,
        json_schema_extra={"example": [
            {
                "distance": 0.4523,
                "author_id": "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a",
                "author_name": "Dr. Sarah Chen",
                "num_abstracts": 124,
                "citation_count": 8924
            },
            {
                "distance": 0.5891,
                "author_id": "author_e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b",
                "author_name": "Dr. Michael Rodriguez",
                "num_abstracts": 98,
                "citation_count": 6543
            }
        ]}
    )
    collection_name: str = Field(
        ...,
        json_schema_extra={"example": "aegis_vectors"}
    )
    search_time_ms: float = Field(
        ...,
        json_schema_extra={"example": 45.23}
    )
    pagination: PaginationMetadata = Field(
        ...,
        json_schema_extra={"example": {
            "offset": 0,
            "limit": 10,
            "returned": 5,
            "has_more": True
        }}
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(
        ...,
        json_schema_extra={"example": "healthy"}
    )
    milvus_connected: bool = Field(
        ...,
        json_schema_extra={"example": True}
    )
    collections: List[str] = Field(
        ...,
        json_schema_extra={"example": ["aegis_vectors", "test_collection"]}
    )


class CollectionInfo(BaseModel):
    """Collection information."""
    name: str = Field(
        ...,
        json_schema_extra={"example": "aegis_vectors"}
    )
    num_entities: int = Field(
        ...,
        json_schema_extra={"example": 15427}
    )
    description: Optional[str] = Field(
        None,
        json_schema_extra={"example": "Author embeddings from averaged paper abstracts"}
    )


class ModelInfo(BaseModel):
    """Information about an available embedding model."""
    name: str = Field(
        ...,
        json_schema_extra={"example": "sentence-transformers/all-MiniLM-L6-v2"}
    )
    dimension: Optional[int] = Field(
        None,
        json_schema_extra={"example": 384}
    )
    description: str = Field(
        ...,
        json_schema_extra={"example": "Fast and efficient sentence embeddings (384 dimensions)"}
    )
    loaded: bool = Field(
        ...,
        json_schema_extra={"example": True}
    )


class ModelsResponse(BaseModel):
    """Response model for listing available models."""
    models: List[ModelInfo] = Field(
        ...,
        json_schema_extra={"example": [
            {
                "name": "sentence-transformers/all-MiniLM-L6-v2",
                "dimension": 384,
                "description": "Fast and efficient sentence embeddings (384 dimensions)",
                "loaded": True
            },
            {
                "name": "cointegrated/rubert-tiny2",
                "dimension": None,
                "description": "Tiny Russian BERT model for multilingual support",
                "loaded": False
            }
        ]}
    )
    default_model: str = Field(
        ...,
        json_schema_extra={"example": "sentence-transformers/all-MiniLM-L6-v2"}
    )


class CreateAuthorEmbeddingResponse(BaseModel):
    """Response model for author embedding creation."""
    author_id: str = Field(
        ...,
        json_schema_extra={"example": "author_d4e5f6a7-b8c9-4d0e-1f2a-3b4c5d6e7f8a"}
    )
    author_name: str = Field(
        ...,
        json_schema_extra={"example": "Dr. Sarah Chen"}
    )
    embedding_dim: int = Field(
        ...,
        json_schema_extra={"example": 384}
    )
    num_abstracts_processed: int = Field(
        ...,
        json_schema_extra={"example": 2}
    )
    collection_name: str = Field(
        ...,
        json_schema_extra={"example": "aegis_vectors"}
    )
    success: bool = Field(
        ...,
        json_schema_extra={"example": True}
    )
    message: str = Field(
        ...,
        json_schema_extra={"example": "Author embedding created and stored successfully"}
    )


class CreateAuthorVectorResponse(BaseModel):
    """Response model for author vector upload."""
    author_id: str = Field(
        ...,
        json_schema_extra={"example": "author_e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b"}
    )
    author_name: str = Field(
        ...,
        json_schema_extra={"example": "Dr. Michael Rodriguez"}
    )
    embedding_dim: int = Field(
        ...,
        json_schema_extra={"example": 384}
    )
    collection_name: str = Field(
        ...,
        json_schema_extra={"example": "aegis_vectors"}
    )
    success: bool = Field(
        ...,
        json_schema_extra={"example": True}
    )
    message: str = Field(
        ...,
        json_schema_extra={"example": "Author vector created and stored successfully"}
    )
