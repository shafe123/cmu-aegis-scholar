"""
Aegis Scholar API - Main FastAPI Application

This is the primary interface between external entities and the Aegis Scholar system.
The system is designed to be read-only for users.

Architecture
------------
    User  ──GET /search/authors?q=...──▶  THIS API  ──POST /search/text──▶  Vector DB (port 8002)
                                              │                                    │
                                              │◀──── ranked author results ────────┘
                                              │
                                              ▼
                                        Format into AuthorSearchResponse and return

The vector DB stores one embedding per author (the average of all their
paper-abstract embeddings).  When a user searches, the vector DB converts
the query text into a 384-dim vector and finds the nearest authors in
Milvus.  This API reformats those results into the Aegis Scholar schema.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.responses import FileResponse
from typing import Optional
import logging
from pathlib import Path

import httpx

from app.config import settings
from app.schemas import (
    AuthorSearchResponse,
    AuthorSearchResult,
    OrgSearchResponse,
    TopicSearchResponse,
    WorkSearchResponse,
    Author,
    Organization,
    Topic,
    Work,
)
from app.services import vector_db

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start/stop long-lived resources (HTTP client pool, future DB pools)."""
    # ── Startup ──
    await vector_db.init_client()
    logger.info("Aegis Scholar API started")
    yield
    # ── Shutdown ──
    await vector_db.close_client()
    logger.info("Aegis Scholar API stopped")


# ---------------------------------------------------------------------------
# Create FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title=settings.api_title,
    description=settings.api_description,
    version=settings.api_version,
    lifespan=lifespan,
    docs_url=None,
    redoc_url=None,
)

# Mount static files for favicon
static_path = Path(__file__).parent / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allow_methods,
    allow_headers=settings.cors_allow_headers,
)


# ---------------------------------------------------------------------------
# Helper: convert vector-DB results → AuthorSearchResult list
# ---------------------------------------------------------------------------

def _distance_to_relevance(distance: float) -> float:
    """
    Convert an L2 distance into a 0-1 relevance score.

    The vector DB uses L2 (Euclidean) distance where 0 = identical.
    We map this to a score where 1.0 = perfect match using:
        relevance = 1 / (1 + distance)
    """
    return round(1.0 / (1.0 + distance), 4)


def _map_vector_results(raw_results: list[dict]) -> list[AuthorSearchResult]:
    """
    Transform the flat dicts returned by the vector DB into
    AuthorSearchResult Pydantic models.

    Vector DB returns:
        { "distance": 0.45, "author_id": "author_abc...", "author_name": "...",
          "num_abstracts": 124, "citation_count": 8924 }

    We map to:
        AuthorSearchResult(id=..., name=..., works_count=..., citation_count=...,
                           relevance_score=...)
    """
    results: list[AuthorSearchResult] = []
    for hit in raw_results:
        try:
            results.append(
                AuthorSearchResult(
                    id=hit["author_id"],
                    name=hit["author_name"],
                    works_count=hit.get("num_abstracts"),
                    citation_count=hit.get("citation_count"),
                    relevance_score=_distance_to_relevance(hit.get("distance", 0)),
                    # Fields not yet available from the vector DB:
                    #   org_ids, h_index, sources, last_updated
                    # These will be populated once the graph DB or a
                    # metadata store is integrated.
                )
            )
        except Exception as e:
            logger.warning(f"Skipping malformed vector result: {e}  raw={hit}")
    return results


# ---------------------------------------------------------------------------
# Helper: re-sort results if the user requested a non-default sort
# ---------------------------------------------------------------------------

_SORTABLE_AUTHOR_FIELDS = {"relevance_score", "citation_count", "works_count"}


def _sort_author_results(
    results: list[AuthorSearchResult],
    sort_by: Optional[str],
    order: str,
) -> list[AuthorSearchResult]:
    """
    Optionally re-sort author results.

    By default the vector DB returns results sorted by distance (most
    relevant first).  If the caller asks for a different sort_by field
    (e.g. citation_count), we re-sort here.
    """
    if not sort_by or sort_by not in _SORTABLE_AUTHOR_FIELDS:
        return results  # keep default relevance order

    reverse = order == "desc"
    return sorted(
        results,
        key=lambda r: getattr(r, sort_by) or 0,
        reverse=reverse,
    )


