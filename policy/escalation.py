
import re


ESCALATION_RULES = {
    "harassment": [
        "harassment",
        "sexual harassment",
        "harassing",
        "harassed",
        "being harassed",
    ],
    "discrimination": [
        "discrimination",
        "discriminated against",
        "being discriminated against",
    ],
    "retaliation": [
        "retaliation",
        "retaliated against",
        "retaliating",
    ],
    "workplace_safety": [
        "workplace violence",
        "physical threat",
        "threatened me",
        "feel unsafe",
        "unsafe at work",
        "bullying",
    ],
}


def detect_escalation(question):
    """Detect topics that should be reviewed by a human."""

    normalized = re.sub(
        r"\s+",
        " ",
        question.lower()
    ).strip()

    for category, keywords in ESCALATION_RULES.items():
        for keyword in keywords:
            pattern = r"\b" + re.escape(keyword) + r"\b"

            if re.search(pattern, normalized):
                return {
                    "escalate": True,
                    "category": category,
                    "reason": f"Sensitive topic detected: {category}",
                }

    return {
        "escalate": False,
        "category": None,
        "reason": "No escalation keywords detected.",
    }


def escalation_response(category):
    """Return a safe response for questions requiring human review."""

    return (
        "This topic needs individual review by People Operations. "
        "Please contact your HR representative directly. "
        "I can't assess or resolve this situation through the assistant."
    )


if __name__ == "__main__":
    test_cases = [
        ("I think my manager is harassing me.", "harassment"),
        ("I experienced sexual harassment.", "harassment"),
        ("I believe I was discriminated against.", "discrimination"),
        ("My manager retaliated against me.", "retaliation"),
        ("A coworker threatened me at work.", "workplace_safety"),
        ("What is the company's PTO policy?", None),
        ("How many days do I have to enroll in benefits?", None),
    ]

    print("\n=== ESCALATION TESTS ===")

    passed = 0

    for question, expected_category in test_cases:
        result = detect_escalation(question)
        actual_category = result["category"]
        success = actual_category == expected_category

        if success:
            passed += 1

        print(
            f"[{'PASS' if success else 'FAIL'}] "
            f"{question}"
        )
        print(f"  Expected: {expected_category}")
        print(f"  Actual:   {actual_category}")

    print(f"\nResults: {passed}/{len(test_cases)} tests passed.")

    if passed != len(test_cases):
        raise SystemExit(1)
