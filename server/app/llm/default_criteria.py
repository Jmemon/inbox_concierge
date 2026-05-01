"""Structured criteria for the five default buckets.

Lives here (not inside the migration file) so the format can be unit-tested
and re-used. Each value is the full text of the bucket's `criteria` column —
description paragraph + tagged <positive>/<nearmiss> example blocks — exactly
the shape the classifier prompt consumes. Custom buckets created by users via
POST /api/buckets follow the same shape (see formulate_criteria in bucket_repo)
so the classifier sees one format regardless of source.
"""

IMPORTANT = """\
Threads where I'm a direct recipient and the other participants are
individuals or a company contacting me (not marketing) and I'm required to
act or respond.

Example cases:
<positive>
From: colleague@company.com
To: me
Subject: sprint meeting time

What time should we have the sprint meeting tomorrow?
</positive>
<positive>
From: counsel@lawfirm.com
To: me
Subject: Please review and sign — engagement letter

Attached is the engagement letter for our work together. Please review and
return signed by Friday.
</positive>
<nearmiss>
From: calendar-noreply@google.com
To: team-list@company.com
Subject: Weekly sync — 9 AM

You've been added as an optional attendee.
</nearmiss>
<nearmiss>
From: marketing@vendor.com
To: me
Subject: John, ready to upgrade?

Hi John, based on your usage we think you'd benefit from upgrading to Pro.
</nearmiss>
"""

CAN_WAIT = """\
Threads where I'm a recipient and may eventually want to read or respond,
but it's not urgent and can be batched. Internal announcements, FYIs,
non-blocking discussions.

Example cases:
<positive>
From: people-ops@company.com
To: all-staff@company.com
Subject: Reminder — open enrollment closes November 15

Open enrollment for benefits closes in two weeks. Submit your elections in
Workday.
</positive>
<positive>
From: teammate@company.com
To: project-channel@company.com
Subject: Re: design doc for the new dashboard

Sharing a draft for feedback whenever folks have a chance — no rush.
</positive>
<nearmiss>
From: colleague@company.com
To: me
Subject: Can you review this PR before EOD?

Could use eyes on this before I merge.
</nearmiss>
<nearmiss>
From: notifications@github.com
To: me
Subject: [repo] CI failure on main

Build failed on commit abc1234.
</nearmiss>
"""

AUTO_ARCHIVE = """\
Automated, transactional, or system-generated notifications I don't need to
read or act on individually. Receipts, shipping updates, build
notifications, status pings.

Example cases:
<positive>
From: shipment-tracking@amazon.com
To: me
Subject: Your package has shipped

Your order #123-456 has shipped and will arrive Tuesday.
</positive>
<positive>
From: builds@ci.company.com
To: me
Subject: Build #4521 succeeded

main: build passed in 4m32s.
</positive>
<nearmiss>
From: security@bank.com
To: me
Subject: Unusual sign-in attempt detected

We noticed a sign-in from a new device. If this wasn't you, please review.
</nearmiss>
<nearmiss>
From: status@datadog.com
To: me
Subject: P1 incident — production API down

Datadog detected a P1 incident affecting the prod API.
</nearmiss>
"""

NEWSLETTER = """\
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

MARKETING = """\
Unsolicited or low-engagement promotional emails from vendors and
companies — sales pitches, upgrade nudges, drip campaigns, "one-time
offers" mass-sent to everyone on the list. Distinct from Newsletter
(opted-in content you read for substance) and Auto-archive (transactional
like receipts and build alerts).

Example cases:
<positive>
From: marketing@vendor.com
To: me
Subject: John, ready to upgrade to Pro?

Hi John, based on your usage we think you'd benefit from Pro features
like advanced analytics. Click here to upgrade.
</positive>
<positive>
From: deals@retailer.com
To: me
Subject: 48 hours left — 30% off everything

Our biggest sale of the season ends Sunday. Save 30% sitewide with code
SAVE30 at checkout.
</positive>
<nearmiss>
From: digest@substack.com
To: me
Subject: Your weekly digest from 5 publications

Here's what's new from the writers you follow.
</nearmiss>
<nearmiss>
From: shipment-tracking@amazon.com
To: me
Subject: Your package has shipped

Your order #123-456 has shipped and will arrive Tuesday.
</nearmiss>
"""

# Frozen seed list for migration 0003. Do NOT mutate — adding a new default
# bucket goes into a fresh migration (e.g. 0004 added Marketing). Migrations
# are immutable historical statements; if 0003 imported the live
# DEFAULT_BUCKETS list, growing the registry would retroactively change 0003's
# seed payload on fresh databases and collide with later per-bucket migrations.
INITIAL_DEFAULT_BUCKETS: list[dict] = [
    {"name": "Important",    "criteria": IMPORTANT},
    {"name": "Can wait",     "criteria": CAN_WAIT},
    {"name": "Auto-archive", "criteria": AUTO_ARCHIVE},
    {"name": "Newsletter",   "criteria": NEWSLETTER},
]

# Live registry of all default buckets across all migrations. Append-only as
# new migrations land. Used by tests + any runtime code that wants to
# introspect "what defaults exist in the system right now."
DEFAULT_BUCKETS: list[dict] = INITIAL_DEFAULT_BUCKETS + [
    {"name": "Marketing", "criteria": MARKETING},
]
