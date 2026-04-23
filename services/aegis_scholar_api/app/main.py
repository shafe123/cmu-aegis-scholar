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
                                              │  (for each author, fetch most recent
                                              │   work year from Graph DB)
                                              │──GET /viz/author-network/{id}──▶  Graph DB (port 8003)
                                              │◀──── work nodes with year ──────────┘
                                              │
                                              ▼
                                        Score with WolframAlpha formula and return
                                        AuthorSearchResponse
"""

import logging
import math
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.schemas import (
    Author,
    AuthorSearchResponse,
    AuthorSearchResult,
    LookupResponse,
    Organization,
    OrgSearchResponse,
    Topic,
    TopicSearchResponse,
    Work,
    WorkSearchResponse,
)
from app.services import vector_db
from app.services.graph_db import graph_client

# Configure logging
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application lifecycle
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app_instance: FastAPI):  # pylint: disable=unused-argument
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
# Helper: map raw vector results to schema and calculate hybrid scores
# ---------------------------------------------------------------------------


def _distance_to_relevance(distance: float) -> float:
    """
    Convert an L2 distance into a 0-1 relevance score.
    relevance = 1 / (1 + distance)
    """
    return round(1.0 / (1.0 + distance), 4)


DEFAULT_RECENCY_DECADES = 2.0  # Midpoint of the [0,4] range; used when recency data is unavailable.


def _calculate_decades_since_most_recent_work(most_recent_work_year: str | int | None) -> float:
    """Return decades in the past from today, capped to WolframAlpha's t-range [0,4]."""
    if most_recent_work_year is None:
        # Use midpoint (DEFAULT_RECENCY_DECADES) of the [0,4] range when recency data is unavailable
        # to avoid either penalizing or favoring missing-recency authors.
        return DEFAULT_RECENCY_DECADES

    years_since = max(0, date.today().year - int(most_recent_work_year))
    return min(years_since / 10.0, 4.0)


def _calculate_author_relevance(x: float, y: int, t: float) -> float:
    """
    WolframAlpha formula:
    z(x, y, t) = 1/3*(1-x) + 1/3*(1/(1 + e^(-0.005*(y-100)))) + 1/3*((-tanh(t-2)+1)/2)

    x: vector similarity score (0-1)
    y: citation count (>=0)
    t: decades since most recent work (0-4)
    """
    x = min(max(x, 0.0), 1.0)
    y = max(y, 0)
    t = min(max(t, 0.0), 4.0)

    citations_term = 1.0 / (1.0 + math.exp(-0.005 * (y - 100)))
    recency_term = (-math.tanh(t - 2.0) + 1.0) / 2.0
    return round(((1.0 - x) + citations_term + recency_term) / 3.0, 4)


async def _map_vector_results(vector_results: list) -> list[AuthorSearchResult]:
    """
    Transform raw vector DB dicts into AuthorSearchResult Pydantic models.
    Uses the WolframAlpha relevance formula combining vector score (x),
    citation count (y), and decades since most recent work (t).

    The most recent work year is fetched from the graph DB via
    /viz/author-network/{author_id} for each author.  If the graph DB is
    unavailable the recency term defaults to the neutral midpoint (t=2.0).
    """
    results: list[AuthorSearchResult] = []
    for res in vector_results:
        try:
            distance = res.get("distance", 1.0)
            citation_count = int(res.get("citation_count", 0) or 0)
            vector_score = _distance_to_relevance(distance)
            author_id = res["author_id"]
            most_recent_work_year = await graph_client.get_most_recent_work_year(author_id)
            decades_since_recent_work = _calculate_decades_since_most_recent_work(most_recent_work_year)
            relevance_score = _calculate_author_relevance(vector_score, citation_count, decades_since_recent_work)
            results.append(
                AuthorSearchResult(
                    id=author_id,
                    name=res.get("author_name", "Unknown"),
                    citation_count=citation_count,
                    works_count=res.get("num_abstracts", 0),
                    relevance_score=relevance_score,
                )
            )
        except Exception as e:  # pylint: disable=broad-exception-caught
            logger.warning("Skipping malformed vector result: %s  raw=%s", e, res)
    return sorted(results, key=lambda r: r.relevance_score or 0, reverse=True)


# ---------------------------------------------------------------------------
# Helper: re-sort results if the user requested a non-default sort
# ---------------------------------------------------------------------------

_SORTABLE_AUTHOR_FIELDS = {"relevance_score", "citation_count", "works_count"}


