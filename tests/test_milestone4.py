"""
Tests for Milestone 4.
Run these only after starting the Flask app with: python app.py
These tests check that both signals run and that the combined
confidence score changes in a meaningful way across different texts.
"""

import requests

BASE_URL = "http://localhost:5000"

CLEARLY_AI = (
    "Artificial intelligence represents a transformative paradigm shift in modern society. "
    "It is important to note that while the benefits of AI are numerous, it is equally "
    "essential to consider the ethical implications. Furthermore, stakeholders across "
    "various sectors must collaborate to ensure responsible deployment."
)

CLEARLY_HUMAN = (
    "ok so i finally tried that new ramen place downtown and honestly? "
    "underwhelming. the broth was fine but they put WAY too much sodium in it and "
    "i was thirsty for like three hours after. my friend got the spicy version and "
    "said it was better. probably won't go back unless someone drags me there"
)

BORDERLINE_FORMAL_HUMAN = (
    "The relationship between monetary policy and asset price inflation has been "
    "extensively studied in the literature. Central banks face a fundamental tension "
    "between their mandate for price stability and the unintended consequences of "
    "prolonged low interest rates on equity and real estate valuations."
)

BORDERLINE_EDITED_AI = (
    "I've been thinking a lot about remote work lately. There are genuine tradeoffs, "
    "flexibility and no commute on one side, isolation and blurred work-life boundaries "
    "on the other. Studies show productivity varies widely by individual and role type."
)


def submit(text, creator_id):
    response = requests.post(
        f"{BASE_URL}/submit",
        json={"text": text, "creator_id": creator_id},
    )
    assert response.status_code == 200
    return response.json()


def test_log_entry_includes_both_signal_scores():
    """
    Checks that the audit log records both the llm_score and the
    stylometric_score, not just the combined confidence.
    """
    submit(CLEARLY_AI, "test-m4-a")
    response = requests.get(f"{BASE_URL}/log")
    last_entry = response.json()["entries"][-1]

    assert "llm_score" in last_entry
    assert "stylometric_score" in last_entry

    print("PASS: log entry includes both signal scores")
    print(last_entry)


def test_scores_vary_across_four_inputs():
    """
    Submits four different kinds of text and checks that the
    confidence scores are not all the same. A working multi-signal
    system should show some spread across clearly different writing.
    """
    results = {}
    results["clearly_ai"] = submit(CLEARLY_AI, "test-m4-b")["confidence"]
    results["clearly_human"] = submit(CLEARLY_HUMAN, "test-m4-c")["confidence"]
    results["borderline_formal_human"] = submit(BORDERLINE_FORMAL_HUMAN, "test-m4-d")["confidence"]
    results["borderline_edited_ai"] = submit(BORDERLINE_EDITED_AI, "test-m4-e")["confidence"]

    print("PASS: collected scores for all four inputs")
    for label, score in results.items():
        print(f"{label}: {score}")

    unique_scores = set(results.values())
    assert len(unique_scores) > 1, "All four scores were identical, scoring may not be working"


def test_attribution_uses_three_categories():
    """
    Checks that the attribution field can be one of the three
    expected categories: likely_human, uncertain, likely_ai.
    """
    data = submit(CLEARLY_AI, "test-m4-f")
    assert data["attribution"] in ["likely_human", "uncertain", "likely_ai"]

    print("PASS: attribution uses one of the three expected categories")
    print("attribution:", data["attribution"])


if __name__ == "__main__":
    test_log_entry_includes_both_signal_scores()
    test_scores_vary_across_four_inputs()
    test_attribution_uses_three_categories()
    print("\nAll Milestone 4 tests passed.")