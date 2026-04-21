"""Integration tests for Vector DB API using a live Milvus container."""

import numpy as np
import pytest
from pymilvus import Collection, CollectionSchema, DataType, FieldSchema, connections, utility
from testcontainers.milvus import MilvusContainer

# ---------------------------------------------------------------------------
# Milvus container fixture — starts once for all tests in this module
# ---------------------------------------------------------------------------

MILVUS_IMAGE = "milvusdb/milvus:v2.4.4"
TEST_COLLECTION = "test_aegis_vectors"
EMBEDDING_DIM = 384


@pytest.fixture(scope="module")
def milvus_container():
    """Start a real Milvus container for integration testing."""
    with MilvusContainer(image=MILVUS_IMAGE) as container:
        yield container


@pytest.fixture(scope="module")
def milvus_connection(milvus_container):
    """Connect pymilvus to the test container."""
    host = milvus_container.get_container_host_ip()
    port = milvus_container.get_exposed_port(milvus_container.port)
    connections.connect(alias="test", host=host, port=port)
    yield
    connections.disconnect("test")


@pytest.fixture(scope="module")
def test_collection(milvus_connection):
    """Create a test collection with the standard Aegis Scholar schema."""
    if utility.has_collection(TEST_COLLECTION, using="test"):
        utility.drop_collection(TEST_COLLECTION, using="test")

    fields = [
        FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=255),
        FieldSchema(name="author_id", dtype=DataType.VARCHAR, max_length=255),
        FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=500),
        FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
        FieldSchema(name="num_abstracts", dtype=DataType.INT64),
        FieldSchema(name="citation_count", dtype=DataType.INT64, default_value=0),
    ]
    schema = CollectionSchema(fields=fields, description="Test author embeddings")
    collection = Collection(name=TEST_COLLECTION, schema=schema, using="test")

    index_params = {
        "metric_type": "L2",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()
    yield collection
    utility.drop_collection(TEST_COLLECTION, using="test")


@pytest.fixture(autouse=True)
def clean_collection(test_collection):
    """Delete all entities before each test for a clean slate."""
    test_collection.delete(expr="id != 'sentinel'")
    test_collection.flush()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_embedding(seed: int = 0) -> list[float]:
    """Generate a deterministic normalized embedding vector for testing."""
    rng = np.random.default_rng(seed)
    vec = rng.random(EMBEDDING_DIM).astype(np.float32)
    vec = vec / np.linalg.norm(vec)
    return vec.tolist()


def insert_author(collection: Collection, author_id: str, name: str, seed: int = 0) -> None:
    """Insert a single author embedding into the collection."""
    entity_data = [
        [author_id],        # id
        [author_id],        # author_id
        [name],             # author_name
        [make_embedding(seed)],  # embedding
        [5],                # num_abstracts
        [100],              # citation_count
    ]
    collection.upsert(entity_data)
    collection.flush()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.integration
@pytest.mark.requires_docker
def test_milvus_container_is_healthy(milvus_connection):
    """Verify the Milvus container starts and accepts connections."""
    collections = utility.list_collections(using="test")
    assert isinstance(collections, list)


@pytest.mark.integration
@pytest.mark.requires_docker
def test_collection_created(test_collection):
    """Test collection should exist with the correct schema."""
    assert utility.has_collection(TEST_COLLECTION, using="test")


@pytest.mark.integration
@pytest.mark.requires_docker
def test_author_embedding_inserted(test_collection, sample_authors):
    """Author embedding should be insertable and queryable."""
    author = sample_authors[0]
    insert_author(test_collection, author["id"], author["name"], seed=1)

    results = test_collection.query(
        expr=f'author_id == "{author["id"]}"',
        output_fields=["author_name"],
    )
    assert len(results) == 1
    assert results[0]["author_name"] == author["name"]


@pytest.mark.integration
@pytest.mark.requires_docker
def test_author_embedding_upsert_is_idempotent(test_collection, sample_authors):
    """Upserting the same author twice should not create duplicate entries."""
    author = sample_authors[0]
    insert_author(test_collection, author["id"], author["name"], seed=1)
    insert_author(test_collection, author["id"], author["name"], seed=1)

    results = test_collection.query(
        expr=f'author_id == "{author["id"]}"',
        output_fields=["author_id"],
    )
    assert len(results) == 1


@pytest.mark.integration
@pytest.mark.requires_docker
def test_vector_search_returns_results(test_collection, sample_authors):
    """Vector search should return authors ranked by similarity."""
    for i, author in enumerate(sample_authors):
        insert_author(test_collection, author["id"], author["name"], seed=i)

    query_vector = make_embedding(seed=0)
    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

    results = test_collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=search_params,
        limit=10,
        output_fields=["author_id", "author_name"],
    )

    assert len(results) > 0
    assert len(results[0]) == len(sample_authors)


@pytest.mark.integration
@pytest.mark.requires_docker
def test_vector_search_ranking(test_collection, sample_authors):
    """Author with identical embedding to query should rank first."""
    query_vector = make_embedding(seed=42)

    for i, author in enumerate(sample_authors):
        insert_author(test_collection, author["id"], author["name"], seed=i + 10)

    target = sample_authors[0]
    entity_data = [
        [target["id"]],
        [target["id"]],
        [target["name"]],
        [query_vector],
        [5],
        [100],
    ]
    test_collection.upsert(entity_data)
    test_collection.flush()

    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}
    results = test_collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=search_params,
        limit=10,
        output_fields=["author_id"],
    )

    top_result = results[0][0]
    assert top_result.entity.get("author_id") == target["id"]
    assert top_result.distance < 0.001


@pytest.mark.integration
@pytest.mark.requires_docker
def test_embedding_dimension_enforced(test_collection, sample_authors):
    """Inserting a vector with wrong dimensions should raise an error."""
    author = sample_authors[0]
    wrong_dim_embedding = [0.1] * 128  # wrong — should be 384

    entity_data = [
        [author["id"]],
        [author["id"]],
        [author["name"]],
        [wrong_dim_embedding],
        [5],
        [100],
    ]

    with pytest.raises(Exception):
        test_collection.upsert(entity_data)
        test_collection.flush()


@pytest.mark.integration
@pytest.mark.requires_docker
def test_empty_collection_search(test_collection):
    """Searching an empty collection should return empty results."""
    query_vector = make_embedding(seed=0)
    search_params = {"metric_type": "L2", "params": {"nprobe": 10}}

    results = test_collection.search(
        data=[query_vector],
        anns_field="embedding",
        param=search_params,
        limit=10,
        output_fields=["author_id"],
    )

    assert len(results[0]) == 0
