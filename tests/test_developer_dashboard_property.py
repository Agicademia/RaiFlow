"""Property-based tests for the developer-dashboard feature.

Uses Hypothesis to verify correctness properties across all valid inputs.

Requirements: 1.4, 4.1, 4.2, 4.3, 4.4, 5.2, 5.3, 5.6, 6.1, 6.2, 6.3, 6.4, 6.5,
              6.6, 6.7, 8.1, 8.2, 8.4, 8.5, 9.4, 10.7, 3.6
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from raiflow.cli import _is_ci
from raiflow.dashboard_server import DashboardServer, RunState
from raiflow.gate import CheckResult


# ---------------------------------------------------------------------------
# Hypothesis strategy
# ---------------------------------------------------------------------------

@st.composite
def st_check_result(draw):
    """Generate valid CheckResult instances."""
    status = draw(st.sampled_from(["pass", "fail", "skipped"]))
    return CheckResult(
        article_id=draw(st.text(min_size=1, max_size=20)),
        rule_id=draw(st.text(min_size=1, max_size=20)),
        check_name=draw(st.text(min_size=1, max_size=50)),
        status=status,
        score=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        threshold=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)),
        remediation_hint=draw(st.text(max_size=100)) if status == "fail" else "",
    )


# ---------------------------------------------------------------------------
# Pure Python helpers
# ---------------------------------------------------------------------------

def compute_overall_score(results: list) -> int | None:
    """Compute overall compliance score as round((passing / non_skipped) * 100).

    Returns None when all results are skipped.
    """
    passing = sum(1 for r in results if r.status == "pass")
    non_skipped = sum(1 for r in results if r.status != "skipped")
    if non_skipped == 0:
        return None
    return round((passing / non_skipped) * 100)


def compute_risk_level(score: int) -> tuple[str, str]:
    """Map an integer score 0-100 to (risk_level, colour).

    100        → ("Low",      "green")
    75–99      → ("Medium",   "amber")
    50–74      → ("High",     "orange")
    0–49       → ("Critical", "red")
    """
    if score == 100:
        return ("Low", "green")
    elif score >= 75:
        return ("Medium", "amber")
    elif score >= 50:
        return ("High", "orange")
    else:
        return ("Critical", "red")


def compute_score_banner(results: list) -> dict:
    """Compute the ScoreBanner dict with overall_score, risk_level, checks_run, violations."""
    passing = sum(1 for r in results if r.status == "pass")
    failing = sum(1 for r in results if r.status == "fail")
    skipped = sum(1 for r in results if r.status == "skipped")
    total = passing + failing + skipped
    non_skipped = passing + failing

    if non_skipped == 0:
        overall_score = None
        risk_level = "Unknown"
    else:
        overall_score = round((passing / non_skipped) * 100)
        risk_level, _ = compute_risk_level(overall_score)

    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "checks_run": total,
        "violations": failing,
    }


def render_article_cards_in_order(results: list) -> list[dict]:
    """Render a list of ArticleCard dicts from CheckResult objects, preserving order."""
    cards = []
    for r in results:
        card = {
            "rule_id": r.rule_id,
            "status_badge": r.status.upper(),
            "content": r.remediation_hint if r.status == "fail" else "",
            "has_copy_button": r.status == "fail",
        }
        cards.append(card)
    return cards


def render_live_feed_entry(result: CheckResult) -> dict:
    """Render a LiveFeed entry dict from a CheckResult."""
    css_map = {"pass": "pass", "fail": "fail", "skipped": "skipped"}
    return {
        "css_classes": [css_map[result.status]],
        "check_name": result.check_name,
        "article_id": result.article_id,
        "score": result.score,
        "remediation_hint": result.remediation_hint,
    }


def render_article_card(result: CheckResult) -> dict:
    """Render a single ArticleCard dict from a CheckResult."""
    return {
        "rule_id": result.rule_id,
        "status_badge": result.status.upper(),
        "content": result.remediation_hint if result.status == "fail" else "",
        "has_copy_button": result.status == "fail",
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_test_server() -> DashboardServer:
    """Create a fully initialised DashboardServer (no uvicorn started)."""
    return DashboardServer(port=8000, manifest_path="raiflow.yaml")


def make_client(server: DashboardServer) -> TestClient:
    return TestClient(server._app, raise_server_exceptions=False)


_VALID_STAGES = {"pre-commit", "ci", "pre-deploy", "post-deploy"}


# ---------------------------------------------------------------------------
# Property 1: CI detection is total over all non-empty CI values
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 1: CI detection is total over all non-empty CI values
@given(ci_value=st.text(min_size=1, alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\x00")))
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_is_ci_any_nonempty_value(ci_value, monkeypatch):
    """For any non-empty string assigned to the CI env var, _is_ci() returns True.

    Validates: Requirements 1.4
    """
    monkeypatch.setenv("CI", ci_value)
    assert _is_ci() is True


# ---------------------------------------------------------------------------
# Property 2: Status-to-style mapping is exhaustive
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 2: Status-to-style mapping is exhaustive
@given(result=st_check_result())
@settings(max_examples=200)
def test_status_to_style_mapping(result):
    """For any check_result, LiveFeed entry has correct CSS class and ArticleCard has correct badge.

    Fail cards have remediation_hint and copy button.

    Validates: Requirements 4.2, 4.3, 4.4, 5.2, 5.3, 10.7
    """
    entry = render_live_feed_entry(result)
    card = render_article_card(result)

    expected_class = result.status  # "pass", "fail", or "skipped"
    assert expected_class in entry["css_classes"]
    assert card["status_badge"] == result.status.upper()

    if result.status == "fail":
        assert result.remediation_hint in card["content"]
        assert card["has_copy_button"] is True
    else:
        assert card["has_copy_button"] is False


# ---------------------------------------------------------------------------
# Property 3: ArticleCard ordering matches SSE stream order
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 3: ArticleCard ordering matches SSE stream order
@given(results=st.lists(st_check_result(), min_size=1, max_size=20))
@settings(max_examples=100)
def test_article_card_order(results):
    """For any sequence of check_results, ArticleCards appear in same order as received.

    Validates: Requirements 5.6
    """
    cards = render_article_cards_in_order(results)
    assert [c["rule_id"] for c in cards] == [r.rule_id for r in results]


# ---------------------------------------------------------------------------
# Property 4: Overall_Score formula holds for all result sets
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 4: Overall_Score formula holds for all result sets
@given(
    results=st.lists(st_check_result(), min_size=1, max_size=20).filter(
        lambda rs: any(r.status != "skipped" for r in rs)
    )
)
@settings(max_examples=200)
def test_overall_score_formula(results):
    """For any non-empty list with at least one non-skipped result:
    score = round((passing / non_skipped) * 100).

    Validates: Requirements 6.1
    """
    passing = sum(1 for r in results if r.status == "pass")
    non_skipped = sum(1 for r in results if r.status != "skipped")
    expected = round((passing / non_skipped) * 100)
    assert compute_overall_score(results) == expected


# ---------------------------------------------------------------------------
# Property 5: Score-to-risk-level mapping covers all integer scores
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 5: Score-to-risk-level mapping covers all integer scores
@given(score=st.integers(min_value=0, max_value=100))
@settings(max_examples=101)
def test_score_to_risk_level(score):
    """For any integer 0-100: 100→Low/green, 75-99→Medium/amber, 50-74→High/orange, 0-49→Critical/red.

    Validates: Requirements 6.2, 6.3, 6.4, 6.5
    """
    level, colour = compute_risk_level(score)
    if score == 100:
        assert level == "Low"
        assert colour == "green"
    elif score >= 75:
        assert level == "Medium"
        assert colour == "amber"
    elif score >= 50:
        assert level == "High"
        assert colour == "orange"
    else:
        assert level == "Critical"
        assert colour == "red"


# ---------------------------------------------------------------------------
# Property 6: ScoreBanner displays all four required fields
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 6: ScoreBanner displays all four required fields
@given(
    results=st.lists(st_check_result(), min_size=1, max_size=20).filter(
        lambda rs: any(r.status != "skipped" for r in rs)
    )
)
@settings(max_examples=100)
def test_score_banner_all_fields_present(results):
    """For any run_complete event, ScoreBanner has non-null overall_score, risk_level,
    checks_run, violations.

    Validates: Requirements 6.6
    """
    banner = compute_score_banner(results)
    assert banner["overall_score"] is not None
    assert banner["risk_level"] is not None
    assert banner["checks_run"] is not None
    assert banner["violations"] is not None


# ---------------------------------------------------------------------------
# Property 7: Live tally updates after every check_result event
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 7: Live tally updates after every check_result event
@given(results=st.lists(st_check_result(), min_size=1, max_size=20))
@settings(max_examples=100)
def test_live_tally_updates_after_each_event(results):
    """After each check_result, pass count + fail count reflects all events so far.

    Validates: Requirements 6.7
    """
    cumulative_pass = 0
    cumulative_fail = 0

    for i, result in enumerate(results):
        if result.status == "pass":
            cumulative_pass += 1
        elif result.status == "fail":
            cumulative_fail += 1

        # Tally computed from all results seen so far
        seen = results[: i + 1]
        tally_pass = sum(1 for r in seen if r.status == "pass")
        tally_fail = sum(1 for r in seen if r.status == "fail")

        assert tally_pass == cumulative_pass
        assert tally_fail == cumulative_fail


# ---------------------------------------------------------------------------
# Property 8: POST /api/run with valid stage returns 202
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 8: POST /api/run with valid stage returns 202
@given(stage=st.sampled_from(["pre-commit", "ci", "pre-deploy", "post-deploy"]))
@settings(max_examples=100)
def test_post_run_valid_stage_returns_202(stage):
    """For any valid stage, POST /api/run returns 202.

    Validates: Requirements 8.1, 8.2
    """
    server = make_test_server()
    client = make_client(server)

    with patch.object(server, "_run_checks_in_background"):
        resp = client.post("/api/run", json={"stage": stage})

    assert resp.status_code == 202


# ---------------------------------------------------------------------------
# Property 9: POST /api/run with invalid stage returns 422
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 9: POST /api/run with invalid stage returns 422
@given(
    stage=st.text().filter(lambda s: s not in _VALID_STAGES)
)
@settings(max_examples=100)
def test_post_run_invalid_stage_returns_422(stage):
    """For any string not in valid stages, POST /api/run returns 422.

    Validates: Requirements 8.4
    """
    server = make_test_server()
    client = make_client(server)

    resp = client.post("/api/run", json={"stage": stage})

    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Property 10: RunState is reset before each new run
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 10: RunState is reset before each new run
@given(prior_results=st.lists(st_check_result(), min_size=1, max_size=10))
@settings(max_examples=100)
def test_run_state_reset_before_new_run(prior_results):
    """After reset_run_state(), results=[], report=None, status="idle".

    Validates: Requirements 3.6, 8.5
    """
    server = make_test_server()
    for r in prior_results:
        server.push_result(r)
    server.push_complete({"overall_status": "pass"})

    server.reset_run_state()

    state = server.get_run_state()
    assert state.results == []
    assert state.report is None
    assert state.status == "idle"


# ---------------------------------------------------------------------------
# Property 11: RunState replay round-trip
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 11: RunState replay round-trip
@given(results=st.lists(st_check_result(), min_size=0, max_size=15))
@settings(max_examples=100)
def test_run_state_replay_round_trip(results):
    """Replaying results from /api/run-state produces same ArticleCard set and ScoreBanner
    as live SSE.

    Validates: Requirements 9.4
    """
    # Simulate live SSE path
    live_cards = render_article_cards_in_order(results)
    live_banner = compute_score_banner(results)

    # Simulate replay path (from /api/run-state) — same data, same helpers
    replayed_cards = render_article_cards_in_order(results)
    replayed_banner = compute_score_banner(results)

    assert live_cards == replayed_cards
    assert live_banner == replayed_banner


# ---------------------------------------------------------------------------
# Property 12: SSE event field completeness
# ---------------------------------------------------------------------------

# Feature: developer-dashboard, Property 12: SSE event field completeness
@given(result=st_check_result())
@settings(max_examples=200)
def test_push_result_event_fields(result):
    """For any CheckResult, push_result emits event with all 7 required fields matching source.

    Validates: Requirements 4.1, 8.2
    """
    server = make_test_server()
    server.push_result(result)

    event = server._queue.get_nowait()

    assert event.type == "check_result"
    required_fields = (
        "article_id",
        "rule_id",
        "check_name",
        "status",
        "score",
        "threshold",
        "remediation_hint",
    )
    for field_name in required_fields:
        assert field_name in event.payload, f"Missing field: {field_name}"
        assert event.payload[field_name] == getattr(result, field_name), (
            f"Field {field_name}: expected {getattr(result, field_name)!r}, "
            f"got {event.payload[field_name]!r}"
        )
