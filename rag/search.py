import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


CHUNKS_PATH = Path("data/chunks.json")
VECTORS_PATH = Path("data/vectors.npy")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def cosine_similarity(query_vector, document_vectors):
    """
    Calculate cosine similarity between a query
    and multiple document vectors.

    Our vectors are already normalized, so
    the dot product gives cosine similarity.
    """

    return document_vectors @ query_vector


def main():

    # Load document records
    chunks = json.loads(
        CHUNKS_PATH.read_text(encoding="utf-8")
    )

    # Load stored embeddings
    document_vectors = np.load(VECTORS_PATH)

    if len(chunks) != len(document_vectors):
        raise ValueError("Chunk/vector count mismatch.")

    # Load embedding model
    model = SentenceTransformer(MODEL_NAME)

    # Ask a question
    query = input("\nAsk the handbook a question: ")

    # Embed the question
    query_vector = model.encode(
        query,
        normalize_embeddings=True
    )

    # Calculate similarities
    scores = cosine_similarity(
        query_vector,
        document_vectors
    )

    # Get the three most relevant chunks
    top_indices = np.argsort(scores)[::-1][:3]

    print("\n--- SEARCH RESULTS ---\n")

    for index in top_indices:

        chunk = chunks[index]

        print(f"Source: {chunk['source']}")
        print(f"Section: {chunk['section']}")
        print(f"Similarity: {scores[index]:.4f}")
        print(f"Content: {chunk['text']}")
        print("-" * 50)


if __name__ == "__main__":
    main()