
import json
from pathlib import Path

from rag.database_search import (
    semantic_search,
    find_benefits_deadline_conflicts
)
from policy.escalation import detect_escalation


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CASES_FILE = PROJECT_ROOT / "evals" / "cases.json"

REGION = "US"
RETRIEVAL_LIMIT = 4


def run_case(case):
    """Run the local checks supported by the application."""

    case_id = case["id"]
    question = case["question"]
    role = case["role"]
    expected_outcome = case["expected_outcome"]
    expected_source = case.get("expected_source")

    # Escalation tests don't need database retrieval.
    if expected_outcome == "escalate":
        result = detect_escalation(question)
        passed = result["escalate"]

        return {
            "id": case_id,
            "status": "PASS" if passed else "FAIL",
            "details": (
                f"Escalation detected: {result.get('category')}"
                if passed
                else "Expected escalation was not detected."
            )
        }

    # Test policy conflict detection directly.
    if expected_outcome == "policy_conflict":
        records = find_benefits_deadline_conflicts(
            role=role,
            region=REGION
        )

        actual_deadlines = set()

        for source, last_updated, section, content in records:
            import re

            matches = re.findall(
                r"\b(\d+)\s+days?\b",
                content,
                re.IGNORECASE
            )

            actual_deadlines.update(
                int(match) for match in matches
            )

        expected_deadlines = set(
            case["expected_deadlines"]
        )

        passed = actual_deadlines == expected_deadlines

        return {
            "id": case_id,
            "status": "PASS" if passed else "FAIL",
            "details": (
                f"Conflicting deadlines detected: "
                f"{sorted(actual_deadlines)}"
                if passed
                else (
                    f"Expected deadlines {sorted(expected_deadlines)}, "
                    f"found {sorted(actual_deadlines)}"
                )
            )
        }

    # Unanswerable tests require actual generation.
    if expected_outcome == "abstain":
        return {
            "id": case_id,
            "status": "DEFERRED",
            "details": (
                "Requires generation evaluation to verify abstention."
            )
        }

    # Retrieve documents using the role assigned by the test.
    documents = semantic_search(
        question,
        role=role,
        region=REGION,
        limit=RETRIEVAL_LIMIT
    )

    retrieved_sources = {
        document[0]
        for document in documents
    }

    if expected_outcome == "answer":
        passed = expected_source in retrieved_sources

        details = (
            f"Expected source retrieved: {expected_source}"
            if passed
            else (
                f"Expected {expected_source}, "
                f"retrieved: {sorted(retrieved_sources)}"
            )
        )

    elif expected_outcome == "restricted":
        passed = expected_source not in retrieved_sources

        details = (
            f"Restricted source correctly filtered: {expected_source}"
            if passed
            else f"SECURITY FAILURE: retrieved {expected_source}"
        )

    else:
        return {
            "id": case_id,
            "status": "DEFERRED",
            "details": f"Unsupported outcome: {expected_outcome}"
        }

    return {
        "id": case_id,
        "status": "PASS" if passed else "FAIL",
        "details": details
    }


def main():
    with open(CASES_FILE, "r", encoding="utf-8") as file:
        cases = json.load(file)

    results = []

    print("\nPEOPLE OPS ASSISTANT EVALUATION")
    print("=" * 55)

    for case in cases:
        try:
            result = run_case(case)

        except Exception as error:
            result = {
                "id": case["id"],
                "status": "ERROR",
                "details": str(error)
            }

        results.append(result)

        print(
            f"{result['status']:8} "
            f"{result['id']:10} "
            f"{result['details']}"
        )

    passed = sum(r["status"] == "PASS" for r in results)
    failed = sum(r["status"] == "FAIL" for r in results)
    deferred = sum(r["status"] == "DEFERRED" for r in results)
    errors = sum(r["status"] == "ERROR" for r in results)

    print("\n" + "=" * 55)
    print(f"Total cases: {len(results)}")
    print(f"Passed:      {passed}")
    print(f"Failed:      {failed}")
    print(f"Deferred:    {deferred}")
    print(f"Errors:      {errors}")

    results_file = (
        PROJECT_ROOT / "evals" / "latest_results.json"
    )

    with open(results_file, "w", encoding="utf-8") as file:
        json.dump(results, file, indent=2)

    print(f"\nResults saved to: {results_file}")


if __name__ == "__main__":
    main()
