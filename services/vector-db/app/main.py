from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from pymilvus import connections, Collection, utility, DataType, FieldSchema, CollectionSchema
from sentence_transformers import SentenceTransformer
import numpy as np
import logging

from app.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=settings.api_description,
)

# Global variables (initialized on startup)
embedding_model = None

# Cache for loaded collections and their schema info
_loaded_collections: Dict[str, Collection] = {}
_collection_schema_cache: Dict[str, Dict[str, Any]] = {}


# Pydantic models for request/response
class VectorSearchRequest(BaseModel):
    """Request model for vector search."""
    query_vector: List[float] = Field(..., description="Query vector for similarity search")
    collection_name: Optional[str] = Field(None, description="Collection to search in")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results to return per page")
    offset: int = Field(0, ge=0, description="Number of results to skip for pagination")
    output_fields: Optional[List[str]] = Field(None, description="Fields to include in results")
    filter_expr: Optional[str] = Field(None, description="Filter expression for search")


class TextSearchRequest(BaseModel):
    """Request model for text-based search."""
    query_text: str = Field(..., min_length=1, description="Query text to search for")
    collection_name: Optional[str] = Field(None, description="Collection to search in")
    limit: int = Field(10, ge=1, le=100, description="Maximum number of results to return per page")
    offset: int = Field(0, ge=0, description="Number of results to skip for pagination")
    output_fields: Optional[List[str]] = Field(None, description="Fields to include in results")
    filter_expr: Optional[str] = Field(None, description="Filter expression for search")


class VectorSearchResult(BaseModel):
    """Single search result."""
    id: str
    distance: float
    entity: Dict[str, Any]


class PaginationMetadata(BaseModel):
    """Pagination metadata."""
    offset: int
    limit: int
    returned: int
    has_more: bool


class VectorSearchResponse(BaseModel):
    """Response model for vector search."""
    results: List[VectorSearchResult]
    collection_name: str
    search_time_ms: float
    pagination: PaginationMetadata


class HealthResponse(BaseModel):
    """Health check response."""
    status: str
    milvus_connected: bool
    collections: List[str]


class CollectionInfo(BaseModel):
    """Collection information."""
    name: str
    num_entities: int
    description: Optional[str] = None


class CreateAuthorEmbeddingRequest(BaseModel):
    """Request model for creating or updating author embedding from abstracts."""
    author_id: str = Field(..., description="Unique identifier for the author")
    author_name: str = Field(..., description="Name of the author")
    abstracts: List[str] = Field(..., min_length=1, description="List of paper abstracts by the author")
    collection_name: Optional[str] = Field(None, description="Collection to store the embedding in")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata for the author")


class CreateAuthorEmbeddingResponse(BaseModel):
    """Response model for author embedding creation."""
    author_id: str
    author_name: str
    embedding_dim: int
    num_abstracts_processed: int
    collection_name: str
    success: bool
    message: str


class CreateAuthorVectorRequest(BaseModel):
    """Request model for creating or updating author with pre-computed vector."""
    author_id: str = Field(..., description="Unique identifier for the author")
    author_name: str = Field(..., description="Name of the author")
    embedding: List[float] = Field(..., description="Pre-computed embedding vector for the author")
    num_abstracts: Optional[int] = Field(None, description="Number of abstracts used to compute the embedding")
    collection_name: Optional[str] = Field(None, description="Collection to store the embedding in")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata for the author")


class CreateAuthorVectorResponse(BaseModel):
    """Response model for author vector upload."""
    author_id: str
    author_name: str
    embedding_dim: int
    collection_name: str
    success: bool
    message: str


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
        logger.info(f"Connected to Milvus at {settings.milvus_host}:{settings.milvus_port}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to Milvus: {e}")
        return False


def disconnect_milvus():
    """Disconnect from Milvus."""
    try:
        connections.disconnect("default")
        logger.info("Disconnected from Milvus")
    except Exception as e:
        logger.error(f"Error disconnecting from Milvus: {e}")


