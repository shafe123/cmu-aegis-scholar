"""
Shared schema definitions for the Aegis Scholar vector database.

Centralizing field definitions here ensures the test suite always validates
against the same schema the production service uses. Import from this module
rather than redefining fields inline.
"""

from pymilvus import DataType, FieldSchema

COLLECTION_NAME = "aegis_vectors"
EMBEDDING_DIM = 384

AUTHOR_FIELDS = [
    FieldSchema(name="id", dtype=DataType.VARCHAR, is_primary=True, max_length=255),
    FieldSchema(name="author_id", dtype=DataType.VARCHAR, max_length=255),
    FieldSchema(name="author_name", dtype=DataType.VARCHAR, max_length=500),
    FieldSchema(name="embedding", dtype=DataType.FLOAT_VECTOR, dim=EMBEDDING_DIM),
    FieldSchema(name="num_abstracts", dtype=DataType.INT64),
    FieldSchema(name="citation_count", dtype=DataType.INT64, default_value=0),
]

INDEX_PARAMS = {
    "metric_type": "L2",
    "index_type": "IVF_FLAT",
    "params": {"nlist": 128},
}
