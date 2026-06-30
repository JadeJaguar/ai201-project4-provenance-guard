"""
Tests for the ensemble detection stretch feature.
Run these only after starting the Flask app with: python app.py
These tests check that the third signal (punctuation and structure)
is present in the log and that the three-signal formula still
produces meaningful variation across different texts.
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

REPEATED_OPENERS = (
    "It is clear that the policy failed. "
    "It is clear that better planning was needed. "
    "It is clear that stakeholders were not consulted."
)


def submit(text, creator_id):
    response = requests.post(
        f"{BASE_URL}/submit",
        json={"text": text, "creator_id": creator_id},
    )
    assert response.status_code == 200
    return response.json()


def test_log_entry_includes_punctuation_score():
    """
    Checks that the audit log records punctuation_score, alongside
    the existing llm_score and stylometric_score, confirming the
    third signal is wired into the pipeline.
    """
    submit(CLEARLY_AI, "test-ensemble-a")
    response = requests.get(f"{BASE_URL}/log")
    last_entry = response.json()["entries"][-1]

    assert "llm_score" in last_entry
    assert "stylometric_score" in last_entry
    assert "punctuation_score" in last_entry

    print("PASS: log entry includes all three signal scores")
    print(last_entry)


def test_repeated_openers_increase_punctuation_score():
    """
    Checks that text with repeated sentence openers scores higher
    on the punctuation and structure signal than typical casual
    human text, confirming the repeat-opener logic is working.
    """
    repeated_result = submit(REPEATED_OPENERS, "test-ensemble-b")
    casual_result = submit(CLEARLY_HUMAN, "test-ensemble-c")

    response = requests.get(f"{BASE_URL}/log")
    entries = response.json()["entries"]

    repeated_entry = next(
        e for e in entries if e["content_id"] == repeated_result["content_id"]
    )
    casual_entry = next(
        e for e in entries if e["content_id"] == casual_result["content_id"]
    )

    print("repeated openers punctuation_score:", repeated_entry["punctuation_score"])
    print("casual text punctuation_score:", casual_entry["punctuation_score"])

    assert repeated_entry["punctuation_score"] > casual_entry["punctuation_score"], (
        "Repeated openers text should score higher on the punctuation signal"
    )
    print("PASS: repeated openers increase the punctuation and structure score")


def test_three_signal_confidence_still_varies():
    """
    Confirms the three-signal formula still produces meaningfully
    different confidence scores across clearly different texts,
    the same check we ran for the two-signal version in Milestone 4.
    """
    ai_result = submit(CLEARLY_AI, "test-ensemble-d")
    human_result = submit(CLEARLY_HUMAN, "test-ensemble-e")

    print("clearly_ai confidence:", ai_result["confidence"])
    print("clearly_human confidence:", human_result["confidence"])

    assert ai_result["confidence"] != human_result["confidence"]
    print("PASS: three-signal confidence still varies across different texts")


if __name__ == "__main__":
    test_log_entry_includes_punctuation_score()
    test_repeated_openers_increase_punctuation_score()
    test_three_signal_confidence_still_varies()
    print("\nAll ensemble detection tests passed.")