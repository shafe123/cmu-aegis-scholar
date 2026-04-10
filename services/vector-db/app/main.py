"""FastAPI application for vector database operations with Milvus."""

import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
from fastembed import TextEmbedding
from fastapi import FastAPI, HTTPException, status
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    connections,
    utility,
)

from app.config import AVAILABLE_MODELS, settings
from app.schemas import (
    VectorSearchRequest,
    TextSearchRequest,
    CreateAuthorEmbeddingRequest,
    CreateAuthorVectorRequest,
    VectorSearchResult,
    PaginationMetadata,
    VectorSearchResponse,
    HealthResponse,
    CollectionInfo,
    ModelInfo,
    ModelsResponse,
    CreateAuthorEmbeddingResponse,
    CreateAuthorVectorResponse,
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables (initialized on startup)
embedding_models: Dict[str, TextEmbedding] = {}  # Cache of loaded models
model_dimensions: Dict[str, int] = {}  # Cache of model dimensions

# Cache for loaded collections and their schema info
_loaded_collections: Dict[str, Collection] = {}
_collection_schema_cache: Dict[str, Dict[str, Any]] = {}


# Model management functions
def get_or_load_model(model_name: str) -> TextEmbedding:
    """
    Get a model from cache or load it if not already loaded.

    Args:
        model_name: Name of the model to load

    Returns:
        TextEmbedding: The loaded model

    Raises:
        ValueError: If model_name is not in AVAILABLE_MODELS
        RuntimeError: If model fails to load
    """
    if model_name not in AVAILABLE_MODELS:
        available = ", ".join(AVAILABLE_MODELS.keys())
        raise ValueError(
            f"Model '{model_name}' is not available. Available models: {available}"
        )

    # Return from cache if already loaded
    if model_name in embedding_models:
        return embedding_models[model_name]

    # Load the model
    try:
        logger.info("Loading model: %s", model_name)

        # FastEmbed model name mapping
        fastembed_model = AVAILABLE_MODELS[model_name].get("fastembed_name", model_name)
        model = TextEmbedding(model_name=fastembed_model)

        embedding_models[model_name] = model

        # Cache the dimension
        dim = AVAILABLE_MODELS[model_name]["dimension"]
        model_dimensions[model_name] = dim

        logger.info("Model '%s' loaded successfully (dimension: %d)", model_name, dim)
        return model
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to load model '%s': %s", model_name, e)
        raise RuntimeError(f"Failed to load model '{model_name}': {str(e)}") from e


def get_model_dimension(model_name: str) -> int:
    """
    Get the dimension of a model without loading it if possible.

    Args:
        model_name: Name of the model

    Returns:
        int: Dimension of the model's embeddings
    """
    # Check cache first
    if model_name in model_dimensions:
        return model_dimensions[model_name]

    # Check config
    if (
        model_name in AVAILABLE_MODELS
        and AVAILABLE_MODELS[model_name]["dimension"] is not None
    ):
        return AVAILABLE_MODELS[model_name]["dimension"]

    # Need to load the model to determine dimension
    model = get_or_load_model(model_name)
    return model.get_sentence_embedding_dimension()


# Milvus connection management
def get_milvus_connection():
    """Establish connection to Milvus."""
    try:
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port,
            user=settings.milvus_user if settings.milvus_user else None,
            password=settings.milvus_password if settings.milvus_password else None,
        )
        logger.info(
            "Connected to Milvus at %s:%d", settings.milvus_host, settings.milvus_port
        )
        return True
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to connect to Milvus: %s", e)
        return False


def disconnect_milvus():
    """Disconnect from Milvus."""
    try:
        connections.disconnect("default")
        logger.info("Disconnected from Milvus")
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error disconnecting from Milvus: %s", e)


