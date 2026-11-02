"""Database type for embedding vectors.

Postgres stores a real ``vector(768)``; SQLite (tests) stores the same list as
JSON so the in-memory suite needs no extensions or containers.
"""

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON

from app.modules.retrieval.constants import EMBEDDING_DIM

Vector768 = Vector(EMBEDDING_DIM).with_variant(JSON(), "sqlite")
