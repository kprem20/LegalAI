from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routes import router
from backend.config.settings import settings

logger = logging.getLogger("nyayasearch")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Pre-warm embedding model and ChromaDB store on startup
    try:
        from ai.embeddings.encoder import get_embedding_model
        from database.chroma.store import get_chroma

        get_embedding_model()
        get_chroma()
    except Exception as exc:
        logger.warning("Pre-warm warning: %s", exc)
    yield


app = FastAPI(
    title="NyayaSearch AI",
    description="AI-assisted retrieval of Indian Supreme Court judgments.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


def run() -> None:
    import uvicorn

    uvicorn.run(
        "backend.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=False,
    )


if __name__ == "__main__":
    run()
