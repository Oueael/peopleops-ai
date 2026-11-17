import json
import numpy as np

from rag.database import get_connection


CHUNKS_FILE = "data/chunks.json"
VECTORS_FILE = "data/vectors.npy"


def load_chunks():
    """Load processed document chunks from JSON."""

    with open(CHUNKS_FILE, "r", encoding="utf-8") as file:
        return json.load(file)


def load_vectors():
    """Load document embeddings from NumPy."""

    return np.load(VECTORS_FILE)


def store_chunks():
    chunks = load_chunks()
    vectors = load_vectors()

    if len(chunks) != len(vectors):
        raise ValueError(
            f"Chunk/vector mismatch: "
            f"{len(chunks)} chunks and {len(vectors)} vectors"
        )

    with get_connection() as conn:
        with conn.cursor() as cur:

            # Remove previously stored versions of these sources.
            sources = list(set(chunk["source"] for chunk in chunks))

            cur.execute(
                "DELETE FROM document_chunks WHERE source = ANY(%s)",
                (sources,)
            )

            # Insert chunks and their corresponding embeddings.
            for chunk, vector in zip(chunks, vectors):

                cur.execute(
                    """
                    INSERT INTO document_chunks (
                        source,
                        section,
                        content,
                        audience,
                        region,
                        last_updated,
                        embedding
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        chunk["source"],
                        chunk.get("section"),
                        chunk["text"],
                        chunk.get("audience", "all_employees"),
                        chunk.get("region", "global"),
                        chunk.get("last_updated"),
                        vector.tolist()
                    )
                )

        conn.commit()

    print(f"Successfully stored {len(chunks)} chunks.")


if __name__ == "__main__":
    store_chunks()