def initialize_default_collection():
    """Initialize the default collection for author embeddings if it doesn't exist."""
    collection_name = settings.default_collection
    
    try:
        if not utility.has_collection(collection_name):
            logger.info(f"Collection '{collection_name}' does not exist. Creating it...")
            
            # Get embedding dimension from the model
            if embedding_model is None:
                logger.warning("Embedding model not loaded. Skipping collection initialization.")
                return
            
            # Use the model's actual dimension
            embedding_dim = embedding_model.get_sentence_embedding_dimension()
            
            # Define schema
            fields = [
                FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=255),
                FieldSchema(name="author_id", dtype=DataType.VARCHAR, max_length=255),
                FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=500),
                FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=embedding_dim),
                FieldSchema(name="num_abstracts", dtype=DataType.INT64),
            ]
            
            schema = CollectionSchema(
                fields=fields,
                description="Author embeddings from averaged paper abstracts"
            )
            
            collection = Collection(name=collection_name, schema=schema)
            
            # Create index for vector field
            index_params = {
                "metric_type": "L2",
                "index_type": "IVF_FLAT",
                "params": {"nlist": 128}
            }
            collection.create_index(field_name="embedding", index_params=index_params)
            logger.info(f"Created collection '{collection_name}' with index (dim={embedding_dim})")
        else:
            logger.info(f"Collection '{collection_name}' already exists")
    except Exception as e:
        logger.error(f"Error initializing default collection: {e}")


