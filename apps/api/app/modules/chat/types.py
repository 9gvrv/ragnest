"""Database type for message citations.

Postgres stores JSONB; SQLite (tests) stores the same list as JSON.
"""

from sqlalchemy import JSON
from sqlalchemy.dialects.postgresql import JSONB

CitationsJSON = JSONB().with_variant(JSON(), "sqlite")
