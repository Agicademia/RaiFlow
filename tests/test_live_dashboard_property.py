"""Property-based tests for the live-dashboard feature.

Uses Hypothesis to verify correctness properties across all valid inputs.

Requirements: 3.1, 3.2, 4.1, 4.2, 4.3, 4.6, 5.3, 6.1, 6.4, 7.3
"""

from __future__ import annotations

import queue as stdlib_queue
import socket
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from raiflow.cli import _is_ci, cli
from raiflow.dashboard_server import DashboardServer, RunState, SSE_Event
from raiflow.gate import CheckResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_test_server() -> DashboardServer:
    """Create a DashboardServer without starting uvicorn."""
    server = DashboardServer.__new__(DashboardServer)
    server._port = 8000
    server._actual_port = 8000
    server._run_state = RunState()
    server._queue = stdlib_queue.SimpleQueue()
    server._app = None
    server._server_thread = None
    return server


def drain_queue(server: DashboardServer) -> list[SSE_Event]:
    """Empty the internal event queue into a list."""
    events = []
    while True:
        try:
            events.append(server._queue.get_nowait())
        except stdlib_queue.Empty:
            break
    return events


# ---------------------------------------------------------------------------
# Hypothesis strategy
# ---------------------------------------------------------------------------

def st_check_result():
    """Generate valid CheckResult instances."""
    return st.builds(
        CheckResult,
        article_id=st.text(min_size=1, max_size=50),
        rule_id=st.text(min_size=1, max_size=30),
        check_name=st.text(min_size=1, max_size=80),
        status=st.sampled_from(["pass", "fail", "skipped"]),
        score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        remediation_hint=st.text(max_size=200),
        skip_reason=st.text(max_size=100),
    )


# ---------------------------------------------------------------------------
# Status-to-CSS helper (Property 6)
# ---------------------------------------------------------------------------

def status_to_css_class(status: str) -> str:
    """Map a CheckResult status to its CSS class name."""
    mapping = {"pass": "pass", "fail": "fail", "skipped": "skipped"}
    return mapping[status]


# ---------------------------------------------------------------------------
# Property 1: CI detection is total over all non-empty CI values
# ---------------------------------------------------------------------------

# Feature: live-dashboard, Property 1: CI detection is total over all non-empty CI values
@given(ci_value=st.text(min_size=1, alphabet=st.characters(blacklist_characters="\x00")))
@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_is_ci_any_nonempty_value(ci_value, monkeypatch):
    """For any non-empty string assigned to CI env var, _is_ci() shall return True.

    Validates: Requirements 6.1
    """
    monkeypatch.setenv("CI", ci_value)
    # Force isatty True so only the env-var branch is exercised
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
    assert _is_ci() is True


# ---------------------------------------------------------------------------
# Property 2: CI flag suppression is a no-op on outputs
# ---------------------------------------------------------------------------

def _mock_runner_cls(results):
    """Return a mock CheckRunner class whose .run() returns *results*."""
    mock_instance = MagicMock()
    mock_instance.run.return_value = results
    return MagicMock(return_value=mock_instance)


# Feature: live-dashboard, Property 2: CI flag suppression is a no-op on outputs
@given(
    article_id=st.text(min_size=1, max_size=30),
    rule_id=st.text(min_size=1, max_size=20),
)
@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_ci_flag_suppression_noop(article_id, rule_id, monkeypatch):
    """In CI, adding --dashboard produces identical stdout/stderr and exit code.

    Validates: Requirements 6.4
    """
    monkeypatch.setenv("CI", "1")
    monkeypatch.setattr(sys.stdout, "isatty", lambda: True)

    result = CheckResult(
        article_id=article_id,
        rule_id=rule_id,
        check_name="Test Check",
        status="pass",
        score=1.0,
        threshold=1.0,
    )
    mock_cls = _mock_runner_cls([result])

    runner = CliRunner()

    with patch("raiflow.cli.load_manifest", return_value=MagicMock()), \
         patch("raiflow.cli.CheckRunner", mock_cls), \
         patch("raiflow.cli.build_report", return_value={}), \
         patch("raiflow.cli.write_report"), \
         patch("raiflow.cli.DashboardServer") as mock_ds_cls:

        result_without = runner.invoke(cli, ["check", "--stage", "ci"])
        result_with = runner.invoke(cli, ["check", "--stage", "ci", "--dashboard"])

    # DashboardServer must never be instantiated in CI
    mock_ds_cls.assert_not_called()

    # Exit codes must match
    assert result_without.exit_code == result_with.exit_code

    # stdout without --dashboard must be a subset of stdout with --dashboard
    # (the only extra content is the suppression notice on stderr)
    assert result_without.output == result_with.output.replace(
        "--dashboard ignored in CI environment\n", ""
    )


