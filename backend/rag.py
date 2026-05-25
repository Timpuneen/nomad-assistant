import os
import io
import re
import json
from pathlib import Path
from collections import defaultdict

import chromadb
from chromadb.config import Settings
from docx import Document
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_PATH    = os.getenv("CHROMA_PATH", "./chroma_db")
LAWS_DIR       = Path(os.getenv("LAWS_DIR", "/app/laws"))

# File that stores enabled/disabled state for law documents
DOC_STATE_FILE = LAWS_DIR / ".doc_state.json"

EMBED_MODEL      = "text-embedding-3-small"
CHAT_MODEL       = "gpt-4o-mini"
COLLECTION_NAME  = "insurance_laws"
CHUNK_SIZE       = 800
CHUNK_OVERLAP    = 150
TOP_K            = 5

SOURCE_LAW    = "law"    # pre-loaded from laws/ folder
SOURCE_UPLOAD = "upload" # uploaded via UI

SYSTEM_PROMPT = """Ты — юридический ИИ-ассистент страховой компании Казахстана.
Ты консультируешь сотрудников по вопросам страхового законодательства Республики Казахстан.

Правила:
1. Отвечай ТОЛЬКО на основе предоставленных фрагментов законов. Не придумывай информацию.
2. Если в предоставленных фрагментах нет ответа — честно скажи об этом.
3. Всегда указывай источник: название закона и номер статьи.
4. Отвечай на том же языке, на котором задан вопрос (русский или казахский).
5. Давай точные, структурированные ответы. Используй нумерацию и списки где уместно.
6. Не интерпретируй законы расширительно — цитируй или близко пересказывай текст.

Формат ответа:
- Краткий ответ по существу
- Правовое обоснование со ссылкой на статью
- Если есть несколько норм — перечисли каждую отдельно
"""


# ------------------------------------------------------------------ #
#  Doc-state helpers  (enabled/disabled stored in JSON, not ChromaDB)
# ------------------------------------------------------------------ #

