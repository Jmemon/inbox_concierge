"""marketing default bucket

Revision ID: 0004_marketing_bucket
Revises: 0003_buckets_v2
Create Date: 2026-05-01 18:00:00.000000

Adds a fifth default bucket "Marketing" for unsolicited promotional emails,
distinct from Newsletter (opted-in content) and Auto-archive (transactional).
Uses the same deterministic uuid5 pattern as 0003 with a fresh namespace so
the row's id round-trips cleanly across down→up cycles.

Downgrade NULLs out any inbox_threads.bucket_id that points at the Marketing
row before deleting the bucket — InboxThread.bucket_id has a FK to buckets.id
(same constraint that 0003's downgrade has to navigate).
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.llm.default_criteria import MARKETING


revision: str = "0004_marketing_bucket"
down_revision: Union[str, Sequence[str], None] = "0003_buckets_v2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Fresh namespace per migration so default-bucket ids stay partitioned by
# the migration that introduced them. Same construction pattern as 0003.
_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000004")
_MARKETING_ID = uuid.uuid5(_NAMESPACE, "Marketing").hex


def upgrade() -> None:
    bucket_table = sa.table(
        "buckets",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("name", sa.String),
        sa.column("criteria", sa.Text),
        sa.column("is_deleted", sa.Boolean),
    )
    op.bulk_insert(
        bucket_table,
        [
            {
                "id": _MARKETING_ID,
                "user_id": None,
                "name": "Marketing",
                "criteria": MARKETING,
                "is_deleted": False,
            }
        ],
    )


def downgrade() -> None:
    bind = op.get_bind()

    # Threads classified into Marketing fall back to NULL (renders as
    # unclassified client-side). Must precede the DELETE to satisfy the
    # inbox_threads.bucket_id → buckets.id foreign key.
    bind.execute(
        sa.text("UPDATE inbox_threads SET bucket_id = NULL WHERE bucket_id = :id"),
        {"id": _MARKETING_ID},
    )
    bind.execute(
        sa.text("DELETE FROM buckets WHERE id = :id"),
        {"id": _MARKETING_ID},
    )
