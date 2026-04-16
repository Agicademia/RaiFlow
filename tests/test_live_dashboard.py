"""Unit tests for the live-dashboard feature.

Covers: raiflow/cli.py (_is_ci, --dashboard flag), raiflow/dashboard_server.py
(RunState, push_result, push_complete, push_error, SSE keep-alive),
and raiflow/gate.py (run_streaming).

Requirements: 1.1, 1.3, 2.4, 2.5, 3.1, 3.3, 3.4, 3.5, 6.1, 6.2, 6.3, 7.2
"""

from __future__ import annotations

import queue as stdlib_queue
import sys
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from raiflow.cli import _is_ci, cli
from raiflow.dashboard_server import DashboardServer, RunState, SSE_Event
from raiflow.gate import CheckResult, CheckRunner


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server() -> DashboardServer:
    """Create a DashboardServer without starting uvicorn."""
    server = DashboardServer.__new__(DashboardServer)
    server._port = 8000
    server._actual_port = 8000
    server._run_state = RunState()
    server._queue = stdlib_queue.SimpleQueue()
    server._app = None
    server._server_thread = None
    return server


def _pass_result() -> CheckResult:
    return CheckResult(
        article_id="Article 13",
        rule_id="ART13-1",
        check_name="Transparency by Design",
        status="pass",
        score=1.0,
        threshold=1.0,
    )


def _mock_runner_cls(results):
    """Return a mock CheckRunner class whose .run() returns *results*."""
    mock_instance = MagicMock()
    mock_instance.run.return_value = results
    return MagicMock(return_value=mock_instance)


# ---------------------------------------------------------------------------
# CI detection
# ---------------------------------------------------------------------------

