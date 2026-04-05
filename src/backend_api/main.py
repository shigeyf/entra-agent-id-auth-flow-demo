from fastapi import FastAPI

from backend_api.routes.call_foundry_agent import router

app = FastAPI(title="Backend API", version="1.0.0")

# CORS is not needed until Phase 3 (SPA integration).

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
