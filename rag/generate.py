
import os
import re
import time
import logging

from dotenv import load_dotenv
from google import genai
from google.genai import types

from rag.database_search import (
    semantic_search,
    find_benefits_deadline_conflicts
)
from rag.prompt import build_prompt
from rag.citations import (
    validate_citations,
    add_source_details
)
from rag.audit import record_audit_event
from policy.escalation import detect_escalation, escalation_response


load_dotenv()

logger = logging.getLogger(__name__)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("GEMINI_API_KEY was not found in the .env file.")

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.5-flash-lite"

MIN_SIMILARITY = 0.50
RETRIEVAL_LIMIT = 3


def audit_safely(**kwargs):
    """Prevent an audit logging failure from breaking an answer."""

    try:
        record_audit_event(**kwargs)
    except Exception:
        logger.exception("Failed to write assistant audit record.")


def check_benefits_deadline_conflict(question, role, region):
    """
    Check whether accessible handbook documents contain
    conflicting benefits enrollment deadlines.
    """

    question_lower = question.lower()

    asks_about_benefits = "benefit" in question_lower
    asks_about_enrollment = (
        "enroll" in question_lower
        or "enrollment" in question_lower
    )

    if not (asks_about_benefits and asks_about_enrollment):
        return None

    records = find_benefits_deadline_conflicts(
        role=role,
        region=region
    )

    deadlines = {}

    for source, last_updated, section, content in records:
        matches = re.findall(
            r"\b(\d+)\s+days?\b",
            content,
            re.IGNORECASE
        )

        for match in matches:
            days = int(match)

            deadlines.setdefault(days, set()).add(source)

    if len(deadlines) <= 1:
        return None

    details = []

    for days in sorted(deadlines):
        sources = ", ".join(sorted(deadlines[days]))
        details.append(f"{days} days ({sources})")

    return (
        "I found conflicting benefits enrollment deadlines "
        "in the handbook: "
        + "; ".join(details)
        + ". I can't determine which deadline is authoritative. "
        "Please contact People Operations for confirmation."
    )


def generate_answer(
    question,
    role="employee",
    region="US",
    request_context=None
):
    """Retrieve, generate, validate, and audit an answer."""

    total_start = time.perf_counter()

    # STEP 1: Check for sensitive topics.

    escalation = detect_escalation(question)

    if escalation["escalate"]:
        answer = escalation_response(escalation["category"])

        total_ms = int(
            (time.perf_counter() - total_start) * 1000
        )

        audit_safely(
            question=question,
            role=role,
            region=region,
            outcome="escalated",
            request_context=request_context,
            escalation_category=escalation["category"],
            latency_ms=total_ms
        )

        logger.info("Escalation completed in %s ms", total_ms)

        return answer

    # STEP 2: Check for conflicting benefits deadlines.

    conflict_answer = check_benefits_deadline_conflict(
        question,
        role,
        region
    )

    if conflict_answer:
        total_ms = int(
            (time.perf_counter() - total_start) * 1000
        )

        audit_safely(
            question=question,
            role=role,
            region=region,
            outcome="policy_conflict",
            request_context=request_context,
            latency_ms=total_ms
        )

        logger.warning("Conflicting benefits deadlines detected.")

        return conflict_answer

    # STEP 3: Retrieve authorized handbook documents.

    retrieval_start = time.perf_counter()

    documents = semantic_search(
        question,
        role=role,
        region=region,
        limit=RETRIEVAL_LIMIT
    )

    retrieval_ms = int(
        (time.perf_counter() - retrieval_start) * 1000
    )

    logger.info("Retrieval completed in %s ms", retrieval_ms)

    if not documents:
        total_ms = int(
            (time.perf_counter() - total_start) * 1000
        )

        audit_safely(
            question=question,
            role=role,
            region=region,
            outcome="no_retrieval",
            request_context=request_context,
            latency_ms=total_ms
        )

        return "I couldn't find relevant information in the handbook."

    # STEP 4: Check retrieval relevance.

    top_similarity = documents[0][3]

    logger.info(
        "Top retrieval similarity: %.4f",
        top_similarity
    )

    if top_similarity < MIN_SIMILARITY:
        total_ms = int(
            (time.perf_counter() - total_start) * 1000
        )

        audit_safely(
            question=question,
            role=role,
            region=region,
            outcome="low_relevance",
            request_context=request_context,
            retrieved_documents=documents,
            latency_ms=total_ms
        )

        logger.info(
            "Request rejected due to low relevance: %.4f",
            top_similarity
        )

        return (
            "I couldn't find sufficiently relevant information "
            "in the handbook. Please contact People Operations."
        )

    # STEP 5: Build prompt and call Gemini.

    prompt = build_prompt(question, documents)

    generation_start = time.perf_counter()

    try:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2
            )
        )

        answer = response.text

    except Exception:
        generation_ms = int(
            (time.perf_counter() - generation_start) * 1000
        )

        total_ms = int(
            (time.perf_counter() - total_start) * 1000
        )

        logger.exception("Gemini generation failed.")
        logger.info(
            "Generation failed after %s ms",
            generation_ms
        )

        audit_safely(
            question=question,
            role=role,
            region=region,
            outcome="generation_error",
            request_context=request_context,
            retrieved_documents=documents,
            latency_ms=total_ms
        )

        raise

    generation_ms = int(
        (time.perf_counter() - generation_start) * 1000
    )

    logger.info(
        "Gemini generation completed in %s ms",
        generation_ms
    )

    # STEP 6: Validate citations.

    validation_start = time.perf_counter()

    validation = validate_citations(answer, documents)

    validation_ms = int(
        (time.perf_counter() - validation_start) * 1000
    )

    logger.info(
        "Citation validation completed in %s ms",
        validation_ms
    )

    if not validation["valid"]:
        total_ms = int(
            (time.perf_counter() - total_start) * 1000
        )

        audit_safely(
            question=question,
            role=role,
            region=region,
            outcome="citation_rejected",
            request_context=request_context,
            retrieved_documents=documents,
            citation_validation=validation,
            latency_ms=total_ms
        )

        logger.warning(
            "Citation validation failed: %s",
            validation["message"]
        )

        return (
            "I couldn't provide a verified answer. "
            "Please contact People Operations."
        )

    outcome = (
        "abstained"
        if validation.get("abstained")
        else "answered"
    )

    total_ms = int(
        (time.perf_counter() - total_start) * 1000
    )

    audit_safely(
        question=question,
        role=role,
        region=region,
        outcome=outcome,
        request_context=request_context,
        retrieved_documents=documents,
        citation_validation=validation,
        latency_ms=total_ms
    )

    logger.info(
        "Request timing: retrieval=%s ms, generation=%s ms, "
        "validation=%s ms, total=%s ms",
        retrieval_ms,
        generation_ms,
        validation_ms,
        total_ms
    )

    return add_source_details(answer, validation)


if __name__ == "__main__":
    question = (
        "When do new employees need to enroll "
        "in health insurance?"
    )

    answer = generate_answer(
        question,
        role="employee",
        region="US"
    )

    print("\n=== PEOPLE OPS ASSISTANT ===")
    print(answer)
