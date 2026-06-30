"""
Tests for Milestone 3.
Run these only after starting the Flask app with: python app.py
These tests check the submit endpoint and the log endpoint.
"""

import requests

BASE_URL = "http://localhost:5000"


def test_submit_returns_required_fields():
    """
    Checks that POST /submit returns content_id, attribution,
    confidence, and label. This is the basic contract every
    other milestone depends on.
    """
    payload = {
        "text": "The sun dipped below the horizon, painting the sky in hues of amber and rose.",
        "creator_id": "test-user-1",
    }
    response = requests.post(f"{BASE_URL}/submit", json=payload)

    assert response.status_code == 200, "Expected status code 200"

    data = response.json()
    required_fields = ["content_id", "attribution", "confidence", "label"]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    print("PASS: submit returns all required fields")
    print(data)


def test_confidence_is_a_number_between_0_and_1():
    """
    Checks that the confidence score is a real number,
    not a string, and that it falls between 0 and 1.
    """
    payload = {
        "text": "ok so i finally tried that new ramen place downtown and honestly underwhelming",
        "creator_id": "test-user-2",
    }
    response = requests.post(f"{BASE_URL}/submit", json=payload)
    data = response.json()

    confidence = data["confidence"]
    assert isinstance(confidence, (int, float)), "Confidence should be a number"
    assert 0.0 <= confidence <= 1.0, "Confidence should be between 0 and 1"

    print("PASS: confidence is a valid number between 0 and 1")
    print("confidence:", confidence)


def test_log_endpoint_returns_entries():
    """
    Checks that GET /log returns a list of entries, and that
    the list is not empty after at least one submission.
    """
    response = requests.get(f"{BASE_URL}/log")
    assert response.status_code == 200, "Expected status code 200"

    data = response.json()
    assert "entries" in data, "Response should have an entries field"
    assert len(data["entries"]) > 0, "Log should have at least one entry"

    print("PASS: log endpoint returns entries")
    print("number of entries:", len(data["entries"]))


def test_log_entry_has_required_fields():
    """
    Checks that each log entry has the fields needed for the
    audit log requirement: content_id, timestamp, attribution,
    confidence, and llm_score.
    """
    response = requests.get(f"{BASE_URL}/log")
    data = response.json()

    last_entry = data["entries"][-1]
    required_fields = ["content_id", "timestamp", "attribution", "confidence", "llm_score"]
    for field in required_fields:
        assert field in last_entry, f"Missing field in log entry: {field}"

    print("PASS: log entry has all required fields")


if __name__ == "__main__":
    test_submit_returns_required_fields()
    test_confidence_is_a_number_between_0_and_1()
    test_log_endpoint_returns_entries()
    test_log_entry_has_required_fields()
    print("\nAll Milestone 3 tests passed.")