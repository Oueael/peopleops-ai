import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


CHUNKS_PATH = Path("data/chunks.json")
VECTORS_PATH = Path("data/vectors.npy")

MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main():

    # Load our previously processed documents
    chunks = json.loads(
        CHUNKS_PATH.read_text(encoding="utf-8")
    )

    if not chunks:
        raise ValueError("No document chunks found.")

    # Load the embedding model
    print(f"Loading model: {MODEL_NAME}")

    model = SentenceTransformer(MODEL_NAME)

    # Extract text from each chunk
    texts = [
        chunk["text"]
        for chunk in chunks
    ]

    # Generate embeddings
    print(f"Generating embeddings for {len(texts)} chunks...")

    embeddings = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=True
    )

    # Convert to NumPy array
    embeddings = np.asarray(
        embeddings,
        dtype=np.float32
    )

    # Save vectors
    np.save(VECTORS_PATH, embeddings)

    print("\nEmbedding generation complete!")
    print(f"Number of vectors: {len(embeddings)}")
    print(f"Vector dimensions: {embeddings.shape[1]}")
    print(f"Saved to: {VECTORS_PATH}")


if __name__ == "__main__":
    main()