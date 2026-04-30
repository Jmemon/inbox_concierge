from fastapi import FastAPI
from app.api.auth import router as auth_router
from app.config import get_settings


settings = get_settings()
app = FastAPI(title="inbox_concierge")
app.include_router(auth_router)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.env}