def initialize_default_collection():
    """Initialize the default collection for author embeddings if it doesn't exist."""
    collection_name = settings.default_collection

    try:
        if not utility.has_collection(collection_name):
            logger.info(
                "Collection '%s' does not exist. Creating it...", collection_name
            )

            # Get the embedding dimension from config/cache
            try:
                # Load model to ensure it's cached (side effect)
                get_or_load_model(settings.default_embedding_model)
                # Get dimension from model_dimensions cache (populated during load)
                embedding_dim = model_dimensions[settings.default_embedding_model]
            except Exception as e:  # pylint: disable=broad-exception-caught
                logger.warning(
                    "Could not determine embedding dimension for "
                    "collection initialization: %s",
                    e,
                )
                logger.warning("Skipping collection initialization.")
                return

            # Define schema
            fields = [
                FieldSchema(
                    name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=255
                ),
                FieldSchema(name="author_id", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(
                    name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim
                ),
                FieldSchema(name="num_abstracts", dtype=DataType.INT64),
                FieldSchema(
                    name="citation_count", dtype=DataType.INT64, default_value=0
                ),
            ]

            schema = CollectionSchema(
                fields=fields,
                description="Author embeddings from averaged paper abstracts",
            )

            collection = Collection(name=collection_name, schema=schema)

            # Create index for vector field
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128},
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            logger.info(
                "Created collection '%s' with index (dim=%d)",
                collection_name,
                embedding_dim,
            )
        else:
            logger.info("Collection '%s' already exists", collection_name)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error initializing default collection: %s", e)


