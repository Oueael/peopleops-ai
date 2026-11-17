
import json
import re
from pathlib import Path

from rag.generate import generate_answer
from rag.database_search import (
    semantic_search,
    find_benefits_deadline_conflicts
)
from rag.citations import is_abstention, validate_citations


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = PROJECT_ROOT / "evals" / "cases.json"
RESULTS_FILE = PROJECT_ROOT / "evals" / "latest_generation_results.json"

REGION = "US"
RETRIEVAL_LIMIT = 3


def check_required_content(answer, expected_terms):
    """Check whether required factual terms appear in the answer."""

    answer_lower = answer.lower()

    missing = [
        term for term in expected_terms
        if term.lower() not in answer_lower
    ]

    return len(missing) == 0, missing


def check_policy_conflict(case):
    """Verify that the expected policy deadlines exist in the database."""

    records = find_benefits_deadline_conflicts(
        role=case["role"],
        region=REGION
    )

    deadlines = set()

    for source, last_updated, section, content in records:
        matches = re.findall(
            r"\b(\d+)\s+days?\b",
            content,
            re.IGNORECASE
        )

        deadlines.update(int(match) for match in matches)

    expected = set(case["expected_deadlines"])

    if deadlines != expected:
        return False, (
            f"Expected {sorted(expected)}, "
            f"found {sorted(deadlines)}."
        )

    return True, f"Detected conflicting deadlines: {sorted(deadlines)}"


def run_case(case):
    """Run an end-to-end generation evaluation."""

    expected_outcome = case["expected_outcome"]

    if expected_outcome == "policy_conflict":
        passed, details = check_policy_conflict(case)

        return {
            "id": case["id"],
            "status": "PASS" if passed else "FAIL",
            "details": details
        }

    answer = generate_answer(
        case["question"],
        role=case["role"],
        region=REGION
    )

    if expected_outcome == "abstain":
        passed = is_abstention(answer)

        return {
            "id": case["id"],
            "status": "PASS" if passed else "FAIL",
            "answer": answer,
            "details": (
                "Assistant correctly abstained."
                if passed
                else "Expected an abstention."
            )
        }

    if expected_outcome == "answer":

        if is_abstention(answer):
            return {
                "id": case["id"],
                "status": "FAIL",
                "answer": answer,
                "details": "Assistant abstained instead of answering."
            }

        documents = semantic_search(
            case["question"],
            role=case["role"],
            region=REGION,
            limit=RETRIEVAL_LIMIT
        )

        expected_source = case["expected_source"]

        retrieved_sources = {
            document[0] for document in documents
        }

        source_found = expected_source in retrieved_sources

        validation = validate_citations(answer, documents)

        content_passed, missing_terms = check_required_content(
            answer,
            case.get("expected_contains", [])
        )

        passed = (
            source_found
            and validation["valid"]
            and not validation["abstained"]
            and content_passed
        )

        details = (
            f"Source found: {source_found}; "
            f"Citations valid: {validation['valid']}; "
            f"Required content present: {content_passed}"
        )

        if missing_terms:
            details += f"; Missing terms: {missing_terms}"

        return {
            "id": case["id"],
            "status": "PASS" if passed else "FAIL",
            "answer": answer,
            "citation_validation": validation,
            "details": details
        }

    return {
        "id": case["id"],
        "status": "DEFERRED",
        "details": f"Unsupported outcome: {expected_outcome}"
    }


def main():
    with open(CASES_FILE, "r", encoding="utf-8") as file:
        cases = json.load(file)

    test_cases = [
        case for case in cases
        if case["expected_outcome"] in {
            "answer",
            "abstain",
            "policy_conflict"
        }
    ]

    results = []

    print("\nPEOPLE OPS ANSWER QUALITY EVALUATION")
    print("=" * 60)

    for case in test_cases:
        print(f"\nTesting {case['id']}: {case['question']}")

        try:
            result = run_case(case)

        except Exception as error:
            result = {
                "id": case["id"],
                "status": "ERROR",
                "details": str(error)
            }

        results.append(result)

        if "answer" in result:
            print("\nAssistant response:")
            print(result["answer"])

        print(f"\n{result['status']}: {result['details']}")
        print("-" * 60)

    passed = sum(r["status"] == "PASS" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)
    errors = sum(r["status"] == "ERROR" for r in results)

    print("\nEVALUATION SUMMARY")
    print("=" * 40)
    print(f"Total tests: {len(results)}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")
    print(f"Errors:      {errors}")

    with open(RESULTS_FILE, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print(f"\nResults saved to: {RESULTS_FILE}")


if __name__ == "__main__":
    main()
