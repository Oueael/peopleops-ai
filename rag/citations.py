
import re


def is_abstention(answer):
    """Check whether the assistant indicates insufficient information."""

    abstention_patterns = [
        r"provided (?:handbook )?sources do not contain",
        r"provided sources don't contain",
        r"available sources do not contain",
        r"available information is insufficient",
        r"information (?:is|was) not available in the provided sources",
        r"handbook does not contain",
        r"i (?:could not|couldn't|cannot|can't) find.*information",
        r"there is not enough information",
        r"the handbook doesn't contain",
        r"the handbook does not provide",
        r"cannot determine from the provided sources",
    ]

    return any(
        re.search(pattern, answer, re.IGNORECASE)
        for pattern in abstention_patterns
    )


def validate_citations(answer, retrieved_documents):
    """
    Check whether citations refer to retrieved documents.
    Allow explicit abstentions without citations.
    """

    valid_sources = {
        index: {
            "source": document[0],
            "section": document[1]
        }
        for index, document in enumerate(retrieved_documents, start=1)
    }

    cited_numbers = re.findall(
        r"\[Source (\d+)\]",
        answer,
        re.IGNORECASE
    )

    if not cited_numbers:

        if is_abstention(answer):
            return {
                "valid": True,
                "message": (
                    "Assistant abstained because the available "
                    "information was insufficient."
                ),
                "citations": [],
                "abstained": True
            }

        return {
            "valid": False,
            "message": "No source citations found.",
            "citations": [],
            "abstained": False
        }

    citations = []

    for number in cited_numbers:
        source_number = int(number)

        if source_number not in valid_sources:
            return {
                "valid": False,
                "message": f"Invalid citation: Source {source_number}.",
                "citations": citations,
                "abstained": False
            }

        citation = valid_sources[source_number]

        citations.append({
            "reference": f"Source {source_number}",
            "source": citation["source"],
            "section": citation["section"]
        })

    return {
        "valid": True,
        "message": "All cited references exist in the retrieved documents.",
        "citations": citations,
        "abstained": False
    }


def add_source_details(answer, validation):
    """Append readable document names and sections to an answer."""

    if not validation["valid"] or validation.get("abstained"):
        return answer

    unique_sources = []
    seen_sources = set()

    for citation in validation["citations"]:
        source = citation["source"]
        section = citation["section"]

        source_key = (source, section)

        if source_key not in seen_sources:
            seen_sources.add(source_key)
            unique_sources.append((source, section))

    if not unique_sources:
        return answer

    source_lines = [
        f"- {source} | {section}"
        for source, section in unique_sources
    ]

    return (
        answer.rstrip()
        + "\n\nSources:\n"
        + "\n".join(source_lines)
    )


if __name__ == "__main__":

    sample_documents = [
        ("benefits.md", "Benefits Enrollment", "30 days", 0.49),
        ("pto.md", "Paid Time Off", "20 days", 0.12)
    ]

    print("\n=== TEST 1: VALID CITATION ===")

    test_answer = (
        "New employees have 30 days to enroll "
        "in benefits [Source 1]."
    )

    validation = validate_citations(test_answer, sample_documents)
    print(validation)
    print(add_source_details(test_answer, validation))

    print("\n=== TEST 2: INVALID CITATION ===")

    test_answer = (
        "New employees have 30 days to enroll "
        "in benefits [Source 3]."
    )

    print(validate_citations(test_answer, sample_documents))

    print("\n=== TEST 3: ABSTENTION ===")

    test_answer = (
        "The provided handbook sources do not contain "
        "information about manager performance documentation."
    )

    print(validate_citations(test_answer, sample_documents))

    print("\n=== TEST 4: ALTERNATE ABSTENTION ===")

    test_answer = (
        "I couldn't find information about the annual "
        "home office furniture allowance."
    )

    print(validate_citations(test_answer, sample_documents))
