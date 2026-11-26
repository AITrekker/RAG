"""A local web page for asking the library questions.

Run with scripts/start-web.sh. It listens on 127.0.0.1:8080 inside WSL only; reach it
from the Mac through the SSH tunnel in the README.
"""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from . import pipeline

STATIC = Path(__file__).parent / "static"
app = FastAPI(title="rag")


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    book: str | None = None
    mode: str = Field("hybrid", pattern="^(hybrid|vector|bm25)$")
    window: int = Field(2, ge=0, le=4)
    summaries: bool = False


@app.on_event("startup")
def warm_up():
    """Load the embedding model and build the all-books BM25 index before the first question."""
    from . import search_bm25
    from .search_vector import embed
    units, _ = pipeline.units_for("r128", None)
    search_bm25.search("warm up", units)
    embed(["warm up"])


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


@app.get("/api/books")
def books():
    return pipeline.books()


@app.post("/api/ask")
def ask(req: Ask):
    if req.book and req.book not in {b["slug"] for b in pipeline.books()}:
        raise HTTPException(400, f"unknown book {req.book}")
    try:
        return pipeline.run(req.question, req.book or None, req.mode, req.window, req.summaries)
    except OSError as e:  # vLLM down or unreachable
        raise HTTPException(503, f"generator unavailable: {e}. Start it with scripts/start-vllm.sh")
