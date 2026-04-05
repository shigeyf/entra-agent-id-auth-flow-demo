import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from identity_echo_api.routes.resource import router

app = FastAPI(title="Identity Echo API", version="1.0.0")

_local_origins = [
    "http://localhost:3000",
    "http://localhost:5173",
]
_spa_url = os.getenv("FRONTEND_SPA_APP_URL", "").strip().rstrip("/")
_extra_origins = [_spa_url] if _spa_url else []

app.add_middleware(
    CORSMiddleware,
    allow_origins=_local_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok"}
