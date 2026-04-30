from fastapi import FastAPI

app = FastAPI(title="inbox_concierge")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
