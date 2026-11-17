
import hashlib
import json

from rag.database import get_connection


def question_fingerprint(question):
    """Create a SHA-256 fingerprint without storing question text."""

    normalized = question.strip().lower()

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def record_audit_event(
    question,
    role,
    region,
    outcome,
    request_context=None,
    escalation_category=None,
    retrieved_documents=None,
    citation_validation=None,
    latency_ms=None
):
    """Store metadata about an assistant interaction."""

    context = request_context or {}
    documents = retrieved_documents or []

    sources = [
        {
            "source": document[0],
            "section": document[1]
        }
        for document in documents
    ]

    citation_valid = None
    abstained = None

    if citation_validation is not None:
        citation_valid = citation_validation["valid"]
        abstained = citation_validation.get("abstained", False)

    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO assistant_audit_log (
                    slack_user_id,
                    slack_channel_id,
                    role,
                    region,
                    question_hash,
                    question_length,
                    outcome,
                    escalation_category,
                    retrieved_sources,
                    citation_valid,
                    abstained,
                    latency_ms
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s::jsonb, %s, %s, %s
                );
            """, (
                context.get("user_id"),
                context.get("channel_id"),
                role,
                region,
                question_fingerprint(question),
                len(question),
                outcome,
                escalation_category,
                json.dumps(sources),
                citation_valid,
                abstained,
                latency_ms
            ))

        conn.commit()
