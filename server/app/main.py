from fastapi import FastAPI
from app.config import get_settings

settings = get_settings()  # crash early if env is missing/invalid

app = FastAPI(title="inbox_concierge")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}
