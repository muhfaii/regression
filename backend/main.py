"""FastAPI application entry point."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.routers import analysis, data, export
from backend.services.session_store import cleanup_loop

app = FastAPI(title="Statistical Analysis API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(data.router)
app.include_router(analysis.router)
app.include_router(export.router)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_loop())


@app.get("/health")
async def health():
    return {"status": "ok"}
