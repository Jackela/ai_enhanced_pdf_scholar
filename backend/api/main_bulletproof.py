import json
import os
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI(title="PDF Scholar API - Bulletproof Edition")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "pdf_scholar.db"


# Health check endpoints
@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


@app.get("/api/health")
def api_health():
    return {
        "status": "healthy",
        "service": "api",
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/ping")
def ping():
    return {"message": "pong"}


# Document models
class DocumentCreate(BaseModel):
    title: str
    content: str | None = ""
    metadata: dict[str, Any] | None = {}


class Document(BaseModel):
    id: str
    title: str
    content: str | None
    metadata: dict[str, Any] | None
    created_at: datetime
    updated_at: datetime


# Document endpoints
@app.post("/api/documents", response_model=Document)
def create_document(doc: DocumentCreate):
    doc_id = str(uuid.uuid4())
    now = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO documents (id, title, content, metadata, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (doc_id, doc.title, doc.content, json.dumps(doc.metadata), now, now),
    )

    conn.commit()
    conn.close()

    return Document(
        id=doc_id,
        title=doc.title,
        content=doc.content,
        metadata=doc.metadata,
        created_at=now,
        updated_at=now,
    )


@app.get("/api/documents/{doc_id}", response_model=Document)
def get_document(doc_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id, title, content, metadata, created_at, updated_at
        FROM documents WHERE id = ?
    """,
        (doc_id,),
    )

    row = cursor.fetchone()
    conn.close()

    if not row:
        raise HTTPException(status_code=404, detail="Document not found")

    return Document(
        id=row[0],
        title=row[1],
        content=row[2],
        metadata=json.loads(row[3]) if row[3] else {},
        created_at=datetime.fromisoformat(row[4]),
        updated_at=datetime.fromisoformat(row[5]),
    )


@app.get("/api/documents", response_model=list[Document])
def list_documents():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, title, content, metadata, created_at, updated_at
        FROM documents ORDER BY created_at DESC LIMIT 100
    """)

    rows = cursor.fetchall()
    conn.close()

    return [
        Document(
            id=row[0],
            title=row[1],
            content=row[2],
            metadata=json.loads(row[3]) if row[3] else {},
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
        )
        for row in rows
    ]


# Collection endpoints
class CollectionCreate(BaseModel):
    name: str
    description: str | None = ""


@app.post("/api/collections")
def create_collection(collection: CollectionCreate):
    coll_id = str(uuid.uuid4())
    now = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO collections (id, name, description, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?)
    """,
        (coll_id, collection.name, collection.description, now, now),
    )

    conn.commit()
    conn.close()

    return {
        "id": coll_id,
        "name": collection.name,
        "description": collection.description,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
    }


# Multi-document index endpoints
@app.post("/api/multi-document-indexes")
def create_index(data: dict[str, Any]):
    index_id = str(uuid.uuid4())
    now = datetime.now()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO multi_document_indexes
        (id, collection_id, name, description, config, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """,
        (
            index_id,
            data.get("collection_id"),
            data.get("name", "Default Index"),
            data.get("description", ""),
            json.dumps(data.get("config", {})),
            now,
            now,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "id": index_id,
        "collection_id": data.get("collection_id"),
        "name": data.get("name", "Default Index"),
        "status": "created",
    }


if __name__ == "__main__":
    import uvicorn

    server_host = os.getenv("API_SERVER_HOST", "127.0.0.1")
    server_port = int(os.getenv("API_SERVER_PORT", "8000"))
    uvicorn.run(app, host=server_host, port=server_port)
