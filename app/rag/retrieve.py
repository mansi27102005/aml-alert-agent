
"""Policy chunking and semantic retrieval using ChromaDB."""

import re
from pathlib import Path
from typing import Dict, List

import chromadb
from chromadb.utils.embedding_functions import (
    SentenceTransformerEmbeddingFunction
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = PROJECT_ROOT / "data" / "policies"

MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "aml_policies"
DEFAULT_DB_PATH = PROJECT_ROOT / "chroma_db"

PREFIX = {
    "aml_structuring_policy.md": "POL_STRUCT",
    "aml_sanctions_policy.md": "POL_SANCT",
    "aml_high_value_policy.md": "POL_HVT",
    "customer_due_diligence_policy.md": "POL_KYC",
    "evidence_quality_policy.md": "POL_EVIDENCE",
    "human_escalation_policy.md": "POL_ESCALATE",
}


def split_text(text: str, max_chars: int = 500) -> List[str]:
    """Split policy text into stable, sentence-aware chunks."""

    text = re.sub(r"\s+", " ", text).strip()

    if not text:
        return []

    sentences = re.split(r"(?<=[.!?])\s+", text)

    chunks = []
    current = ""

    for sentence in sentences:
        if len(sentence) > max_chars:
            words = sentence.split()

            for word in words:
                if current and len(current) + len(word) + 1 > max_chars:
                    chunks.append(current.strip())
                    current = ""

                current = (current + " " + word).strip()

            continue

        if current and len(current) + len(sentence) + 1 > max_chars:
            chunks.append(current.strip())
            current = sentence
        else:
            current = (current + " " + sentence).strip()

    if current:
        chunks.append(current.strip())

    return chunks


def load_policy_chunks() -> List[Dict[str, str]]:
    """Load policies and assign deterministic source IDs."""

    chunks = []

    for filename, prefix in PREFIX.items():

        path = POLICY_DIR / filename

        if not path.exists():
            raise FileNotFoundError(
                f"Policy document missing: {path}"
            )

        content = path.read_text(encoding="utf-8")

        text_chunks = split_text(content)

        for index, text_chunk in enumerate(text_chunks, start=1):

            chunks.append({
                "source_id": f"{prefix}_{index:02d}",
                "title": path.stem.replace("_", " ").title(),
                "content": text_chunk,
                "policy_file": filename
            })

    return chunks


def get_policy_collection(
    persist_directory: str = None,
    collection_name: str = COLLECTION_NAME
):
    """Create or connect to the persistent ChromaDB collection."""

    db_path = (
        Path(persist_directory)
        if persist_directory
        else DEFAULT_DB_PATH
    )

    if not db_path.is_absolute():
        db_path = PROJECT_ROOT / db_path

    db_path.mkdir(parents=True, exist_ok=True)

    client = chromadb.PersistentClient(
        path=str(db_path)
    )

    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name=MODEL_NAME,
        normalize_embeddings=True
    )

    collection = client.get_or_create_collection(
        name=collection_name,
        embedding_function=embedding_function,
        configuration={
            "hnsw": {
                "space": "cosine"
            }
        }
    )

    return collection


def retrieve_policy(
    query: str,
    top_k: int = 3
) -> List[Dict]:

    """Retrieve relevant policy chunks using semantic similarity."""

    if not query or not query.strip():
        raise ValueError("Policy query cannot be empty")

    if top_k < 1:
        raise ValueError("top_k must be at least 1")

    collection = get_policy_collection()

    total_chunks = collection.count()

    if total_chunks == 0:
        raise RuntimeError(
            "No policy documents indexed. "
            "Run ingest_policies() first."
        )

    results = collection.query(
        query_texts=[query],
        n_results=min(top_k, total_chunks),
        include=[
            "documents",
            "metadatas",
            "distances"
        ]
    )

    retrieved = []

    for index, content in enumerate(results["documents"][0]):

        metadata = results["metadatas"][0][index]

        retrieved.append({
            "source_id": results["ids"][0][index],
            "title": metadata["title"],
            "content": content,
            "distance": float(
                results["distances"][0][index]
            )
        })

    return retrieved

def retrieve_policy_context(
    query: str,
    typology: str = None,
    top_k: int = 2
) -> List[Dict]:
    """
    Compatibility adapter for Mansi's LangGraph policy node.

    Uses the existing ChromaDB semantic retrieval function
    and returns the format expected by Role A.
    """

    if typology:
        query = f"{typology} {query}"

    results = retrieve_policy(
        query=query,
        top_k=top_k
    )

    # Return the shared Interface Contract format
    return [
        {
            "source_id": item["source_id"],
            "title": item["title"],
            "content": item["content"]
        }
        for item in results
    ]