class TestIsCi:
    def test_is_ci_with_env_var(self, monkeypatch):
        """Requirement 6.1: _is_ci() returns True when CI=1."""
        monkeypatch.setenv("CI", "1")
        # Force isatty True so only the env-var branch is exercised
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        assert _is_ci() is True

    def test_is_ci_no_tty(self, monkeypatch):
        """Requirement 6.2: _is_ci() returns True when isatty() is False."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: False)
        assert _is_ci() is True

    def test_is_ci_false_with_tty_no_env(self, monkeypatch):
        """Requirement 6.3: _is_ci() returns False when TTY present and CI unset."""
        monkeypatch.delenv("CI", raising=False)
        monkeypatch.setattr(sys.stdout, "isatty", lambda: True)
        assert _is_ci() is False


# ---------------------------------------------------------------------------
# Dashboard flag suppression in CI
# ---------------------------------------------------------------------------

class TestDashboardFlagInCI:
    def test_dashboard_flag_ignored_in_ci(self, monkeypatch):
        """Requirement 1.3: suppression message emitted, no DashboardServer created."""
        monkeypatch.setenv("CI", "1")

        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner_cls([_pass_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"), \
             patch("raiflow.cli.DashboardServer") as mock_ds_cls:
            result = runner.invoke(cli, ["check", "--stage", "ci", "--dashboard"])

        # Suppression notice must appear in output
        assert "--dashboard ignored in CI environment" in result.output
        # DashboardServer must never be instantiated
        mock_ds_cls.assert_not_called()


# ---------------------------------------------------------------------------
# RunState initial state
# ---------------------------------------------------------------------------

class TestRunStateInitial:
    def test_run_state_initial(self):
        """Requirement 2.4: /api/run-state returns empty results and status='running' on startup."""
        server = _make_server()
        state = server.get_run_state()
        assert state.results == []
        assert state.status == "running"


# ---------------------------------------------------------------------------
# push_result
# ---------------------------------------------------------------------------

class TestPushResult:
    def test_push_result_appends_to_run_state(self):
        """Requirement 3.1: push_result grows RunState.results by one."""
        server = _make_server()
        assert len(server.get_run_state().results) == 0

        server.push_result(_pass_result())

        assert len(server.get_run_state().results) == 1


# ---------------------------------------------------------------------------
# push_complete
# ---------------------------------------------------------------------------

class TestPushComplete:
    def test_run_complete_event(self):
        """Requirement 3.3: exactly one run_complete event after push_complete; status=='complete'."""
        server = _make_server()
        report = {"overall_status": "pass"}
        server.push_complete(report)

        # Drain the queue
        events = []
        while True:
            try:
                events.append(server._queue.get_nowait())
            except stdlib_queue.Empty:
                break

        run_complete_events = [e for e in events if e.type == "run_complete"]
        assert len(run_complete_events) == 1
        assert server.get_run_state().status == "complete"


# ---------------------------------------------------------------------------
# push_error
# ---------------------------------------------------------------------------

class TestPushError:
    def test_run_error_event(self):
        """Requirement 3.4: run_error event emitted with correct message after push_error."""
        server = _make_server()
        error_msg = "Something went wrong"
        server.push_error(error_msg)

        events = []
        while True:
            try:
                events.append(server._queue.get_nowait())
            except stdlib_queue.Empty:
                break

        run_error_events = [e for e in events if e.type == "run_error"]
        assert len(run_error_events) == 1
        assert run_error_events[0].payload["message"] == error_msg


# ---------------------------------------------------------------------------
# Keep-alive format
# ---------------------------------------------------------------------------

class TestKeepaliveFormat:
    def test_keepalive_format(self):
        """Requirement 3.5: keep-alive comment is exactly ': ping\\n\\n'."""
        # Drive the async generator manually: patch time so the 15-second
        # threshold is immediately exceeded, then collect the first yielded value.
        import asyncio
        import time as time_module

        server = _make_server()

        async def _collect_one():
            # Monkey-patch monotonic so the ping fires on the first iteration
            original = time_module.monotonic
            time_module.monotonic = lambda: original() + 20  # > 15 s ahead
            try:
                gen = server._sse_generator()
                value = await gen.__anext__()
                await gen.aclose()
                return value
            finally:
                time_module.monotonic = original

        yielded = asyncio.run(_collect_one())
        assert yielded == ": ping\n\n"


# ---------------------------------------------------------------------------
# --dashboard-port without --dashboard
# ---------------------------------------------------------------------------

class TestPortIgnoredWithoutDashboard:
    def test_port_ignored_without_dashboard(self):
        """Requirement 7.2: --dashboard-port alone has no effect on CLI output."""
        runner = CliRunner()
        mock_manifest = MagicMock()
        mock_runner_cls = _mock_runner_cls([_pass_result()])

        with patch("raiflow.cli.load_manifest", return_value=mock_manifest), \
             patch("raiflow.cli.CheckRunner", mock_runner_cls), \
             patch("raiflow.cli.build_report", return_value={}), \
             patch("raiflow.cli.write_report"), \
             patch("raiflow.cli.DashboardServer") as mock_ds_cls:
            result = runner.invoke(
                cli, ["check", "--stage", "ci", "--dashboard-port", "9999"]
            )

        # DashboardServer must never be started
        mock_ds_cls.assert_not_called()
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# run_streaming
# ---------------------------------------------------------------------------

class TestRunStreaming:
    def test_run_streaming_calls_callback(self):
        """Requirement 1.1: run_streaming invokes callback once per check result."""
        manifest = MagicMock()
        manifest.model_metadata.name = "safe-model"
        manifest.banned_models = []
        manifest.model_metadata.disclosure_flag = True
        manifest.risk_management.assessment_path = None
        manifest.oversight.override_endpoints = []
        manifest.logging.middleware_active = True
        manifest.data_governance.dataset_path = None
        manifest.robustness.red_team_prompts_path = None
        manifest.robustness.toxicity_threshold = 0.1

        runner = CheckRunner(manifest)
        collected: list[CheckResult] = []

        results = runner.run_streaming("pre-commit", collected.append)

        # run_streaming must return the same results it passed to the callback
        assert len(collected) == len(results)
        assert collected == results
        # pre-commit stage runs exactly one check (banned model scan)
        assert len(results) == 1