# Application lifecycle events
@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Manage application lifecycle (startup and shutdown)."""
    # Startup
    logger.info("Starting Vector DB Service...")
    get_milvus_connection()

    # Preload default embedding model
    logger.info(
        "Preloading default embedding model: %s", settings.default_embedding_model
    )
    try:
        # Load model into cache (side effect is the purpose)
        get_or_load_model(settings.default_embedding_model)
        logger.info(
            "Default model loaded successfully (dimension: %d)",
            model_dimensions[settings.default_embedding_model],
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Failed to load default embedding model: %s", e)

    # Initialize default collection
    initialize_default_collection()

    # Pre-load default collection into memory and cache schema
    try:
        collection_name = settings.default_collection
        if utility.has_collection(collection_name):
            collection = Collection(collection_name)
            collection.load()  # Load into memory once at startup
            _loaded_collections[collection_name] = collection

            # Cache schema info for validation
            schema_dict = collection.schema.to_dict()
            embedding_field = next(
                (f for f in schema_dict["fields"] if f["name"] == "embedding"), None
            )
            if embedding_field:
                _collection_schema_cache[collection_name] = {
                    "embedding_dim": embedding_field["params"]["dim"]
                }
            logger.info("Pre-loaded collection '%s' into memory", collection_name)
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error pre-loading default collection: %s", e)

    yield

    # Shutdown
    logger.info("Shutting down Vector DB Service...")
    disconnect_milvus()


# Initialize FastAPI app with lifespan
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
    lifespan=lifespan,
    docs_url=None,  # Disable default docs
    redoc_url=None,  # Disable default redoc
)

# Mount static files for favicon
static_path = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_path)), name="static")


# Helper Functions
def _upsert_author_embedding(  # pylint: disable=too-many-positional-arguments
    collection_name: str,
    author_id: str,
    author_name: str,
    embedding: list,
    num_abstracts: int,
    citation_count: int = 0,
) -> tuple[bool, str]:
    """
    Shared helper function to upsert author embedding into collection.

    Args:
        collection_name: Name of the collection
        author_id: Author's ID (should already include any prefix)
        author_name: Author's display name
        embedding: Embedding vector as a list
        num_abstracts: Number of abstracts used to create the embedding
        citation_count: Author's citation count (defaults to 0 if not provided)

    Returns:
        Tuple of (is_update, action_description)

    Raises:
        HTTPException: If collection not found or validation fails
    """
    # Validate embedding
    if not embedding:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Embedding vector is required",
        )

    embedding_dim = len(embedding)

    # Get collection from cache or load it
    if collection_name in _loaded_collections:
        collection = _loaded_collections[collection_name]
        # Ensure collection is still loaded (connection might have been lost)
        try:
            # Test if collection is accessible
            _ = collection.num_entities
        except Exception as e:  # pylint: disable=broad-exception-caught
            # Collection lost connection, reload it
            logger.warning(
                "Collection '%s' lost connection, reloading: %s", collection_name, e
            )
            collection = Collection(collection_name)
            collection.load()
            _loaded_collections[collection_name] = collection
    else:
        # Collection not cached, load it now
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=(
                    f"Collection '{collection_name}' not found. "
                    "Use the default collection or create it first."
                ),
            )
        collection = Collection(collection_name)
        collection.load()
        _loaded_collections[collection_name] = collection
        logger.info(
            "Loaded collection '%s' into memory (not in cache)", collection_name
        )

    # Validate embedding dimension using cached schema or fetch it
    if collection_name in _collection_schema_cache:
        expected_dim = _collection_schema_cache[collection_name]["embedding_dim"]
    else:
        # Schema not cached, fetch and cache it
        schema_dict = collection.schema.to_dict()
        embedding_field = next(
            (f for f in schema_dict["fields"] if f["name"] == "embedding"), None
        )
        if embedding_field:
            expected_dim = embedding_field["params"]["dim"]
            _collection_schema_cache[collection_name] = {"embedding_dim": expected_dim}
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Collection schema missing embedding field",
            )

    if embedding_dim != expected_dim:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Embedding dimension mismatch. Expected {expected_dim}, got {embedding_dim}",
        )

    # Check if author already exists (optional, for logging purposes)
    author_pk = author_id
    try:
        existing_entities = collection.query(
            expr=f'id == "{author_pk}"', output_fields=["id"], limit=1
        )
        is_update = len(existing_entities) > 0
    except Exception as e:  # pylint: disable=broad-exception-caught
        # If query fails, assume it's a new insert
        logger.warning("Could not check existence for %s: %s", author_pk, e)
        is_update = False

    # Prepare entity data
    entity_data = [
        [author_pk],  # id
        [author_id],  # author_id
        [author_name],  # author_name
        [embedding],  # embedding
        [num_abstracts],  # num_abstracts
        [citation_count],  # citation_count
    ]

    # Upsert the data (insert if new, update if exists)
    collection.upsert(entity_data)
    # Note: Removed flush() - Milvus will batch writes automatically for better performance
    # Data will be persisted naturally. For immediate persistence, flush can be called periodically.

    action = "updated" if is_update else "created"
    return is_update, action


# API Endpoints
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": "vector-db",
        "message": "Aegis Scholar Vector DB API",
        "version": settings.api_version,
    }


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """Health check endpoint."""
    try:
        # Check if connected, if not try to reconnect
        if not connections.has_connection("default"):
            get_milvus_connection()

        # List all collections
        collections = utility.list_collections()

        return HealthResponse(
            status="healthy", milvus_connected=True, collections=collections
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Health check failed: %s", e)
        return HealthResponse(
            status="unhealthy", milvus_connected=False, collections=[]
        )


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
        swagger_favicon_url="/favicon.ico",
    )


@app.get("/redoc", include_in_schema=False)
async def custom_redoc_html():
    """Custom ReDoc with custom favicon."""
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - ReDoc",
        redoc_favicon_url="/favicon.ico",
    )


@app.get("/collections", response_model=List[CollectionInfo], tags=["Collections"])
async def list_collections():
    """List all available collections."""
    try:
        collection_names = utility.list_collections()
        collections_info = []

        for name in collection_names:
            collection = Collection(name)
            collection.load()
            collections_info.append(
                CollectionInfo(
                    name=name,
                    num_entities=collection.num_entities,
                    description=collection.description
                    if hasattr(collection, "description")
                    else None,
                )
            )

        return collections_info
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing collections: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}",
        ) from e


@app.get(
    "/collections/{collection_name}",
    response_model=CollectionInfo,
    tags=["Collections"],
)
async def get_collection_info(collection_name: str):
    """Get information about a specific collection."""
    try:
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found",
            )

        collection = Collection(collection_name)
        collection.load()

        return CollectionInfo(
            name=collection_name,
            num_entities=collection.num_entities,
            description=collection.description
            if hasattr(collection, "description")
            else None,
        )
    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error getting collection info: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection info: {str(e)}",
        ) from e


@app.get("/models", response_model=ModelsResponse, tags=["Models"])
async def list_models():
    """
    List all available embedding models.

    Returns information about each model including:
    - Model name
    - Embedding dimension (if known)
    - Description
    - Whether the model is currently loaded in memory
    """
    try:
        models_list = []

        for model_name, model_config in AVAILABLE_MODELS.items():
            models_list.append(
                ModelInfo(
                    name=model_name,
                    dimension=model_config["dimension"],
                    description=model_config["description"],
                    loaded=model_name in embedding_models,
                )
            )

        return ModelsResponse(
            models=models_list, default_model=settings.default_embedding_model
        )
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error listing models: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list models: {str(e)}",
        ) from e


@app.post("/search/vector", response_model=VectorSearchResponse, tags=["Search"])
async def vector_search(request: VectorSearchRequest):
    """
    Perform vector similarity search using a pre-computed query vector.

    Args:
        request: VectorSearchRequest containing query vector and search parameters

    Returns:
        VectorSearchResponse with search results
    """
    collection_name = request.collection_name or settings.default_collection

    try:
        # Check if collection exists
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found",
            )

        # Load collection
        collection = Collection(collection_name)
        collection.load()

        # Prepare search parameters
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

        # Calculate total results needed (offset + limit + 1 to check if there are more)
        total_needed = request.offset + request.limit + 1

        # Execute search
        start_time = time.time()
        results = collection.search(
            data=[request.query_vector],
            anns_field="embedding",
            param=search_params,
            limit=total_needed,
            output_fields=request.output_fields or ["*"],
            expr=request.filter_expr,
        )
        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Format all results - flatten entity fields
        all_results = []
        for hits in results:
            for hit in hits:
                # Extract fields directly from entity to create flattened result
                result_data = {"distance": hit.distance}

                if hasattr(hit, "entity"):
                    for field_name in hit.entity.fields:
                        # Skip 'id' and 'embedding' fields to avoid duplication
                        if field_name not in ["id", "embedding"]:
                            result_data[field_name] = hit.entity.get(field_name)

                all_results.append(VectorSearchResult(**result_data))

        # Apply pagination
        paginated_results = all_results[request.offset : request.offset + request.limit]
        has_more = len(all_results) > request.offset + request.limit

        return VectorSearchResponse(
            results=paginated_results,
            collection_name=collection_name,
            search_time_ms=search_time,
            pagination=PaginationMetadata(
                offset=request.offset,
                limit=request.limit,
                returned=len(paginated_results),
                has_more=has_more,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error performing vector search: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform search: {str(e)}",
        ) from e


@app.post("/search/text", response_model=VectorSearchResponse, tags=["Search"])
async def text_search(request: TextSearchRequest):
    """
    Perform vector similarity search using a text query.

    This endpoint:
    1. Takes a text query
    2. Converts the text to an embedding vector using the specified (or default) model
    3. Performs vector similarity search with the generated embedding

    Args:
        request: TextSearchRequest containing query text, model name, and search parameters

    Returns:
        VectorSearchResponse with search results
    """
    collection_name = request.collection_name or settings.default_collection
    model_name = request.model_name or settings.default_embedding_model

    try:
        # Get or load the embedding model
        try:
            model = get_or_load_model(model_name)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e

        # Check if collection exists
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found",
            )

        # Load collection
        collection = Collection(collection_name)
        collection.load()

        # Convert text query to embedding
        logger.info(
            "Converting query text to embedding using model '%s': '%s...'",
            model_name,
            request.query_text[:50],
        )
        # FastEmbed returns a generator, convert to list and get first embedding
        embeddings_gen = model.embed([request.query_text])
        query_embedding = np.array(next(iter(embeddings_gen)))

        # Prepare search parameters
        search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

        # Calculate total results needed (offset + limit + 1 to check if there are more)
        total_needed = request.offset + request.limit + 1

        # Execute search
        start_time = time.time()
        results = collection.search(
            data=[query_embedding.tolist()],
            anns_field="embedding",
            param=search_params,
            limit=total_needed,
            output_fields=request.output_fields or ["*"],
            expr=request.filter_expr,
        )
        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds

        # Format all results - flatten entity fields
        all_results = []
        for hits in results:
            for hit in hits:
                # Extract fields directly from entity to create flattened result
                result_data = {"distance": hit.distance}

                if hasattr(hit, "entity"):
                    for field_name in hit.entity.fields:
                        # Skip 'id' and 'embedding' fields to avoid duplication
                        if field_name not in ["id", "embedding"]:
                            result_data[field_name] = hit.entity.get(field_name)

                all_results.append(VectorSearchResult(**result_data))

        # Apply pagination
        paginated_results = all_results[request.offset : request.offset + request.limit]
        has_more = len(all_results) > request.offset + request.limit

        return VectorSearchResponse(
            results=paginated_results,
            collection_name=collection_name,
            search_time_ms=search_time,
            pagination=PaginationMetadata(
                offset=request.offset,
                limit=request.limit,
                returned=len(paginated_results),
                has_more=has_more,
            ),
        )

    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error performing text search: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform search: {str(e)}",
        ) from e


@app.post(
    "/authors/embeddings",
    response_model=CreateAuthorEmbeddingResponse,
    tags=["Authors"],
)
async def create_author_embedding(request: CreateAuthorEmbeddingRequest):
    """
    Create or update author embedding from a list of abstracts.

    This endpoint:
    1. Takes a list of paper abstracts for an author
    2. Converts each abstract into an embedding vector using the specified
       (or default) model
    3. Averages the embeddings to create a single author representation
    4. Upserts the averaged embedding in the vector database
       (creates new or updates existing)

    Args:
        request: CreateAuthorEmbeddingRequest containing author info,
                 abstracts, and optional model name

    Returns:
        CreateAuthorEmbeddingResponse with success status
    """
    collection_name = request.collection_name or settings.default_collection
    model_name = request.model_name or settings.default_embedding_model

    try:
        # Get or load the embedding model
        try:
            model = get_or_load_model(model_name)
        except (ValueError, RuntimeError) as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
            ) from e

        # Validate abstracts
        if not request.abstracts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one abstract is required",
            )

        # Filter out empty abstracts
        valid_abstracts = [
            abstract.strip() for abstract in request.abstracts if abstract.strip()
        ]
        if not valid_abstracts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid abstracts provided (all were empty)",
            )

        logger.info(
            "Processing %d abstracts for author %s using model '%s'",
            len(valid_abstracts),
            request.author_id,
            model_name,
        )

        # Generate embeddings for all abstracts
        # FastEmbed returns a generator, convert to numpy array
        embeddings_gen = model.embed(valid_abstracts)
        abstract_embeddings = np.array(list(embeddings_gen))

        # Average the embeddings
        averaged_embedding = np.mean(abstract_embeddings, axis=0)
        embedding_dim = len(averaged_embedding)

        # Use shared helper to upsert the embedding
        _, action = _upsert_author_embedding(
            collection_name=collection_name,
            author_id=request.author_id,
            author_name=request.author_name,
            embedding=averaged_embedding.tolist(),
            num_abstracts=len(valid_abstracts),
            citation_count=request.citation_count or 0,
        )

        logger.info(
            "Successfully %s embedding for author %s in collection '%s'",
            action,
            request.author_id,
            collection_name,
        )

        return CreateAuthorEmbeddingResponse(
            author_id=request.author_id,
            author_name=request.author_name,
            embedding_dim=embedding_dim,
            num_abstracts_processed=len(valid_abstracts),
            collection_name=collection_name,
            success=True,
            message=f"Author embedding {action} and stored successfully",
        )

    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error creating author embedding: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create author embedding: {str(e)}",
        ) from e


@app.post(
    "/authors/vector", response_model=CreateAuthorVectorResponse, tags=["Authors"]
)
async def create_author_vector(request: CreateAuthorVectorRequest):
    """
    Create or update author with a pre-computed embedding vector.

    This endpoint:
    1. Takes a pre-computed embedding vector for an author
    2. Validates the vector dimension matches the specified model or collection schema
    3. Upserts the embedding in the vector database (creates new or updates existing)

    This is useful when you already have embeddings computed externally and want to
    upload them directly without computing from abstracts.

    Args:
        request: CreateAuthorVectorRequest containing author info,
                 pre-computed vector, and optional model name

    Returns:
        CreateAuthorVectorResponse with success status
    """
    collection_name = request.collection_name or settings.default_collection

    try:
        # Validate embedding vector
        if not request.embedding:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Embedding vector is required",
            )

        embedding_dim = len(request.embedding)

        # If model_name is provided, validate dimension against the model
        if request.model_name:
            try:
                expected_dim = get_model_dimension(request.model_name)
                if embedding_dim != expected_dim:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=(
                            f"Embedding dimension mismatch for model "
                            f"'{request.model_name}'. Expected {expected_dim}, "
                            f"got {embedding_dim}"
                        ),
                    )
            except (ValueError, RuntimeError) as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Error validating model dimension: {str(e)}",
                ) from e

        # Use shared helper to upsert the embedding (also validates against collection schema)
        _, action = _upsert_author_embedding(
            collection_name=collection_name,
            author_id=request.author_id,
            author_name=request.author_name,
            embedding=request.embedding,
            num_abstracts=request.num_abstracts or 0,
            citation_count=request.citation_count or 0,
        )

        logger.info(
            "Successfully %s vector for author %s in collection '%s'",
            action,
            request.author_id,
            collection_name,
        )

        return CreateAuthorVectorResponse(
            author_id=request.author_id,
            author_name=request.author_name,
            embedding_dim=embedding_dim,
            collection_name=collection_name,
            success=True,
            message=f"Author vector {action} and stored successfully",
        )

    except HTTPException:
        raise
    except Exception as e:  # pylint: disable=broad-exception-caught
        logger.error("Error creating author vector: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create author vector: {str(e)}",
        ) from e
