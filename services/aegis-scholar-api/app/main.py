"""
Aegis Scholar API - Main FastAPI Application

This is the primary interface between external entities and the Aegis Scholar system.
The system is designed to be read-only for users.
"""
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import FileResponse
from typing import Optional
import logging
from pathlib import Path

from app.config import settings
from app.schemas import (
    AuthorSearchResponse,
    OrgSearchResponse,
    TopicSearchResponse,
    WorkSearchResponse,
    Author,
    Organization,
    Topic,
    Work,
)

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
)

# Mount static files for favicon
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.api_title,
        "version": settings.api_version,
        "description": settings.api_description,
        "endpoints": {
            "search_authors": "/search/authors",
            "search_alias": "/search",
            "search_orgs": "/search/orgs",
            "search_topics": "/search/topics",
            "search_works": "/search/works",
        }
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "aegis-scholar-api"}


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve custom favicon."""
    favicon_path = Path(__file__).parent / "static" / "favicon.svg"
    return FileResponse(favicon_path, media_type="image/svg+xml")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Custom Swagger UI with custom favicon."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_favicon_url="/favicon.ico"
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    """Custom ReDoc with custom favicon."""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_favicon_url="/favicon.ico"
    )


@app.get("/search/authors", response_model=AuthorSearchResponse)
async def search_authors(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit, description="Maximum number of results to return"),
    offset: int = Query(settings.default_offset, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(None, description="Field to sort by (e.g., 'h_index', 'citation_count')"),
    order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order: 'asc' or 'desc'"),
):
    """
    Search for authors by name, affiliation, or research interests.
    
    This endpoint searches the author database and returns matching researchers
    along with their metrics (h-index, citation count, etc.).
    """
    logger.info(f"Searching authors with query: {q}, limit: {limit}, offset: {offset}")
    
    # TODO: Implement actual search logic
    # This is a placeholder that should be replaced with:
    # - Vector search using embedding models
    # - Database queries (e.g., Azure Cosmos DB, PostgreSQL)
    # - Integration with the vector store from steve/search_aegis.py
    
    # Mock response for now
    mock_results = []
    
    return AuthorSearchResponse(
        query=q,
        total=0,
        limit=limit,
        offset=offset,
        results=mock_results
    )


@app.get("/search", response_model=AuthorSearchResponse)
async def search(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit, description="Maximum number of results to return"),
    offset: int = Query(settings.default_offset, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    order: Optional[str] = Query("desc", regex="^(asc|desc)$", description="Sort order: 'asc' or 'desc'"),
):
    """
    Search endpoint (alias for /search/authors).
    
    This is a convenience endpoint that defaults to searching for authors.
    """
    logger.info(f"Search endpoint called (aliased to authors), query: {q}")
    return await search_authors(q=q, limit=limit, offset=offset, sort_by=sort_by, order=order)


@app.get("/search/orgs", response_model=OrgSearchResponse)
async def search_orgs(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit, description="Maximum number of results to return"),
    offset: int = Query(settings.default_offset, ge=0, description="Number of results to skip"),
    org_type: Optional[str] = Query(None, description="Filter by organization type: 'institution', 'funder', 'publisher'"),
    country: Optional[str] = Query(None, description="Filter by country code (e.g., 'US', 'GB')"),
):
    """
    Search for organizations (institutions, funders, publishers).
    
    This endpoint searches the organization database and returns matching
    research institutions, funding agencies, and publishers.
    """
    logger.info(f"Searching organizations with query: {q}, type: {org_type}, country: {country}")
    
    # TODO: Implement actual search logic
    # This should include:
    # - Full-text search on organization names
    # - Filtering by type and country
    # - Ranking by relevance or publication count
    
    mock_results = []
    
    return OrgSearchResponse(
        query=q,
        total=0,
        limit=limit,
        offset=offset,
        results=mock_results
    )


@app.get("/search/topics", response_model=TopicSearchResponse)
async def search_topics(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit, description="Maximum number of results to return"),
    offset: int = Query(settings.default_offset, ge=0, description="Number of results to skip"),
    field: Optional[str] = Query(None, description="Filter by research field"),
    domain: Optional[str] = Query(None, description="Filter by domain (e.g., 'Physical Sciences', 'Social Sciences')"),
):
    """
    Search for research topics and subject areas.
    
    This endpoint searches the topic taxonomy and returns matching
    research topics, fields, and domains.
    """
    logger.info(f"Searching topics with query: {q}, field: {field}, domain: {domain}")
    
    # TODO: Implement actual search logic
    # This should include:
    # - Hierarchical search through domain > field > subfield
    # - Topic similarity search
    # - Related topics suggestions
    
    mock_results = []
    
    return TopicSearchResponse(
        query=q,
        total=0,
        limit=limit,
        offset=offset,
        results=mock_results
    )


@app.get("/search/works", response_model=WorkSearchResponse)
async def search_works(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit, description="Maximum number of results to return"),
    offset: int = Query(settings.default_offset, ge=0, description="Number of results to skip"),
    year_from: Optional[int] = Query(None, description="Filter by publication year (from)"),
    year_to: Optional[int] = Query(None, description="Filter by publication year (to)"),
    min_citations: Optional[int] = Query(None, ge=0, description="Minimum citation count"),
):
    """
    Search for research works, papers, and publications.
    
    This endpoint searches the works database and returns matching
    research papers, articles, and reports. This is the core search
    functionality for finding relevant research.
    """
    logger.info(f"Searching works with query: {q}, years: {year_from}-{year_to}, min_citations: {min_citations}")
    
    # TODO: Implement actual search logic
    # This should integrate with:
    # - Vector search for semantic similarity (from steve/search_aegis.py)
    # - Database queries for metadata filtering
    # - Ranking by relevance, citation count, or date
    # - Abstract and title search
    
    mock_results = []
    
    return WorkSearchResponse(
        query=q,
        total=0,
        limit=limit,
        offset=offset,
        results=mock_results
    )


@app.get("/search/works/{work_id}", response_model=Work)
async def get_work_by_id(work_id: str):
    """
    Get a specific work by ID.
    
    Returns detailed information about a single research work.
    """
    logger.info(f"Fetching work by ID: {work_id}")
    
    # TODO: Implement database lookup
    raise HTTPException(status_code=404, detail=f"Work with ID {work_id} not found")


@app.get("/search/authors/{author_id}", response_model=Author)
async def get_author_by_id(author_id: str):
    """
    Get a specific author by ID.
    
    Returns detailed information about a single author.
    """
    logger.info(f"Fetching author by ID: {author_id}")
    
    # TODO: Implement database lookup
    raise HTTPException(status_code=404, detail=f"Author with ID {author_id} not found")


@app.get("/search/orgs/{org_id}", response_model=Organization)
async def get_org_by_id(org_id: str):
    """
    Get a specific organization by ID.
    
    Returns detailed information about a single organization.
    """
    logger.info(f"Fetching organization by ID: {org_id}")
    
    # TODO: Implement database lookup
    raise HTTPException(status_code=404, detail=f"Organization with ID {org_id} not found")


@app.get("/search/topics/{topic_id}", response_model=Topic)
async def get_topic_by_id(topic_id: str):
    """
    Get a specific topic by ID.
    
    Returns detailed information about a single topic.
    """
    logger.info(f"Fetching topic by ID: {topic_id}")
    
    # TODO: Implement database lookup
    raise HTTPException(status_code=404, detail=f"Topic with ID {topic_id} not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