# Application lifecycle events
@app.on_event("startup")
async def startup_event():
    """Initialize Milvus connection and embedding model on startup."""
    global embedding_model, _loaded_collections, _collection_schema_cache
    logger.info("Starting Vector DB Service...")
    get_milvus_connection()
    
    # Initialize embedding model
    logger.info(f"Loading embedding model: {settings.embedding_model_name}")
    try:
        embedding_model = SentenceTransformer(settings.embedding_model_name)
        logger.info("Embedding model loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {e}")
        embedding_model = None
    
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
            embedding_field = next((f for f in schema_dict['fields'] if f['name'] == 'embedding'), None)
            if embedding_field:
                _collection_schema_cache[collection_name] = {
                    'embedding_dim': embedding_field['params']['dim']
                }
            logger.info(f"Pre-loaded collection '{collection_name}' into memory")
    except Exception as e:
        logger.error(f"Error pre-loading default collection: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    logger.info("Shutting down Vector DB Service...")
    disconnect_milvus()


# API Endpoints
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint."""
    return {
        "service": "vector-db",
        "message": "AEGIS Scholar Vector DB Service",
        "version": settings.api_version
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
            status="healthy",
            milvus_connected=True,
            collections=collections
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return HealthResponse(
            status="unhealthy",
            milvus_connected=False,
            collections=[]
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
                    description=collection.description if hasattr(collection, 'description') else None
                )
            )
        
        return collections_info
    except Exception as e:
        logger.error(f"Error listing collections: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list collections: {str(e)}"
        )


@app.get("/collections/{collection_name}", response_model=CollectionInfo, tags=["Collections"])
async def get_collection_info(collection_name: str):
    """Get information about a specific collection."""
    try:
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )
        
        collection = Collection(collection_name)
        collection.load()
        
        return CollectionInfo(
            name=collection_name,
            num_entities=collection.num_entities,
            description=collection.description if hasattr(collection, 'description') else None
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting collection info: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get collection info: {str(e)}"
        )


@app.post("/search/vector", response_model=VectorSearchResponse, tags=["Search"])
async def vector_search(request: VectorSearchRequest):
    """
    Perform vector similarity search using a pre-computed query vector.
    
    Args:
        request: VectorSearchRequest containing query vector and search parameters
    
    Returns:
        VectorSearchResponse with search results
    """
    import time
    
    collection_name = request.collection_name or settings.default_collection
    
    try:
        # Check if collection exists
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
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
            expr=request.filter_expr
        )
        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Format all results
        all_results = []
        for hits in results:
            for hit in hits:
                all_results.append(
                    VectorSearchResult(
                        id=str(hit.id),
                        distance=hit.distance,
                        entity=hit.entity.to_dict()
                    )
                )
        
        # Apply pagination
        paginated_results = all_results[request.offset:request.offset + request.limit]
        has_more = len(all_results) > request.offset + request.limit
        
        return VectorSearchResponse(
            results=paginated_results,
            collection_name=collection_name,
            search_time_ms=search_time,
            pagination=PaginationMetadata(
                offset=request.offset,
                limit=request.limit,
                returned=len(paginated_results),
                has_more=has_more
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing vector search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform search: {str(e)}"
        )


@app.post("/search/text", response_model=VectorSearchResponse, tags=["Search"])
async def text_search(request: TextSearchRequest):
    """
    Perform vector similarity search using a text query.
    
    This endpoint:
    1. Takes a text query
    2. Converts the text to an embedding vector using the sentence transformer model
    3. Performs vector similarity search with the generated embedding
    
    Args:
        request: TextSearchRequest containing query text and search parameters
    
    Returns:
        VectorSearchResponse with search results
    """
    import time
    
    collection_name = request.collection_name or settings.default_collection
    
    try:
        # Check if embedding model is loaded
        if embedding_model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedding model not available. Service may still be initializing."
            )
        
        # Check if collection exists
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found"
            )
        
        # Load collection
        collection = Collection(collection_name)
        collection.load()
        
        # Convert text query to embedding
        logger.info(f"Converting query text to embedding: '{request.query_text[:50]}...'")
        query_embedding = embedding_model.encode(
            [request.query_text],
            show_progress_bar=False,
            convert_to_numpy=True
        )[0]  # Get first (and only) embedding
        
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
            expr=request.filter_expr
        )
        search_time = (time.time() - start_time) * 1000  # Convert to milliseconds
        
        # Format all results
        all_results = []
        for hits in results:
            for hit in hits:
                all_results.append(
                    VectorSearchResult(
                        id=str(hit.id),
                        distance=hit.distance,
                        entity=hit.entity.to_dict()
                    )
                )
        
        # Apply pagination
        paginated_results = all_results[request.offset:request.offset + request.limit]
        has_more = len(all_results) > request.offset + request.limit
        
        return VectorSearchResponse(
            results=paginated_results,
            collection_name=collection_name,
            search_time_ms=search_time,
            pagination=PaginationMetadata(
                offset=request.offset,
                limit=request.limit,
                returned=len(paginated_results),
                has_more=has_more
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error performing text search: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to perform search: {str(e)}"
        )


@app.post("/authors/embeddings", response_model=CreateAuthorEmbeddingResponse, tags=["Authors"])
async def create_author_embedding(request: CreateAuthorEmbeddingRequest):
    """
    Create or update author embedding from a list of abstracts.
    
    This endpoint:
    1. Takes a list of paper abstracts for an author
    2. Converts each abstract into an embedding vector
    3. Averages the embeddings to create a single author representation
    4. Upserts the averaged embedding in the vector database (creates new or updates existing)
    
    Args:
        request: CreateAuthorEmbeddingRequest containing author info and abstracts
    
    Returns:
        CreateAuthorEmbeddingResponse with success status
    """
    collection_name = request.collection_name or settings.default_collection
    
    try:
        # Check if embedding model is loaded
        if embedding_model is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Embedding model not available. Service may still be initializing."
            )
        
        # Validate abstracts
        if not request.abstracts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one abstract is required"
            )
        
        # Filter out empty abstracts
        valid_abstracts = [abstract.strip() for abstract in request.abstracts if abstract.strip()]
        if not valid_abstracts:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No valid abstracts provided (all were empty)"
            )
        
        logger.info(f"Processing {len(valid_abstracts)} abstracts for author {request.author_id}")
        
        # Generate embeddings for all abstracts
        abstract_embeddings = embedding_model.encode(
            valid_abstracts,
            show_progress_bar=False,
            convert_to_numpy=True
        )
        
        # Average the embeddings
        averaged_embedding = np.mean(abstract_embeddings, axis=0)
        embedding_dim = len(averaged_embedding)
        
        # Get the collection (should already exist from startup initialization)
        if not utility.has_collection(collection_name):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Collection '{collection_name}' not found. Use the default collection or create it first."
            )
        
        collection = Collection(collection_name)
        
        # Check if author already exists
        author_pk = f"author_{request.author_id}"
        existing_entities = collection.query(
            expr=f'id == "{author_pk}"',
            output_fields=["id"],
            limit=1
        )
        is_update = len(existing_entities) > 0
        
        # Prepare entity data
        entity_data = [
            [author_pk],                      # id
            [request.author_id],              # author_id
            [request.author_name],            # author_name
            [averaged_embedding.tolist()],    # embedding
            [len(valid_abstracts)],           # num_abstracts
        ]
        
        # Upsert the data (insert if new, update if exists)
        collection.upsert(entity_data)
        collection.flush()
        
        action = "updated" if is_update else "created"
        logger.info(f"Successfully {action} embedding for author {request.author_id} in collection '{collection_name}'")
        
        return CreateAuthorEmbeddingResponse(
            author_id=request.author_id,
            author_name=request.author_name,
            embedding_dim=embedding_dim,
            num_abstracts_processed=len(valid_abstracts),
            collection_name=collection_name,
            success=True,
            message=f"Author embedding {action} and stored successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating author embedding: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create author embedding: {str(e)}"
        )


@app.post("/authors/vector", response_model=CreateAuthorVectorResponse, tags=["Authors"])
async def create_author_vector(request: CreateAuthorVectorRequest):
    """
    Create or update author with a pre-computed embedding vector.
    
    This endpoint:
    1. Takes a pre-computed embedding vector for an author
    2. Validates the vector dimension matches the collection schema
    3. Upserts the embedding in the vector database (creates new or updates existing)
    
    This is useful when you already have embeddings computed externally and want to
    upload them directly without computing from abstracts.
    
    Args:
        request: CreateAuthorVectorRequest containing author info and pre-computed vector
    
    Returns:
        CreateAuthorVectorResponse with success status
    """
    collection_name = request.collection_name or settings.default_collection
    
    try:
        # Validate embedding vector
        if not request.embedding:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Embedding vector is required"
            )
        
        embedding_dim = len(request.embedding)
        
        # Get collection from cache or load it
        if collection_name in _loaded_collections:
            collection = _loaded_collections[collection_name]
            # Ensure collection is still loaded (connection might have been lost)
            try:
                # Test if collection is accessible
                collection.num_entities
            except Exception as e:
                # Collection lost connection, reload it
                logger.warning(f"Collection '{collection_name}' lost connection, reloading: {e}")
                collection = Collection(collection_name)
                collection.load()
                _loaded_collections[collection_name] = collection
        else:
            # Collection not cached, load it now
            if not utility.has_collection(collection_name):
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Collection '{collection_name}' not found. Use the default collection or create it first."
                )
            collection = Collection(collection_name)
            collection.load()
            _loaded_collections[collection_name] = collection
            logger.info(f"Loaded collection '{collection_name}' into memory (not in cache)")
        
        # Validate embedding dimension using cached schema or fetch it
        if collection_name in _collection_schema_cache:
            expected_dim = _collection_schema_cache[collection_name]['embedding_dim']
        else:
            # Schema not cached, fetch and cache it
            schema_dict = collection.schema.to_dict()
            embedding_field = next((f for f in schema_dict['fields'] if f['name'] == 'embedding'), None)
            if embedding_field:
                expected_dim = embedding_field['params']['dim']
                _collection_schema_cache[collection_name] = {'embedding_dim': expected_dim}
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Collection schema missing embedding field"
                )
        
        if embedding_dim != expected_dim:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Embedding dimension mismatch. Expected {expected_dim}, got {embedding_dim}"
            )
        
        # Check if author already exists (optional, for logging purposes)
        author_pk = f"author_{request.author_id}"
        try:
            existing_entities = collection.query(
                expr=f'id == "{author_pk}"',
                output_fields=["id"],
                limit=1
            )
            is_update = len(existing_entities) > 0
        except Exception as e:
            # If query fails, assume it's a new insert
            logger.warning(f"Could not check existence for {author_pk}: {e}")
            is_update = False
        
        # Prepare entity data
        entity_data = [
            [author_pk],                          # id
            [request.author_id],                  # author_id
            [request.author_name],                # author_name
            [request.embedding],                  # embedding (pre-computed)
            [request.num_abstracts or 0],         # num_abstracts
        ]
        
        # Upsert the data (insert if new, update if exists)
        collection.upsert(entity_data)
        # Note: Removed flush() - Milvus will batch writes automatically for better performance
        # Data will be persisted naturally. For immediate persistence, flush can be called periodically.
        
        action = "updated" if is_update else "created"
        logger.info(f"Successfully {action} vector for author {request.author_id} in collection '{collection_name}'")
        
        return CreateAuthorVectorResponse(
            author_id=request.author_id,
            author_name=request.author_name,
            embedding_dim=embedding_dim,
            collection_name=collection_name,
            success=True,
            message=f"Author vector {action} and stored successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating author vector: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create author vector: {str(e)}"
        )
