"""Beat schedule.

One periodic tick fires `enqueue_polls` every 30s. Beat itself does no polling
logic — it just enqueues the fan-out task.
"""

from celery.schedules import schedule


beat_schedule = {
    "enqueue-polls-every-30s": {
        "task": "app.workers.tasks.enqueue_polls",
        "schedule": schedule(run_every=30.0),
    },
}
