
"""Ingest synthetic AML policies into persistent ChromaDB."""

from app.rag.retrieve import (
    load_policy_chunks,
    get_policy_collection
)


def ingest_policies(
    persist_directory: str = None,
    collection_name: str = "aml_policies"
):
    """Chunk, embed and store AML policy documents."""

    chunks = load_policy_chunks()

    if not chunks:
        raise RuntimeError("No policy documents found")

    collection = get_policy_collection(
        persist_directory=persist_directory,
        collection_name=collection_name
    )

    collection.upsert(
        ids=[chunk["source_id"] for chunk in chunks],

        documents=[
            chunk["content"] for chunk in chunks
        ],

        metadatas=[
            {
                "title": chunk["title"],
                "policy_file": chunk["policy_file"]
            }
            for chunk in chunks
        ]
    )

    return {
        "collection": collection_name,
        "documents_ingested": len(chunks),
        "stored_chunks": collection.count(),
        "status": "SUCCESS"
    }
