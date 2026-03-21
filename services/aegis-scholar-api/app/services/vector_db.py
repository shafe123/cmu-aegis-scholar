"""
HTTP client for the Aegis Scholar Vector DB service.

This module handles all communication between the main API and the
vector database microservice running on port 8002. It uses httpx for
async HTTP requests and provides a clean interface for searching
author embeddings by text query.
"""
import httpx
import logging
from typing import Optional, List, Dict, Any

from app.config import settings

logger = logging.getLogger(__name__)

# Module-level async client — initialized at startup, closed at shutdown
_client: Optional[httpx.AsyncClient] = None


async def init_client():
    """Create the async HTTP client. Call once at app startup."""
    global _client
    _client = httpx.AsyncClient(
        base_url=settings.vector_db_url,
        timeout=httpx.Timeout(settings.vector_db_timeout),
    )
    logger.info(f"Vector DB client initialized (base_url={settings.vector_db_url})")


async def close_client():
    """Close the async HTTP client. Call once at app shutdown."""
    global _client
    if _client and not _client.is_closed:
        await _client.aclose()
        _client = None
        logger.info("Vector DB client closed")


def _get_client() -> httpx.AsyncClient:
    """Return the active client or raise if not initialized."""
    if _client is None or _client.is_closed:
        raise RuntimeError(
            "Vector DB client is not initialized. "
            "Ensure init_client() was called at startup."
        )
    return _client


# ---------------------------------------------------------------------------
# Search operations
# ---------------------------------------------------------------------------

async def search_by_text(
    query_text: str,
    limit: int = 10,
    offset: int = 0,
    collection_name: Optional[str] = None,
    output_fields: Optional[List[str]] = None,
    filter_expr: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Search for authors by natural-language query.

    Calls POST /search/text on the vector DB service, which:
      1. Embeds the query text using sentence-transformers/all-MiniLM-L6-v2
      2. Runs a nearest-neighbor search in Milvus
      3. Returns authors ranked by cosine/L2 distance

    Args:
        query_text: The user's search string.
        limit:      Maximum results to return.
        offset:     Number of results to skip (pagination).
        collection_name: Milvus collection to search (defaults to aegis_vectors).
        output_fields: Which Milvus fields to include in results.
        filter_expr: Optional Milvus boolean filter (e.g. "num_abstracts > 10").

    Returns:
        Raw JSON response dict from the vector DB service. Shape:
        {
            "results": [ { "distance": float, "author_id": str, ... }, ... ],
            "collection_name": str,
            "search_time_ms": float,
            "pagination": { "offset": int, "limit": int, "returned": int, "has_more": bool }
        }

    Raises:
        httpx.ConnectError:     Vector DB service is unreachable.
        httpx.HTTPStatusError:  Vector DB returned a 4xx/5xx response.
    """
    client = _get_client()

    payload: Dict[str, Any] = {
        "query_text": query_text,
        "limit": limit,
        "offset": offset,
    }
    if collection_name:
        payload["collection_name"] = collection_name
    if output_fields:
        payload["output_fields"] = output_fields
    if filter_expr:
        payload["filter_expr"] = filter_expr

    logger.debug(f"POST /search/text  payload={payload}")
    response = await client.post("/search/text", json=payload)
    response.raise_for_status()
    return response.json()


async def health() -> Dict[str, Any]:
    """Check whether the vector DB service is reachable and healthy."""
    client = _get_client()
    response = await client.get("/health")
    response.raise_for_status()
    return response.json()
