"""
Tests for the analytics dashboard stretch feature.
Run these only after starting the Flask app with: python app.py
These tests check that GET /analytics returns correct structure
and that the numbers it reports are internally consistent.
"""

import requests

BASE_URL = "http://localhost:5000"


def test_analytics_returns_required_fields():
    """
    Checks that GET /analytics returns all four expected top-level
    fields: total_submissions, attribution_breakdown, appeal_rate,
    and average_confidence.
    """
    response = requests.get(f"{BASE_URL}/analytics")
    assert response.status_code == 200

    data = response.json()
    required_fields = [
        "total_submissions",
        "attribution_breakdown",
        "appeal_rate",
        "average_confidence",
    ]
    for field in required_fields:
        assert field in data, f"Missing field: {field}"

    print("PASS: analytics returns all required fields")
    print(data)


def test_attribution_breakdown_has_three_categories():
    """
    Checks that the attribution breakdown includes all three
    categories, each with a count and a percent.
    """
    response = requests.get(f"{BASE_URL}/analytics")
    data = response.json()

    breakdown = data["attribution_breakdown"]
    expected_categories = ["likely_human", "uncertain", "likely_ai"]

    for category in expected_categories:
        assert category in breakdown, f"Missing category: {category}"
        assert "count" in breakdown[category]
        assert "percent" in breakdown[category]

    print("PASS: attribution breakdown includes all three categories")


def test_attribution_percentages_add_up_to_roughly_100():
    """
    Checks that the three category percentages sum to roughly 100,
    allowing a small margin for rounding.
    """
    response = requests.get(f"{BASE_URL}/analytics")
    data = response.json()

    breakdown = data["attribution_breakdown"]
    total_percent = sum(category["percent"] for category in breakdown.values())

    print("total percent across categories:", total_percent)
    assert 99 <= total_percent <= 101, "Percentages should sum to roughly 100"
    print("PASS: attribution percentages sum to roughly 100")


def test_attribution_counts_match_total_submissions():
    """
    Checks that the sum of counts across all three categories
    equals total_submissions, confirming no submissions were
    dropped or double-counted.
    """
    response = requests.get(f"{BASE_URL}/analytics")
    data = response.json()

    breakdown = data["attribution_breakdown"]
    total_count = sum(category["count"] for category in breakdown.values())

    assert total_count == data["total_submissions"], (
        "Sum of category counts should equal total_submissions"
    )
    print("PASS: attribution counts match total submissions")


def test_average_confidence_is_between_0_and_1():
    """
    Checks that average_confidence is a valid number between 0 and 1,
    consistent with how individual confidence scores are bounded.
    """
    response = requests.get(f"{BASE_URL}/analytics")
    data = response.json()

    average_confidence = data["average_confidence"]
    assert isinstance(average_confidence, (int, float))
    assert 0.0 <= average_confidence <= 1.0

    print("PASS: average confidence is a valid number between 0 and 1")
    print("average_confidence:", average_confidence)


if __name__ == "__main__":
    test_analytics_returns_required_fields()
    test_attribution_breakdown_has_three_categories()
    test_attribution_percentages_add_up_to_roughly_100()
    test_attribution_counts_match_total_submissions()
    test_average_confidence_is_between_0_and_1()
    print("\nAll analytics dashboard tests passed.")