def _sort_author_results(
    results: list[AuthorSearchResult],
    sort_by: str | None,
    order: str,
) -> list[AuthorSearchResult]:
    """Optionally re-sort author results."""
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
            "identity_lookup": "/identity/lookup",
        },
    }


@app.get("/health")
async def health_check():
    """Health check — also pings the vector DB to report downstream status."""
    vdb_status = "unknown"
    try:
        vdb_health = await vector_db.health()
        vdb_status = vdb_health.get("status", "unknown")
    except Exception as e:  # pylint: disable=broad-exception-caught
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
    """Serve custom Swagger UI html."""
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Swagger UI",
        swagger_favicon_url="/favicon.ico",
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    """Serve custom ReDoc html."""
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
        settings.default_limit,
        ge=1,
        le=settings.max_limit,
        description="Maximum number of results to return",
    ),
    offset: int = Query(
        settings.default_offset,
        ge=0,
        description="Number of results to skip",
    ),
    sort_by: str | None = Query(
        None,
        description=(
            "Field to sort by. Supported: 'relevance_score', "
            "'citation_count', 'works_count'. "
            "Default: relevance_score (most relevant first)."
        ),
    ),
    order: str | None = Query(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order: 'asc' or 'desc'",
    ),
):
    """Search for authors by name, affiliation, or research interests."""
    logger.info("GET /search/authors  q=%r  limit=%d  offset=%d", q, limit, offset)

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
    except httpx.ConnectError as exc:
        logger.error("Vector DB service is unreachable")
        raise HTTPException(
            status_code=503,
            detail="Search service temporarily unavailable. Please try again later.",
        ) from exc
    except httpx.HTTPStatusError as e:
        logger.error("Vector DB returned error: %s %s", e.response.status_code, e.response.text)
        raise HTTPException(
            status_code=502,
            detail="Upstream search service returned an error.",
        ) from e

    # Map and optionally re-sort
    authors = await _map_vector_results(raw.get("results", []))
    authors = _sort_author_results(authors, sort_by, order or "desc")

    if need_resort:
        total_available = len(authors)
        authors = authors[offset : offset + limit]
    else:
        pagination = raw.get("pagination", {})
        total_available = pagination.get("returned", len(authors))

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
        settings.default_limit,
        ge=1,
        le=settings.max_limit,
        description="Maximum number of results to return",
    ),
    offset: int = Query(settings.default_offset, ge=0, description="Number of results to skip"),
    sort_by: str | None = Query(None, description="Field to sort by"),
    order: str | None = Query("desc", pattern="^(asc|desc)$", description="Sort order"),
):
    """Convenience alias — delegates to /search/authors."""
    return await search_authors(q=q, limit=limit, offset=offset, sort_by=sort_by, order=order)


# ---------------------------------------------------------------------------
# SEARCH ENDPOINTS — Orgs, Topics, Works  (awaiting graph DB / metadata store)
# ---------------------------------------------------------------------------


@app.get("/search/orgs", response_model=OrgSearchResponse)
async def search_orgs(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit),
    offset: int = Query(settings.default_offset, ge=0),
    org_type: str | None = Query(None, description="Filter by organization type"),
    country: str | None = Query(None, description="Filter by country code"),
):
    """Search for organizations."""
    # pylint: disable=unused-argument
    logger.info("GET /search/orgs  q=%r  (not yet implemented)", q)
    raise HTTPException(
        status_code=501,
        detail="Organization search is not yet available.",
    )


@app.get("/search/topics", response_model=TopicSearchResponse)
async def search_topics(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit),
    offset: int = Query(settings.default_offset, ge=0),
    field: str | None = Query(None, description="Filter by research field"),
    domain: str | None = Query(None, description="Filter by domain"),
):
    """Search for research topics and subject areas."""
    # pylint: disable=unused-argument
    logger.info("GET /search/topics  q=%r  (not yet implemented)", q)
    raise HTTPException(
        status_code=501,
        detail="Topic search is not yet available.",
    )


@app.get("/search/works", response_model=WorkSearchResponse)
async def search_works(
    q: str = Query(..., description="Search query string"),
    limit: int = Query(settings.default_limit, ge=1, le=settings.max_limit),
    offset: int = Query(settings.default_offset, ge=0),
    year_from: int | None = Query(None, description="Filter by publication year (from)"),
    year_to: int | None = Query(None, description="Filter by publication year (to)"),
    min_citations: int | None = Query(None, ge=0, description="Minimum citation count"),
):
    """Search for research works, papers, and publications."""
    # pylint: disable=unused-argument,too-many-arguments,too-many-positional-arguments
    logger.info("GET /search/works  q=%r  (not yet implemented)", q)
    raise HTTPException(
        status_code=501,
        detail="Work search is not yet available.",
    )


