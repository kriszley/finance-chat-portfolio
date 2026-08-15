"""FastAPI entry point. PYTHONPATH setup, WAL mode init, CORS, routes."""

import sys
from pathlib import Path

# Add finance-automation to PYTHONPATH for pipeline imports
# Docker: mounted at /finance-automation; Local dev: sibling directory
_fa_docker = Path("/finance-automation")
_fa_local = Path(__file__).parent.parent / "finance-automation"
FINANCE_AUTOMATION_ROOT = _fa_docker if _fa_docker.exists() else _fa_local
sys.path.insert(0, str(FINANCE_AUTOMATION_ROOT))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.connection import init_db
from routers import tools, upload, data, conversations


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Finance Chat API",
    description="Backend for the Finance Chat Agent",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — dev-only convenience for direct API testing.
# In production, browser only talks to Next.js (proxy pattern).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tools.router)
app.include_router(upload.router)
app.include_router(data.router)
app.include_router(conversations.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
