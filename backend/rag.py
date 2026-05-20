import os
import io
import re
from typing import Optional
from collections import defaultdict

import chromadb
from chromadb.config import Settings
from docx import Document
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
CHROMA_PATH = os.getenv("CHROMA_PATH", "./chroma_db")

EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4o-mini"
COLLECTION_NAME = "insurance_laws"
CHUNK_SIZE = 800       # chars per chunk
CHUNK_OVERLAP = 150    # overlap between chunks
TOP_K = 5              # how many chunks to retrieve

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
        # session memory: session_id -> list of {role, content}
        self.sessions: dict[str, list] = defaultdict(list)

    # ------------------------------------------------------------------ #
    #  INGESTION
    # ------------------------------------------------------------------ #

    def ingest_docx(self, file_bytes: bytes, filename: str) -> dict:
        """Parse a .docx file, chunk it, embed, and store in ChromaDB."""
        doc = Document(io.BytesIO(file_bytes))
        full_text = self._extract_structured_text(doc)
        chunks = self._smart_chunk(full_text, filename)

        if not chunks:
            return {"status": "error", "message": "No text found in document"}

        # Embed all chunks
        texts = [c["text"] for c in chunks]
        embeddings = self._embed_batch(texts)

        ids = [c["id"] for c in chunks]
        metadatas = [c["metadata"] for c in chunks]

        # Delete existing chunks for this file before re-indexing
        self._delete_by_source(filename)

        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
        )

        return {
            "status": "ok",
            "filename": filename,
            "chunks_indexed": len(chunks),
        }

    def _extract_structured_text(self, doc: Document) -> str:
        """Extract text preserving paragraph structure."""
        lines = []
        for para in doc.paragraphs:
            text = para.text.strip()
            if text:
                lines.append(text)
        return "\n".join(lines)

    def _smart_chunk(self, text: str, filename: str) -> list[dict]:
        """
        Split text into chunks by article boundaries first,
        then by size if an article is too long.
        Preserves article metadata for citation.
        """
        chunks = []
        # Try to split on Статья / Article boundaries
        article_pattern = re.compile(
            r"(Статья\s+\d+[\.\-]?\d*\..*?)(?=Статья\s+\d+|$)",
            re.DOTALL,
        )
        articles = article_pattern.findall(text)

        if articles:
            for art in articles:
                art = art.strip()
                if not art:
                    continue
                # Extract article number for metadata
                num_match = re.match(r"Статья\s+([\d\.\-]+)", art)
                article_num = num_match.group(1) if num_match else "?"

                # Sub-chunk if article text is too long
                sub_chunks = self._split_by_size(art, CHUNK_SIZE, CHUNK_OVERLAP)
                for i, sub in enumerate(sub_chunks):
                    chunk_id = f"{filename}::art{article_num}::part{i}"
                    chunks.append({
                        "id": chunk_id,
                        "text": sub,
                        "metadata": {
                            "source": filename,
                            "article": article_num,
                            "part": i,
                        },
                    })
        else:
            # Fallback: plain size-based chunking
            sub_chunks = self._split_by_size(text, CHUNK_SIZE, CHUNK_OVERLAP)
            for i, sub in enumerate(sub_chunks):
                chunk_id = f"{filename}::chunk{i}"
                chunks.append({
                    "id": chunk_id,
                    "text": sub,
                    "metadata": {
                        "source": filename,
                        "article": "—",
                        "part": i,
                    },
                })

        return chunks

    def _split_by_size(self, text: str, size: int, overlap: int) -> list[str]:
        """Split text into overlapping chunks of `size` chars."""
        chunks = []
        start = 0
        while start < len(text):
            end = start + size
            chunks.append(text[start:end].strip())
            start += size - overlap
        return [c for c in chunks if c]

    # ------------------------------------------------------------------ #
    #  QUERYING
    # ------------------------------------------------------------------ #

    def query(self, question: str, session_id: str = "default") -> dict:
        """Retrieve relevant chunks and generate an answer."""
        # 1. Embed the question
        q_embedding = self._embed_single(question)

        # 2. Retrieve top-k chunks from ChromaDB
        results = self.collection.query(
            query_embeddings=[q_embedding],
            n_results=min(TOP_K, self.collection.count() or 1),
            include=["documents", "metadatas", "distances"],
        )

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        # 3. Filter low-relevance chunks (cosine distance > 0.6 means low similarity)
        threshold = 0.6
        filtered = [
            (d, m, dist)
            for d, m, dist in zip(docs, metas, distances)
            if dist < threshold
        ]

        if not filtered:
            return {
                "answer": (
                    "В загруженных документах не найдено релевантной информации "
                    "по вашему вопросу. Пожалуйста, убедитесь, что соответствующие "
                    "законы загружены в систему."
                ),
                "sources": [],
            }

        docs_f, metas_f, _ = zip(*filtered)

        # 4. Build context string
        context_parts = []
        for doc, meta in zip(docs_f, metas_f):
            source = meta.get("source", "—")
            article = meta.get("article", "—")
            context_parts.append(f"[Источник: {source}, Статья {article}]\n{doc}")
        context = "\n\n---\n\n".join(context_parts)

        # 5. Build conversation history (last 6 turns)
        history = self.sessions[session_id][-6:]
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages.extend(history)
        messages.append({
            "role": "user",
            "content": f"Контекст из законов:\n\n{context}\n\nВопрос: {question}",
        })

        # 6. Call OpenAI
        response = self.client.chat.completions.create(
            model=CHAT_MODEL,
            messages=messages,
            temperature=0.1,  # low temperature for legal accuracy
            max_tokens=1500,
        )
        answer = response.choices[0].message.content

        # 7. Save to session history
        self.sessions[session_id].append({"role": "user", "content": question})
        self.sessions[session_id].append({"role": "assistant", "content": answer})

        # 8. Deduplicate sources
        seen = set()
        sources = []
        for meta in metas_f:
            key = (meta.get("source", ""), meta.get("article", ""))
            if key not in seen:
                seen.add(key)
                sources.append({
                    "source": meta.get("source", "—"),
                    "article": meta.get("article", "—"),
                })

        return {"answer": answer, "sources": sources}

    # ------------------------------------------------------------------ #
    #  EMBEDDING HELPERS
    # ------------------------------------------------------------------ #

    def _embed_single(self, text: str) -> list[float]:
        resp = self.client.embeddings.create(model=EMBED_MODEL, input=[text])
        return resp.data[0].embedding

    def _embed_batch(self, texts: list[str]) -> list[list[float]]:
        resp = self.client.embeddings.create(model=EMBED_MODEL, input=texts)
        return [item.embedding for item in resp.data]

    # ------------------------------------------------------------------ #
    #  DOCUMENT MANAGEMENT
    # ------------------------------------------------------------------ #

    def _delete_by_source(self, filename: str):
        """Remove all chunks belonging to a given file."""
        try:
            results = self.collection.get(where={"source": filename})
            if results["ids"]:
                self.collection.delete(ids=results["ids"])
        except Exception:
            pass

    def delete_document(self, filename: str) -> dict:
        self._delete_by_source(filename)
        return {"status": "ok", "deleted": filename}

    def list_documents(self) -> dict:
        try:
            results = self.collection.get(include=["metadatas"])
            sources = list({m["source"] for m in results["metadatas"]})
            return {"documents": sorted(sources), "total": len(sources)}
        except Exception:
            return {"documents": [], "total": 0}

    def get_stats(self) -> dict:
        count = self.collection.count()
        docs = self.list_documents()
        return {
            "total_chunks": count,
            "total_documents": docs["total"],
            "documents": docs["documents"],
        }