# ---------------------------------------------------------------------------
# DETAIL ENDPOINTS — single-entity lookups (awaiting metadata store)
# ---------------------------------------------------------------------------


@app.get("/search/works/{work_id}", response_model=Work)
async def get_work_by_id(work_id: str):
    """Get a specific work by ID."""
    logger.info("GET /search/works/%s  (not yet implemented)", work_id)
    raise HTTPException(
        status_code=501,
        detail="Work detail lookup is not yet available.",
    )


@app.get("/search/authors/{author_id}", response_model=Author)
async def get_author_by_id(author_id: str):
    """Get a specific author by ID by querying the Graph DB."""
    logger.info("GET /search/authors/%s", author_id)

    try:
        # Replaces the hardcoded http://graph-db:8003
        graph_data = await graph_client.get_author_details(author_id)

        org_ids = [org["id"] for org in graph_data.get("organizations", [])]

        return {
            "id": graph_data["id"],
            "name": graph_data["name"],
            "h_index": graph_data.get("h_index", 0),
            "works_count": graph_data.get("works_count", 0),
            "org_ids": org_ids,
            "citation_count": 0,
        }

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Author not found") from e
        raise HTTPException(status_code=502, detail="Upstream Graph DB error") from e
    except (httpx.RequestError, httpx.HTTPError) as e:
        logger.error("Error communicating with Graph DB: %s", e)
        raise HTTPException(status_code=503, detail="Graph DB service is currently unavailable.") from e


@app.get("/search/orgs/{org_id}", response_model=Organization)
async def get_org_by_id(org_id: str):
    """Get a specific organization by ID."""
    logger.info("GET /search/orgs/%s  (not yet implemented)", org_id)
    raise HTTPException(
        status_code=501,
        detail="Organization detail lookup is not yet available.",
    )


@app.get("/search/topics/{topic_id}", response_model=Topic)
async def get_topic_by_id(topic_id: str):
    """Get a specific topic by ID."""
    logger.info("GET /search/topics/%s  (not yet implemented)", topic_id)
    raise HTTPException(
        status_code=501,
        detail="Topic detail lookup is not yet available.",
    )


@app.get("/viz/author-network/{author_id}")
async def get_author_network_viz(author_id: str):
    """Proxy endpoint to fetch graph visualization data for an author."""
    logger.info("GET /viz/author-network/%s", author_id)
    try:
        # Use graph_client: it respects settings and handles the async client lifecycle
        return await graph_client.get_viz_data(author_id)
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            raise HTTPException(status_code=404, detail="Visualization data not found") from e
        raise HTTPException(status_code=503, detail="Graph visualization service unavailable.") from e
    except (httpx.RequestError, httpx.HTTPError) as e:
        logger.error("Error communicating with Graph DB for viz: %s", e)
        raise HTTPException(status_code=503, detail="Graph visualization service unavailable.") from e


# ---------------------------------------------------------------------------
# IDENTITY ENDPOINTS
# ---------------------------------------------------------------------------


@app.get("/identity/lookup", response_model=LookupResponse)
async def lookup_identity(name: str = Query(..., description="Name of the author/user to lookup in the directory")):
    """
    Proxy endpoint to fetch exact and fuzzy-matched identity records
    from the downstream Identity API.
    """
    logger.info("GET /identity/lookup  name=%r", name)

    identity_service_url = getattr(settings, "identity_api_url", "http://identity-api:8005")

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{identity_service_url}/lookup", params={"name": name}, timeout=10.0)

        response.raise_for_status()
        return response.json()

    except httpx.HTTPStatusError as e:
        logger.error("Identity API returned error: %s %s", e.response.status_code, e.response.text)
        raise HTTPException(
            status_code=e.response.status_code, detail="Upstream identity service returned an error."
        ) from e
    except httpx.RequestError as e:
        logger.error("Error communicating with Identity API: %s", e)
        raise HTTPException(status_code=503, detail="Identity service is currently unavailable.") from e


# ---------------------------------------------------------------------------
# Entrypoint for local development
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.api_host, port=settings.api_port)