# ---------------------------------------------------------------------------
# System endpoints
# ---------------------------------------------------------------------------

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
        },
    }


@app.get("/health")
async def health_check():
    """Health check — also pings the vector DB to report downstream status."""
    vdb_status = "unknown"
    try:
        vdb_health = await vector_db.health()
        vdb_status = vdb_health.get("status", "unknown")
    except Exception as e:
        vdb_status = f"unreachable: {e}"

    return {
        "status": "healthy",
        "service": "aegis-scholar-api",
        "dependencies": {
            "vector_db": vdb_status,
        },
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon():
    """Serve custom favicon."""
    favicon_path = Path(__file__).parent / "static" / "favicon.svg"
    if favicon_path.exists():
        return FileResponse(favicon_path, media_type="image/svg+xml")
    raise HTTPException(status_code=404, detail="Favicon not found")


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_favicon_url="/favicon.ico",
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_favicon_url="/favicon.ico",
    )


# ---------------------------------------------------------------------------
# SEARCH ENDPOINTS — Author (fully wired to vector DB)
# ---------------------------------------------------------------------------

@app.get("/search/authors", response_model=AuthorSearchResponse)
async def search_authors(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(
        settings.default_limit, ge=1, le=settings.max_limit,
        description="Maximum number of results to return",
    ),
    offset: int = Query(
        settings.default_offset, ge=0,
        description="Number of results to skip",
    ),
    sort_by: Optional[str] = Query(
        None,
        description=(
            "Field to sort by. Supported: 'relevance_score', "
            "'citation_count', 'works_count'. "
            "Default: relevance_score (most relevant first)."
        ),
    ),
    order: Optional[str] = Query(
        "desc", pattern="^(asc|desc)$",
        description="Sort order: 'asc' or 'desc'",
    ),
):
    """
    Search for authors by name, affiliation, or research interests.

    The query text is converted into a semantic embedding and compared
    against author embeddings (averaged paper abstracts) in the vector
    database.  Results are ranked by relevance unless a different
    sort_by field is specified.
    """
    logger.info(f"GET /search/authors  q={q!r}  limit={limit}  offset={offset}")

    # When re-sorting by a non-relevance field we need to pull a bigger
    # window from the vector DB so the re-sort is meaningful.  We fetch
    # up to max_limit results, re-sort, then slice for the requested page.
    need_resort = sort_by and sort_by in _SORTABLE_AUTHOR_FIELDS and sort_by != "relevance_score"
    fetch_limit = settings.max_limit if need_resort else limit
    fetch_offset = 0 if need_resort else offset

    try:
        raw = await vector_db.search_by_text(
            query_text=q,
            limit=fetch_limit,
            offset=fetch_offset,
            output_fields=["author_id", "author_name", "num_abstracts", "citation_count"],
        )
    except httpx.ConnectError:
        logger.error("Vector DB service is unreachable")
        raise HTTPException(
            status_code=503,
            detail="Search service temporarily unavailable. Please try again later.",
        )
    except httpx.HTTPStatusError as e:
        logger.error(f"Vector DB returned error: {e.response.status_code} {e.response.text}")
        raise HTTPException(
            status_code=502,
            detail="Upstream search service returned an error.",
        )

    # Map and optionally re-sort
    authors = _map_vector_results(raw.get("results", []))
    authors = _sort_author_results(authors, sort_by, order or "desc")

    # Apply local pagination when we fetched a larger window for re-sort
    if need_resort:
        total_available = len(authors)
        authors = authors[offset : offset + limit]
    else:
        pagination = raw.get("pagination", {})
        total_available = pagination.get("returned", len(authors))
        # Vector DB already paginated for us

    return AuthorSearchResponse(
        query=q,
        total=total_available,
        limit=limit,
        offset=offset,
        results=authors,
    )


@app.get("/search", response_model=AuthorSearchResponse)
async def search(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(
        settings.default_limit, ge=1, le=settings.max_limit,
        description="Maximum number of results to return",
    ),
    offset: int = Query(settings.default_offset, ge=0, description="Number of results to skip"),
    sort_by: Optional[str] = Query(None, description="Field to sort by"),
    order: Optional[str] = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
):
    """Convenience alias — delegates to /search/authors."""
    return await search_authors(q=q, limit=limit, offset=offset, sort_by=sort_by, order=order)


