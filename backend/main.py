"""
Milestone 1 - FastAPI application.

For now this only exposes a health check, which exists so the frontend can prove
it can reach the backend. The OCR endpoints arrive in a later milestone; the
extraction pipeline itself already lives in extract.py and is deliberately not
wired up here yet.

Run from this directory:
    .venv/Scripts/uvicorn main:app --reload --port 8000
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# DESIGN DECISION: routes are namespaced under /api. The Vite dev server proxies
# that one prefix to this app, so the frontend only ever calls same-origin
# relative URLs and there is no backend host hard-coded in the React code.
API_PREFIX = "/api"

# The Vite dev server's default origins. Only needed for requests that bypass the
# proxy (a browser hitting the API directly, or a future non-proxied client) -
# proxied calls arrive same-origin and never trigger CORS. Listed explicitly
# rather than "*" so the allowed set stays obvious.
DEV_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app = FastAPI(
    title="Pixcel API",
    description="OCR extraction for MapleStory screenshots.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEV_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Health(BaseModel):
    """Response model for the health check.

    Declared as a model rather than a bare dict so the shape is enforced here and
    published in the OpenAPI schema, which is what the frontend's matching
    TypeScript type is written against.
    """

    status: str
    service: str


@app.get(f"{API_PREFIX}/health", response_model=Health)
def health() -> Health:
    """Liveness probe, and the frontend's connectivity test."""
    return Health(status="ok", service="pixcel-api")
