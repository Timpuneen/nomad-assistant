from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from pydantic import BaseModel
from typing import Optional
import uvicorn

from rag import RAGEngine
from startup_indexer import run as run_startup_indexer


rag = RAGEngine()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs once on startup — index any .docx files in /app/laws/
    run_startup_indexer(rag)
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


@app.get("/")
def root():
    return {"status": "ok", "message": "Insurance Law Assistant API"}


@app.get("/api/stats")
def get_stats():
    """Return number of indexed documents and chunks."""
    return rag.get_stats()


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload and index a .docx file."""
    if not file.filename.endswith(".docx"):
        raise HTTPException(status_code=400, detail="Only .docx files are supported")

    contents = await file.read()
    result = rag.ingest_docx(contents, file.filename)
    return result


@app.post("/api/chat", response_model=ChatResponse)
def chat(request: ChatRequest):
    """Ask a question about insurance law."""
    if not request.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    result = rag.query(request.question, request.session_id)
    return ChatResponse(
        answer=result["answer"],
        sources=result["sources"],
        session_id=request.session_id,
    )


@app.delete("/api/documents/{doc_name}")
def delete_document(doc_name: str):
    """Remove a document from the index."""
    result = rag.delete_document(doc_name)
    return result


@app.get("/api/documents")
def list_documents():
    """List all indexed documents."""
    return rag.list_documents()


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