# ---------------------------------------------------------------------------
# SEARCH ENDPOINTS — Orgs, Topics, Works  (awaiting graph DB / metadata store)
# ---------------------------------------------------------------------------
# These endpoints are structurally complete but return 501 until a
# backend data source is connected.  The vector DB only stores author
# embeddings, so we cannot yet search for works, topics, or orgs by
# semantic similarity.  Once the graph DB is ready, these will be
# wired in the same pattern as search_authors.

@app.get("/search/orgs", response_model=OrgSearchResponse)
async def search_orgs(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit),
    offset: int = Query(settings.default_offset, ge=0),
    org_type: Optional[str] = Query(None, description="Filter by organization type"),
    country: Optional[str] = Query(None, description="Filter by country code"),
):
    """
    Search for organizations.

    **Status: not yet implemented.**
    This endpoint requires the graph database or a metadata store to be
    connected.  It will return organization results once that integration
    is complete.
    """
    logger.info(f"GET /search/orgs  q={q!r}  (not yet implemented)")
    raise HTTPException(
        status_code=501,
        detail=(
            "Organization search is not yet available. "
            "This endpoint will be enabled once the graph database integration is complete."
        ),
    )


@app.get("/search/topics", response_model=TopicSearchResponse)
async def search_topics(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit),
    offset: int = Query(settings.default_offset, ge=0),
    field: Optional[str] = Query(None, description="Filter by research field"),
    domain: Optional[str] = Query(None, description="Filter by domain"),
):
    """
    Search for research topics and subject areas.

    **Status: not yet implemented.**
    Topic search requires the OpenAlex topic taxonomy to be loaded into
    either the graph database or a metadata store.
    """
    logger.info(f"GET /search/topics  q={q!r}  (not yet implemented)")
    raise HTTPException(
        status_code=501,
        detail=(
            "Topic search is not yet available. "
            "This endpoint will be enabled once the topic taxonomy is loaded."
        ),
    )


@app.get("/search/works", response_model=WorkSearchResponse)
async def search_works(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit),
    offset: int = Query(settings.default_offset, ge=0),
    year_from: Optional[int] = Query(None, description="Filter by publication year (from)"),
    year_to: Optional[int] = Query(None, description="Filter by publication year (to)"),
    min_citations: Optional[int] = Query(None, ge=0, description="Minimum citation count"),
):
    """
    Search for research works, papers, and publications.

    **Status: not yet implemented.**
    Work search requires a metadata store (Cosmos DB / PostgreSQL) or
    the graph database for structured queries over publication records.
    """
    logger.info(f"GET /search/works  q={q!r}  (not yet implemented)")
    raise HTTPException(
        status_code=501,
        detail=(
            "Work search is not yet available. "
            "This endpoint will be enabled once the metadata store integration is complete."
        ),
    )


# ---------------------------------------------------------------------------
# DETAIL ENDPOINTS — single-entity lookups (awaiting metadata store)
# ---------------------------------------------------------------------------

@app.get("/search/works/{work_id}", response_model=Work)
async def get_work_by_id(work_id: str):
    """Get a specific work by ID."""
    logger.info(f"GET /search/works/{work_id}  (not yet implemented)")
    raise HTTPException(
        status_code=501,
        detail="Work detail lookup is not yet available.",
    )


@app.get("/search/authors/{author_id}", response_model=Author)
async def get_author_by_id(author_id: str):
    """Get a specific author by ID."""
    logger.info(f"GET /search/authors/{author_id}  (not yet implemented)")
    raise HTTPException(
        status_code=501,
        detail="Author detail lookup is not yet available.",
    )


@app.get("/search/orgs/{org_id}", response_model=Organization)
async def get_org_by_id(org_id: str):
    """Get a specific organization by ID."""
    logger.info(f"GET /search/orgs/{org_id}  (not yet implemented)")
    raise HTTPException(
        status_code=501,
        detail="Organization detail lookup is not yet available.",
    )


@app.get("/search/topics/{topic_id}", response_model=Topic)
async def get_topic_by_id(topic_id: str):
    """Get a specific topic by ID."""
    logger.info(f"GET /search/topics/{topic_id}  (not yet implemented)")
    raise HTTPException(
        status_code=501,
        detail="Topic detail lookup is not yet available.",
    )


# ---------------------------------------------------------------------------
# Entrypoint for local development
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