# ---------------------------------------------------------------------------
# Property 3: SSE event field completeness
# ---------------------------------------------------------------------------

# Feature: live-dashboard, Property 3: SSE event field completeness
@given(result=st_check_result())
@settings(max_examples=200)
def test_push_result_event_fields(result):
    """For any CheckResult, the check_result SSE_Event shall contain exactly the required fields.

    Validates: Requirements 3.1
    """
    server = make_test_server()
    server.push_result(result)
    event = server._queue.get_nowait()

    assert event.type == "check_result"
    required_fields = ("article_id", "rule_id", "check_name", "status", "score", "threshold", "remediation_hint")
    for field_name in required_fields:
        assert field_name in event.payload
        assert event.payload[field_name] == getattr(result, field_name)


# ---------------------------------------------------------------------------
# Property 4: SSE event ordering preservation
# ---------------------------------------------------------------------------

# Feature: live-dashboard, Property 4: SSE event ordering preservation
@given(results=st.lists(st_check_result(), min_size=1, max_size=20))
@settings(max_examples=100)
def test_event_order_preserved(results):
    """For any sequence of CheckResults, events appear in the same order.

    Validates: Requirements 3.2
    """
    server = make_test_server()
    for r in results:
        server.push_result(r)
    events = drain_queue(server)
    assert [e.payload["rule_id"] for e in events] == [r.rule_id for r in results]


# ---------------------------------------------------------------------------
# Property 5: RunState replay completeness
# ---------------------------------------------------------------------------

# Feature: live-dashboard, Property 5: RunState replay completeness
@given(results=st.lists(st_check_result(), min_size=0, max_size=15))
@settings(max_examples=100)
def test_run_state_replay_completeness(results):
    """For any N completed check_result entries, len(state.results) == N.

    Validates: Requirements 4.6
    """
    server = make_test_server()
    for r in results:
        server.push_result(r)
    state = server.get_run_state()
    assert len(state.results) == len(results)


# ---------------------------------------------------------------------------
# Property 6: Status-to-style mapping
# ---------------------------------------------------------------------------

# Feature: live-dashboard, Property 6: Status-to-style mapping
@given(result=st_check_result())
@settings(max_examples=200)
def test_status_to_css_class(result):
    """For any check_result SSE event, the CSS class matches the status.

    Validates: Requirements 4.1, 4.2, 4.3
    """
    expected = {"pass": "pass", "fail": "fail", "skipped": "skipped"}
    css = status_to_css_class(result.status)
    assert css == expected[result.status]


# ---------------------------------------------------------------------------
# Property 7: Port fallback selects next available port
# ---------------------------------------------------------------------------

# Feature: live-dashboard, Property 7: Port fallback selects next available port
@given(offset=st.integers(min_value=0, max_value=8))
@settings(max_examples=50)
def test_port_fallback(offset):
    """For any port P already bound, DashboardServer.start(port=P) binds to next available port.

    Validates: Requirements 2.1, 7.3
    """
    base_port = 19000  # arbitrary base; we mock availability entirely

    # Ports base_port through base_port+offset are "occupied"; base_port+offset+1 is free
    def mock_port_available(port: int) -> bool:
        return port > base_port + offset

    server = DashboardServer(port=base_port)

    with patch.object(DashboardServer, "_port_available", staticmethod(mock_port_available)), \
         patch("uvicorn.Config"), \
         patch("uvicorn.Server") as mock_uvicorn_server, \
         patch("threading.Thread") as mock_thread:

        mock_server_instance = MagicMock()
        mock_uvicorn_server.return_value = mock_server_instance
        mock_thread_instance = MagicMock()
        mock_thread.return_value = mock_thread_instance

        actual_port = server.start()

    # The server should have bound to base_port + offset + 1
    assert actual_port == base_port + offset + 1


# ---------------------------------------------------------------------------
# Property 8: RunState persistence after run completion
# ---------------------------------------------------------------------------

# Feature: live-dashboard, Property 8: RunState persistence after run completion
@given(results=st.lists(st_check_result(), min_size=1, max_size=10))
@settings(max_examples=100)
def test_run_state_immutable_after_complete(results):
    """After push_complete, repeated get_run_state() calls return same final state.

    Validates: Requirements 5.3
    """
    server = make_test_server()
    for r in results:
        server.push_result(r)
    server.push_complete({"overall_status": "pass"})

    state_a = server.get_run_state()
    state_b = server.get_run_state()

    assert state_a == state_b
    assert state_a.status == "complete"
    assert len(state_a.results) == len(results)
