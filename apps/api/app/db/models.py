"""Import every SQLAlchemy model so ``Base.metadata`` is complete.

Alembic autogenerate and the test harness import this module. Feature code
should import models from their own module directly.
"""

from app.modules.users.models import User  # noqa: F401
