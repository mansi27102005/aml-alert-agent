"""Optional ChromaDB ingestion for synthetic AML policy documents."""
from pathlib import Path
from .retrieve import load_policy_chunks

def ingest_policies(persist_directory: str = "chroma_db", collection_name: str = "aml_policies"):
    try:
        import chromadb
        from chromadb.utils import embedding_functions
    except ImportError as exc:
        raise RuntimeError("Install chromadb to enable vector ingestion") from exc

    client = chromadb.PersistentClient(path=persist_directory)
    collection = client.get_or_create_collection(name=collection_name)
    chunks = load_policy_chunks()
    if not chunks:
        raise RuntimeError("No policy documents found")
    # Upsert is idempotent: stable IDs prevent duplicate records on reruns.
    collection.upsert(
        ids=[c["source_id"] for c in chunks],
        documents=[c["content"] for c in chunks],
        metadatas=[{"title": c["title"]} for c in chunks],
    )
    return {"collection": collection_name, "documents_ingested": len(chunks)}