def _load_doc_state() -> dict:
    """Returns {filename: bool} — True means enabled."""
    if DOC_STATE_FILE.exists():
        try:
            return json.loads(DOC_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_doc_state(state: dict):
    DOC_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    DOC_STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


class RAGEngine:
    def __init__(self):
        self.client = OpenAI(api_key=OPENAI_API_KEY)
        self.chroma = chromadb.PersistentClient(
            path=CHROMA_PATH,
            settings=Settings(anonymized_telemetry=False),
        )
        self.collection = self.chroma.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        self.sessions: dict[str, list] = defaultdict(list)

    # ------------------------------------------------------------------ #
    #  INGESTION
    # ------------------------------------------------------------------ #

    def ingest_docx(self, file_bytes: bytes, filename: str,
                    source_type: str = SOURCE_UPLOAD) -> dict:
        if source_type == SOURCE_UPLOAD and self.has_source(filename, SOURCE_LAW):
            return {
                "status": "error",
                "filename": filename,
                "message": "This document is preloaded and cannot be uploaded as a user document",
            }

        doc   = Document(io.BytesIO(file_bytes))
        text  = self._extract_structured_text(doc)
        chunks = self._smart_chunk(text, filename, source_type)

        if not chunks:
            return {"status": "error", "message": "No text found in document"}

        texts      = [c["text"]     for c in chunks]
        embeddings = self._embed_batch(texts)
        ids        = [c["id"]       for c in chunks]
        metadatas  = [c["metadata"] for c in chunks]

        if source_type == SOURCE_LAW:
            self._delete_by_source(filename)
        else:
            self._delete_by_source(filename, source_type=source_type)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        # Law documents are enabled by default when first indexed
        if source_type == SOURCE_LAW:
            state = _load_doc_state()
            if filename not in state:
                state[filename] = True
                _save_doc_state(state)

        return {"status": "ok", "filename": filename, "chunks_indexed": len(chunks)}

    def _extract_structured_text(self, doc: Document) -> str:
        return "\n".join(p.text.strip() for p in doc.paragraphs if p.text.strip())

    def _smart_chunk(self, text: str, filename: str,
                     source_type: str = SOURCE_UPLOAD) -> list[dict]:
        chunks  = []
        pattern = re.compile(
            r"(Статья\s+\d+[\.\-]?\d*\..*?)(?=Статья\s+\d+|$)", re.DOTALL
        )
        articles = pattern.findall(text)

        if articles:
            for art in articles:
                art = art.strip()
                if not art:
                    continue
                m          = re.match(r"Статья\s+([\d\.\-]+)", art)
                article_num = m.group(1) if m else "?"
                for i, sub in enumerate(self._split_by_size(art, CHUNK_SIZE, CHUNK_OVERLAP)):
                    chunks.append({
                        "id":   f"{filename}::art{article_num}::part{i}",
                        "text": sub,
                        "metadata": {
                            "source":      filename,
                            "source_type": source_type,
                            "article":     article_num,
                            "part":        i,
                        },
                    })
        else:
            for i, sub in enumerate(self._split_by_size(text, CHUNK_SIZE, CHUNK_OVERLAP)):
                chunks.append({
                    "id":   f"{filename}::chunk{i}",
                    "text": sub,
                    "metadata": {
                        "source":      filename,
                        "source_type": source_type,
                        "article":     "—",
                        "part":        i,
                    },
                })
        return chunks

    def _split_by_size(self, text: str, size: int, overlap: int) -> list[str]:
        chunks, start = [], 0
        while start < len(text):
            chunks.append(text[start:start + size].strip())
            start += size - overlap
        return [c for c in chunks if c]

    # ------------------------------------------------------------------ #
    #  QUERYING
    # ------------------------------------------------------------------ #

    def query(self, question: str, session_id: str = "default") -> dict:
        total = self.collection.count()
        if total == 0:
            return {
                "answer": "База знаний пуста. Загрузите документы с законами.",
                "sources": [],
            }

        # Build list of disabled law sources to exclude from search
        state    = _load_doc_state()
        disabled = [name for name, enabled in state.items() if not enabled]

        q_embedding = self._embed_single(question)
        results = self.collection.query(
            query_embeddings=[q_embedding],
            n_results=min(TOP_K, total),
            include=["documents", "metadatas", "distances"],
        )

        docs      = results["documents"][0]
        metas     = results["metadatas"][0]
        distances = results["distances"][0]

        # Filter: relevance threshold + skip disabled law documents
        threshold = 0.6
        filtered  = [
            (d, m, dist)
            for d, m, dist in zip(docs, metas, distances)
            if dist < threshold and m.get("source") not in disabled
        ]

        if not filtered:
            return {
                "answer": (
                    "В загруженных документах не найдено релевантной информации "
                    "по вашему вопросу. Пожалуйста, убедитесь, что соответствующие "
                    "законы загружены и активны."
                ),
                "sources": [],
            }

        docs_f, metas_f, _ = zip(*filtered)

        context = "\n\n---\n\n".join(
            f"[Источник: {m.get('source','—')}, Статья {m.get('article','—')}]\n{d}"
            for d, m in zip(docs_f, metas_f)
        )

        history  = self.sessions[session_id][-6:]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({
            "role":    "user",
            "content": f"Контекст из законов:\n\n{context}\n\nВопрос: {question}",
        })

        response = self.client.chat.completions.create(
            model=CHAT_MODEL, messages=messages, temperature=0.1, max_tokens=1500
        )
        answer = response.choices[0].message.content

        self.sessions[session_id].append({"role": "user",      "content": question})
        self.sessions[session_id].append({"role": "assistant", "content": answer})

        seen, sources = set(), []
        for meta in metas_f:
            key = (meta.get("source", ""), meta.get("article", ""))
            if key not in seen:
                seen.add(key)
                sources.append({
                    "source":  meta.get("source",  "—"),
                    "article": meta.get("article", "—"),
                })

        return {"answer": answer, "sources": sources}

    # ------------------------------------------------------------------ #
    #  EMBEDDING HELPERS
    # ------------------------------------------------------------------ #

    def _embed_single(self, text: str) -> list[float]:
        return self.client.embeddings.create(
            model=EMBED_MODEL, input=[text]
        ).data[0].embedding

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [
            item.embedding for item in
            self.client.embeddings.create(model=EMBED_MODEL, input=texts).data
        ]

    # ------------------------------------------------------------------ #
    #  DOCUMENT MANAGEMENT
    # ------------------------------------------------------------------ #

    def has_source(self, filename: str, source_type: str | None = None) -> bool:
        try:
            res = self.collection.get(where={"source": filename}, include=["metadatas"])
            if source_type is None:
                return bool(res["ids"])
            return any(
                m.get("source_type") == source_type
                for m in res.get("metadatas", [])
            )
        except Exception:
            return False

    def _delete_by_source(self, filename: str, source_type: str | None = None):
        try:
            res = self.collection.get(where={"source": filename}, include=["metadatas"])
            if not res["ids"]:
                return

            ids = res["ids"]
            if source_type is not None:
                ids = [
                    doc_id
                    for doc_id, metadata in zip(res["ids"], res.get("metadatas", []))
                    if metadata.get("source_type") == source_type
                ]

            if ids:
                self.collection.delete(ids=ids)
        except Exception:
            pass

    # --- uploads (full delete) ---

    def delete_upload(self, filename: str) -> dict:
        """Permanently delete an upload document from ChromaDB."""
        self._delete_by_source(filename, source_type=SOURCE_UPLOAD)
        return {"status": "ok", "deleted": filename}

    # --- laws (toggle enabled/disabled) ---

    def toggle_law(self, filename: str, enabled: bool) -> dict:
        """Enable or disable a law document in search (no ChromaDB change)."""
        state          = _load_doc_state()
        state[filename] = enabled
        _save_doc_state(state)
        return {"status": "ok", "filename": filename, "enabled": enabled}

    # --- listing ---

    def list_laws(self) -> list[dict]:
        """All documents with source_type='law', with their enabled state."""
        try:
            res   = self.collection.get(include=["metadatas"])
            state = _load_doc_state()
            seen  = {}
            for m in res["metadatas"]:
                if m.get("source_type") == SOURCE_LAW:
                    name = m["source"]
                    if name not in seen:
                        seen[name] = state.get(name, True)
            return [
                {"filename": name, "enabled": enabled}
                for name, enabled in sorted(seen.items())
            ]
        except Exception:
            return []

    def list_uploads(self) -> list[str]:
        """All documents with source_type='upload'."""
        try:
            res  = self.collection.get(include=["metadatas"])
            seen = set()
            for m in res["metadatas"]:
                if m.get("source_type") == SOURCE_UPLOAD:
                    seen.add(m["source"])
            return sorted(seen)
        except Exception:
            return []

    def get_stats(self) -> dict:
        laws    = self.list_laws()
        uploads = self.list_uploads()
        return {
            "total_chunks":    self.collection.count(),
            "total_laws":      len(laws),
            "total_uploads":   len(uploads),
            "laws":            laws,
            "uploads":         uploads,
        }
