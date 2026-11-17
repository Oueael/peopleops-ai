
from sentence_transformers import SentenceTransformer

from rag.database import get_connection


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

model = SentenceTransformer(MODEL_NAME)


ROLE_AUDIENCES = {
    "employee": ["all_employees"],
    "manager": ["all_employees", "managers"],
    "hr": ["all_employees", "managers", "hr"]
}


def get_allowed_audiences(role):
    """Return the document audiences accessible to a role."""

    if role not in ROLE_AUDIENCES:
        raise ValueError(f"Unknown employee role: {role}")

    return ROLE_AUDIENCES[role]


def semantic_search(query, role="employee", region="US", limit=3):
    """Find relevant chunks using embedding similarity and access filters."""

    allowed_audiences = get_allowed_audiences(role)

    query_embedding = model.encode(
        query,
        normalize_embeddings=True
    )

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    source,
                    section,
                    content,
                    1 - (embedding <=> %s::vector) AS similarity
                FROM document_chunks
                WHERE audience = ANY(%s)
                  AND region = %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s;
                """,
                (
                    query_embedding.tolist(),
                    allowed_audiences,
                    region,
                    query_embedding.tolist(),
                    limit
                )
            )

            return cur.fetchall()

def find_benefits_deadline_conflicts(role="employee", region="US"):
    """
    Find accessible handbook chunks that state benefits
    enrollment deadlines in days.
    """

    allowed_audiences = get_allowed_audiences(role)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    source,
                    last_updated,
                    section,
                    content
                FROM document_chunks
                WHERE audience = ANY(%s)
                  AND region = %s
                  AND POSITION('enroll' IN LOWER(content)) > 0
                  AND content ~* '[0-9]+[[:space:]]+days?'
                ORDER BY last_updated DESC;
                """,
                (
                    allowed_audiences,
                    region
                )
            )

            return cur.fetchall()


def keyword_search(query, role="employee", region="US", limit=3):
    """Find matching chunks using full-text search and access filters."""

    allowed_audiences = get_allowed_audiences(role)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    source,
                    section,
                    content,
                    ts_rank(
                        to_tsvector('english', content),
                        plainto_tsquery('english', %s)
                    ) AS relevance
                FROM document_chunks
                WHERE audience = ANY(%s)
                  AND region = %s
                  AND to_tsvector('english', content)
                      @@ plainto_tsquery('english', %s)
                ORDER BY relevance DESC
                LIMIT %s;
                """,
                (
                    query,
                    allowed_audiences,
                    region,
                    query,
                    limit
                )
            )

            return cur.fetchall()


if __name__ == "__main__":
    question = "What are the responsibilities for managing team PTO requests?"

    print("\n=== EMPLOYEE SEARCH ===")

    for result in semantic_search(question, role="employee"):
        print(result)

    print("\n=== MANAGER SEARCH ===")

    for result in semantic_search(question, role="manager"):
        print(result)

    print("\n=== BENEFITS DEADLINE RECORDS ===")

    for result in find_benefits_deadline_conflicts():
        print(result)
