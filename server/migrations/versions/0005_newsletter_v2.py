"""newsletter v2 criteria

Revision ID: 0005_newsletter_v2
Revises: 0004_marketing_bucket
Create Date: 2026-05-01 19:00:00.000000

Updates the default Newsletter bucket's criteria text on existing databases.

Why this is its own migration: when 0004 added the Marketing bucket we also
edited the Python NEWSLETTER constant to drop "marketing" overlap and swap
one nearmiss block. But the classifier reads bucket criteria from the
`buckets` table, not from the Python module — so existing prod DBs were
still running the old Newsletter prompt and the boundary teaching was lost.

This migration UPDATEs the Newsletter row with the v2 text. Both the v1 and
v2 strings are inlined here (not imported from default_criteria) so the
migration is genuinely immutable: a future edit to NEWSLETTER will require
a fresh migration with its own inline text, not silent retroactive change.

Downgrade restores v1 inline.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_newsletter_v2"
down_revision: Union[str, Sequence[str], None] = "0004_marketing_bucket"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Frozen v1 text — what 0003 originally seeded into the Newsletter row.
_NEWSLETTER_V1 = """\
Opted-in marketing, content subscriptions, and bulk-sends from publications
or vendors. Distinct from transactional automated mail (which is
Auto-archive) — these are read-as-content rather than processed-as-events.

Example cases:
<positive>
From: newsletter@stratechery.com
To: me
Subject: The end of the long tail

This week: how aggregation theory plays out in the AI era…
</positive>
<positive>
From: digest@substack.com
To: me
Subject: Your weekly digest from 5 publications

Here's what's new from the writers you follow.
</positive>
<nearmiss>
From: receipts@vendor.com
To: me
Subject: Your invoice for October

Invoice #INV-2026-10-1234 is attached. Total due: $42.
</nearmiss>
<nearmiss>
From: founder@startup.com
To: me
Subject: Quick favor — feedback on our beta?

Hey John, would love your take on what we shipped this week. 5-min
question if you have a sec.
</nearmiss>
"""


# Frozen v2 text — drops the "marketing" overlap and swaps the founder
# nearmiss for a marketing-style example so the LLM has an explicit boundary
# vs. the new Marketing bucket.
_NEWSLETTER_V2 = """\
Opted-in content subscriptions and digests from publications or writers.
Distinct from Marketing (promotional pushes from vendors) and Auto-archive
(transactional mail like receipts) — these are read-as-content rather than
processed-as-events.

Example cases:
<positive>
From: newsletter@stratechery.com
To: me
Subject: The end of the long tail

This week: how aggregation theory plays out in the AI era…
</positive>
<positive>
From: digest@substack.com
To: me
Subject: Your weekly digest from 5 publications

Here's what's new from the writers you follow.
</positive>
<nearmiss>
From: receipts@vendor.com
To: me
Subject: Your invoice for October

Invoice #INV-2026-10-1234 is attached. Total due: $42.
</nearmiss>
<nearmiss>
From: marketing@vendor.com
To: me
Subject: 48 hours left — 30% off everything

Our biggest sale of the season ends Sunday. Save 30% sitewide with code
SAVE30 at checkout.
</nearmiss>
"""


def upgrade() -> None:
    bind = op.get_bind()
    # Idempotent: WHERE name='Newsletter' AND user_id IS NULL targets the
    # default row (user_id=NULL means default; user-created customs all have
    # a user_id). Re-running is harmless.
    bind.execute(
        sa.text(
            "UPDATE buckets SET criteria = :v2 "
            "WHERE name = 'Newsletter' AND user_id IS NULL"
        ),
        {"v2": _NEWSLETTER_V2},
    )


def downgrade() -> None:
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE buckets SET criteria = :v1 "
            "WHERE name = 'Newsletter' AND user_id IS NULL"
        ),
        {"v1": _NEWSLETTER_V1},
    )
