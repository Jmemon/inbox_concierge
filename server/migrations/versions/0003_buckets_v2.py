"""buckets v2: is_deleted + structured default criteria

Revision ID: 0003_buckets_v2
Revises: 0002_inbox
Create Date: 2026-05-01 12:00:00.000000

Migration plan from specs/05_01_2026-project_minimum-buckets.md:
 1. add is_deleted to buckets (default false, not null)
 2. insert four new uuid-hex rows for the default buckets with structured criteria
 3. UPDATE inbox_threads.bucket_id from old default-* ids to the new uuids
 4. DELETE old default-* rows
 5. downgrade reverses (insert old rows back, repoint, delete new uuids, drop column)
"""

import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.llm.default_criteria import DEFAULT_BUCKETS


revision: str = "0003_buckets_v2"
down_revision: Union[str, Sequence[str], None] = "0002_inbox"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Old → new id mapping is fixed at migration time so up/down can use the same
# pairs. Names match the seed in 0002_inbox.
_OLD_DEFAULT_NAMES = {
    "default-important": "Important",
    "default-can-wait": "Can wait",
    "default-auto-archive": "Auto-archive",
    "default-newsletter": "Newsletter",
}


def _new_uuid_for(name: str) -> str:
    """Deterministic UUID per bucket name so up→down→up round-trips don't
    diverge. Uses uuid5 in a custom namespace so the value is stable across
    runs but unrelated to any real namespace."""
    ns = uuid.UUID("00000000-0000-0000-0000-000000000003")  # arbitrary; tied to migration 0003
    return uuid.uuid5(ns, name).hex


def upgrade() -> None:
    bind = op.get_bind()

    # 1) is_deleted column
    op.add_column(
        "buckets",
        sa.Column("is_deleted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    # 2) Insert new rows. user_id=None = default (shared across users).
    new_rows = []
    for spec in DEFAULT_BUCKETS:
        new_rows.append(
            {
                "id": _new_uuid_for(spec["name"]),
                "user_id": None,
                "name": spec["name"],
                "criteria": spec["criteria"],
                "is_deleted": False,
            }
        )
    bucket_table = sa.table(
        "buckets",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("name", sa.String),
        sa.column("criteria", sa.Text),
        sa.column("is_deleted", sa.Boolean),
    )
    op.bulk_insert(bucket_table, new_rows)

    # 3) Repoint inbox_threads.bucket_id from old → new
    for old_id, name in _OLD_DEFAULT_NAMES.items():
        new_id = _new_uuid_for(name)
        bind.execute(
            sa.text("UPDATE inbox_threads SET bucket_id = :new WHERE bucket_id = :old"),
            {"new": new_id, "old": old_id},
        )

    # 4) Delete old default-* rows
    bind.execute(
        sa.text(
            "DELETE FROM buckets WHERE id IN ('default-important','default-can-wait',"
            "'default-auto-archive','default-newsletter')"
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    # 1) Re-insert the old default rows with the original (short, ad-hoc)
    #    criteria. We don't try to round-trip the structured criteria — this
    #    is a recovery path, not the source of truth.
    old_rows = [
        {"id": "default-important",     "user_id": None, "name": "Important",
         "criteria": "needs response soon or affects me directly"},
        {"id": "default-can-wait",      "user_id": None, "name": "Can wait",
         "criteria": "can be handled later, not urgent"},
        {"id": "default-auto-archive",  "user_id": None, "name": "Auto-archive",
         "criteria": "automated notifications i don't act on"},
        {"id": "default-newsletter",    "user_id": None, "name": "Newsletter",
         "criteria": "marketing or content subscriptions"},
    ]
    # Note: down version of the table doesn't have is_deleted yet so insert
    # without that column.
    bucket_table = sa.table(
        "buckets",
        sa.column("id", sa.String),
        sa.column("user_id", sa.String),
        sa.column("name", sa.String),
        sa.column("criteria", sa.Text),
    )
    op.bulk_insert(bucket_table, old_rows)

    # 2) Repoint inbox_threads from new uuids back to old default-* ids
    for old_id, name in _OLD_DEFAULT_NAMES.items():
        new_id = _new_uuid_for(name)
        bind.execute(
            sa.text("UPDATE inbox_threads SET bucket_id = :old WHERE bucket_id = :new"),
            {"new": new_id, "old": old_id},
        )

    # 3) Delete the new uuid rows
    new_ids = [_new_uuid_for(name) for name in _OLD_DEFAULT_NAMES.values()]
    bind.execute(
        sa.text("DELETE FROM buckets WHERE id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": new_ids},
    )

    # 4) Drop is_deleted column
    op.drop_column("buckets", "is_deleted")
