from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
import uvicorn

from rag import RAGEngine
from startup_indexer import run as run_startup_indexer

rag = RAGEngine()
indexing_complete = False


@asynccontextmanager
async def lifespan(app: FastAPI):
    global indexing_complete
    run_startup_indexer(rag)
    indexing_complete = True
    yield


app = FastAPI(title="Insurance Law Assistant API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatRequest(BaseModel):
    question: str
    session_id: Optional[str] = "default"


class ChatResponse(BaseModel):
    answer: str
    sources: list[dict]
    session_id: str


class ToggleRequest(BaseModel):
    enabled: bool


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok"}


@app.get("/health/ready")
def readiness():
    """Returns 200 only after startup indexing completes"""
    if not indexing_complete:
        raise HTTPException(status_code=503, detail="Indexing in progress")
    return {"status": "ready"}


@app.get("/api/stats")
def get_stats():
    return rag.get_stats()


# ── Chat ──────────────────────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")
    result = rag.query(request.question, request.session_id)
    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        session_id=request.session_id,
    )


# ── Uploads (can be fully deleted) ───────────────────────────────────────────

@app.post("/api/uploads")
async def upload_document(file: UploadFile = File(...)):
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")
    contents = await file.read()
    result   = rag.ingest_docx(contents, file.filename, source_type="upload")
    return result


@app.get("/api/uploads")
def list_uploads():
    return {"uploads": rag.list_uploads()}


@app.delete("/api/uploads/{filename}")
def delete_upload(filename: str):
    return rag.delete_upload(filename)


# ── Laws (toggle only) ────────────────────────────────────────────────────────

@app.get("/api/laws")
def list_laws():
    return {"laws": rag.list_laws()}


@app.patch("/api/laws/{filename}/toggle")
def toggle_law(filename: str, body: ToggleRequest):
    return rag.toggle_law(filename, body.enabled)
