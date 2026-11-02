"""Tunable retrieval constants.

These are code constants, not environment variables: changing the model or
dimension requires a migration and re-embedding every document.
"""

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
EMBEDDING_BATCH_SIZE = 16
EMBEDDING_TIMEOUT_SECONDS = 30.0
EMBEDDING_MAX_ATTEMPTS = 3

CHUNK_TARGET_CHARS = 800
CHUNK_OVERLAP_CHARS = 120
MIN_CHUNK_CHARS = 120

MAX_QUERY_CHARS = 2000
DEFAULT_TOP_K = 5
MAX_TOP_K = 20
