"""baseline: схема УПО (35 таблиц), соответствующая итоговой легаси-схеме.

Для гарантии соответствия baseline создаёт таблицы из metadata ORM-моделей.
"""

from alembic import op

import app.db.models  # noqa: F401
from app.db.base import Base

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    Base.metadata.create_all(bind=op.get_bind())


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
