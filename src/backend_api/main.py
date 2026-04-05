from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend_api.routes.call_foundry_agent import router

app = FastAPI(title="Backend API", version="1.0.0")

# Phase 3: Allow SPA origins (local dev + deployed Static Web Apps)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:4173",
    ],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
