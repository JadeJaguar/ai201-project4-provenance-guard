"""
Tests for Milestone 5.
Run these only after starting the Flask app with: python app.py
These tests check the transparency label, the appeal endpoint, and
that the audit log captures appeal data correctly.
Note: rate limiting is tested separately by hand, since sending 12
rapid requests inside this file would interfere with the other tests
sharing the same submit endpoint.
"""

import requests

BASE_URL = "http://localhost:5000"


def submit(text, creator_id):
    response = requests.post(
        f"{BASE_URL}/submit",
        json={"text": text, "creator_id": creator_id},
    )
    assert response.status_code == 200
    return response.json()


def test_label_is_not_placeholder():
    """
    Checks that the label field has real text, not the old
    placeholder value, and that it is a non-empty string.
    """
    data = submit("This is a normal test sentence for label checking.", "test-m5-a")
    assert data["label"] != "placeholder label"
    assert isinstance(data["label"], str)
    assert len(data["label"]) > 10

    print("PASS: label is real text, not a placeholder")
    print("label:", data["label"])


def test_label_changes_with_attribution():
    """
    Checks that the label text is different for a likely_human
    result compared to a likely_ai result, since each one should
    use a different sentence template.
    """
    human_text = (
        "ok so i finally tried that new ramen place downtown and honestly "
        "underwhelming, the broth was fine but way too salty"
    )
    ai_text = (
        "Artificial intelligence represents a transformative paradigm shift. "
        "It is important to note that stakeholders must collaborate to ensure "
        "responsible deployment across all relevant sectors."
    )

    human_result = submit(human_text, "test-m5-b")
    ai_result = submit(ai_text, "test-m5-c")

    print("human label:", human_result["label"])
    print("ai label:", ai_result["label"])

    assert human_result["label"] != ai_result["label"], (
        "Labels should differ when attribution differs"
    )
    print("PASS: label text changes based on attribution")


def test_appeal_updates_status_and_log():
    """
    Submits a piece of content, then appeals it, then checks the
    audit log to confirm status changed to under_review and the
    appeal reasoning was saved.
    """
    submitted = submit("A short poem about walking in the rain.", "test-m5-d")
    content_id = submitted["content_id"]

    appeal_response = requests.post(
        f"{BASE_URL}/appeal",
        json={
            "content_id": content_id,
            "creator_reasoning": "I wrote this myself, it is based on a real memory.",
        },
    )
    assert appeal_response.status_code == 200
    appeal_data = appeal_response.json()
    assert appeal_data["status"] == "under_review"

    log_response = requests.get(f"{BASE_URL}/log")
    entries = log_response.json()["entries"]
    matching = [e for e in entries if e["content_id"] == content_id]

    assert len(matching) == 1, "Expected exactly one log entry for this content_id"
    entry = matching[0]

    assert entry["status"] == "under_review"
    assert "appeal_reasoning" in entry
    assert "appeal_timestamp" in entry

    print("PASS: appeal updates status and is reflected in the audit log")
    print(entry)


def test_appeal_with_missing_content_id_returns_404():
    """
    Checks that appealing a content_id that does not exist
    returns a 404 error, instead of silently doing nothing.
    """
    response = requests.post(
        f"{BASE_URL}/appeal",
        json={
            "content_id": "this-id-does-not-exist",
            "creator_reasoning": "testing a missing id",
        },
    )
    assert response.status_code == 404

    print("PASS: appealing a missing content_id returns 404")


def test_appeal_with_missing_fields_returns_400():
    """
    Checks that submitting an appeal without creator_reasoning
    returns a 400 error, instead of accepting an incomplete appeal.
    """
    response = requests.post(
        f"{BASE_URL}/appeal",
        json={"content_id": "some-id"},
    )
    assert response.status_code == 400

    print("PASS: appeal with missing fields returns 400")


if __name__ == "__main__":
    test_label_is_not_placeholder()
    test_label_changes_with_attribution()
    test_appeal_updates_status_and_log()
    test_appeal_with_missing_content_id_returns_404()
    test_appeal_with_missing_fields_returns_400()
    print("\nAll Milestone 5 tests passed.")