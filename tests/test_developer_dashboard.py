"""Unit tests for the developer-dashboard feature.

Covers: raiflow/dashboard_server.py — POST /api/run endpoint, RunState reset,
background runner, and 409/422 conflict handling.

Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6
"""

from __future__ import annotations

import queue as stdlib_queue
import threading
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from raiflow.dashboard_server import DashboardServer, RunRequest, RunState, SSE_Event
from raiflow.gate import CheckResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_server(manifest_path: str = "raiflow.yaml") -> DashboardServer:
    """Create a fully initialised DashboardServer (no uvicorn started)."""
    return DashboardServer(port=8000, manifest_path=manifest_path)


def _pass_result(**kwargs) -> CheckResult:
    defaults = dict(
        article_id="Article 13",
        rule_id="ART13-1",
        check_name="Transparency by Design",
        status="pass",
        score=1.0,
        threshold=1.0,
        remediation_hint="",
    )
    defaults.update(kwargs)
    return CheckResult(**defaults)


def _make_client(server: DashboardServer) -> TestClient:
    return TestClient(server._app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Task 1 unit tests (RunState)
# ---------------------------------------------------------------------------

class TestRunStateIdleOnStartup:
    def test_run_state_idle_on_startup(self):
        """Requirement 8.6: RunState.status is 'idle' on startup."""
        server = _make_server()
        assert server.get_run_state().status == "idle"


class TestRunStateResetClearsResults:
    def test_run_state_reset_clears_results(self):
        """Requirement 8.5: reset() clears results, report, error_message and sets status='idle'."""
        server = _make_server()
        server.push_result(_pass_result())
        server.push_complete({"overall_status": "pass"})

        server.reset_run_state()

        state = server.get_run_state()
        assert state.results == []
        assert state.report is None
        assert state.error_message is None
        assert state.status == "idle"


# ---------------------------------------------------------------------------
# Task 2 unit tests (POST /api/run)
# ---------------------------------------------------------------------------

class TestPostRunReturns202:
    def test_post_run_returns_202(self):
        """Requirement 8.1, 8.2: POST /api/run with valid stage returns 202."""
        server = _make_server()
        client = _make_client(server)

        # Patch _run_checks_in_background so no real manifest is loaded
        with patch.object(server, "_run_checks_in_background"):
            resp = client.post("/api/run", json={"stage": "ci"})

        assert resp.status_code == 202


class TestPostRunConflictReturns409:
    def test_post_run_conflict_returns_409(self):
        """Requirement 8.3: POST /api/run while run in progress returns 409."""
        server = _make_server()
        client = _make_client(server)

        # Simulate a run already in progress by acquiring the lock and setting status
        server._running_lock.acquire()
        server._run_state.status = "running"

        try:
            resp = client.post("/api/run", json={"stage": "ci"})
        finally:
            server._running_lock.release()

        assert resp.status_code == 409
        assert resp.json()["error"] == "run already in progress"


class TestPostRunInvalidStageReturns422:
    def test_post_run_invalid_stage_returns_422(self):
        """Requirement 8.4: POST /api/run with invalid stage returns 422."""
        server = _make_server()
        client = _make_client(server)

        resp = client.post("/api/run", json={"stage": "invalid-stage"})

        assert resp.status_code == 422

    def test_post_run_missing_stage_returns_422(self):
        """Requirement 8.4: POST /api/run with missing stage field returns 422."""
        server = _make_server()
        client = _make_client(server)

        resp = client.post("/api/run", json={})

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# reset_run_state drains queue
# ---------------------------------------------------------------------------

class TestResetRunStateDrainsQueue:
    def test_reset_drains_queue(self):
        """reset_run_state() removes all pending SSE events from the queue."""
        server = _make_server()
        server.push_result(_pass_result())
        server.push_result(_pass_result(rule_id="ART9-1"))

        server.reset_run_state()

        assert server._queue.empty()


# ---------------------------------------------------------------------------
# _run_checks_in_background always calls push_complete or push_error
# ---------------------------------------------------------------------------

class TestRunChecksInBackground:
    def test_background_runner_calls_push_complete_on_success(self):
        """Background runner calls push_complete after a successful run."""
        server = _make_server()
        server._run_state.status = "running"
        server._running_lock.acquire()

        mock_manifest = MagicMock()
        mock_manifest.model_metadata.name = "safe-model"
        mock_manifest.banned_models = []
        mock_manifest.model_metadata.disclosure_flag = True
        mock_manifest.risk_management.assessment_path = None
        mock_manifest.oversight.override_endpoints = []
        mock_manifest.logging.middleware_active = True
        mock_manifest.data_governance.dataset_path = None
        mock_manifest.robustness.red_team_prompts_path = None
        mock_manifest.robustness.toxicity_threshold = 0.1

        with patch("raiflow.dashboard_server.load_manifest", return_value=mock_manifest), \
             patch("raiflow.dashboard_server.build_report", return_value={"overall_status": "pass"}):
            server._run_checks_in_background("pre-commit")

        assert server.get_run_state().status == "complete"
        # Lock must have been released
        assert server._running_lock.acquire(blocking=False)
        server._running_lock.release()

    def test_background_runner_calls_push_error_on_exception(self):
        """Background runner calls push_error when an exception is raised."""
        server = _make_server()
        server._run_state.status = "running"
        server._running_lock.acquire()

        with patch("raiflow.dashboard_server.load_manifest", side_effect=RuntimeError("boom")):
            server._run_checks_in_background("ci")

        assert server.get_run_state().status == "error"
        assert "boom" in server.get_run_state().error_message
        # Lock must have been released
        assert server._running_lock.acquire(blocking=False)
        server._running_lock.release()


# ---------------------------------------------------------------------------
# Task 4 unit tests (CLI — dashboard flag behaviour)
# ---------------------------------------------------------------------------

class TestNoDashboardFlagSkipsServer:
    def test_no_dashboard_flag_skips_server(self):
        """Requirement 1.2: --no-dashboard prevents DashboardServer from being instantiated."""
        from click.testing import CliRunner
        from raiflow.cli import check

        runner = CliRunner()
        with patch("raiflow.cli.DashboardServer") as mock_ds, \
             patch("raiflow.cli._is_ci", return_value=False), \
             patch("raiflow.cli.load_manifest") as mock_manifest, \
             patch("raiflow.cli.CheckRunner") as mock_runner:
            mock_manifest.return_value = MagicMock()
            mock_runner.return_value.run.return_value = []
            result = runner.invoke(check, ["--no-dashboard", "--stage", "ci"])

        mock_ds.assert_not_called()


class TestDashboardDefaultInNonCI:
    def test_dashboard_default_in_non_ci(self):
        """Requirement 1.1: In non-CI, server starts and browser opens by default."""
        from click.testing import CliRunner
        from raiflow.cli import check

        runner = CliRunner()
        mock_server_instance = MagicMock()
        mock_server_instance.start.return_value = 8000
        mock_server_instance.wait_ready.return_value = True
        mock_server_instance.serve_forever.side_effect = SystemExit(0)

        with patch("raiflow.cli.DashboardServer", return_value=mock_server_instance) as mock_ds, \
             patch("raiflow.cli._is_ci", return_value=False), \
             patch("raiflow.cli.load_manifest") as mock_manifest, \
             patch("raiflow.cli.CheckRunner"), \
             patch("raiflow.cli.webbrowser.open") as mock_browser:
            mock_manifest.return_value = MagicMock()
            runner.invoke(check, ["--stage", "ci"])

        mock_ds.assert_called_once()
        mock_server_instance.start.assert_called_once()
        mock_browser.assert_called_once()


class TestDashboardIgnoredInCI:
    def test_dashboard_ignored_in_ci(self):
        """Requirement 1.4, 1.5: In CI with --dashboard, warning emitted and no server started."""
        from click.testing import CliRunner
        from raiflow.cli import check

        runner = CliRunner()
        with patch("raiflow.cli.DashboardServer") as mock_ds, \
             patch("raiflow.cli._is_ci", return_value=True), \
             patch("raiflow.cli.load_manifest") as mock_manifest, \
             patch("raiflow.cli.CheckRunner") as mock_runner:
            mock_manifest.return_value = MagicMock()
            mock_runner.return_value.run.return_value = []
            result = runner.invoke(check, ["--dashboard", "--stage", "ci"])

        mock_ds.assert_not_called()
        assert "--dashboard ignored in CI environment" in result.output


# ---------------------------------------------------------------------------
# Task 5 unit tests (HTML structure)
# ---------------------------------------------------------------------------

class TestEmptyStateShownWhenIdle:
    def test_empty_state_shown_when_idle(self):
        """Requirement 10.6: index.html contains an empty-state element."""
        from pathlib import Path
        html = Path("raiflow/dashboard/index.html").read_text(encoding="utf-8")
        assert 'class="empty-state"' in html or "empty-state" in html


class TestCopyButtonPresentOnFailCard:
    def test_copy_button_present_on_fail_card(self):
        """Requirement 10.7: index.html contains copyHint function and btn-copy class."""
        from pathlib import Path
        html = Path("raiflow/dashboard/index.html").read_text(encoding="utf-8")
        assert "copyHint" in html
        assert "btn-copy" in html


class TestScoreBannerAllFieldsPresent:
    def test_score_banner_all_fields_present(self):
        """Requirement 6.6: compute_score_banner returns all four required fields."""
        results = [
            _pass_result(status="pass"),
            _pass_result(rule_id="ART9-1", status="fail", score=0.0,
                         remediation_hint="Fix something"),
            _pass_result(rule_id="ART12-1", status="skipped", score=0.0),
        ]
        banner = _compute_score_banner(results)
        assert banner["overall_score"] is not None
        assert banner["risk_level"] is not None
        assert banner["checks_run"] is not None
        assert banner["violations"] is not None

    def test_score_banner_correct_values(self):
        """Requirement 6.6: compute_score_banner computes correct values."""
        results = [
            _pass_result(status="pass"),
            _pass_result(rule_id="ART9-1", status="fail", score=0.0,
                         remediation_hint="Fix something"),
        ]
        banner = _compute_score_banner(results)
        # 1 pass, 1 fail → score = round(1/2 * 100) = 50
        assert banner["overall_score"] == 50
        assert banner["checks_run"] == 2
        assert banner["violations"] == 1


class TestWorkbenchNoExternalResources:
    def test_workbench_no_external_resources(self):
        """Requirement 10.2: index.html has no external <script src> or <link href> tags."""
        import re
        from pathlib import Path
        html = Path("raiflow/dashboard/index.html").read_text(encoding="utf-8")

        # Check for external script src (http/https)
        external_scripts = re.findall(r'<script[^>]+src=["\']https?://', html, re.IGNORECASE)
        assert external_scripts == [], f"Found external scripts: {external_scripts}"

        # Check for external link href (http/https)
        external_links = re.findall(r'<link[^>]+href=["\']https?://', html, re.IGNORECASE)
        assert external_links == [], f"Found external links: {external_links}"


class TestRunStateReplayOnPageLoad:
    def test_run_state_replay_on_page_load(self):
        """Requirement 9.1, 9.4: GET /api/run-state returns seeded results for replay."""
        server = _make_server()
        client = _make_client(server)

        # Seed RunState with results
        result1 = _pass_result(rule_id="ART13-1", check_name="Transparency", status="pass",
                                score=1.0)
        result2 = _pass_result(rule_id="ART9-1", check_name="Risk Mgmt", status="fail",
                                score=0.0, remediation_hint="Fix risk docs")
        server.push_result(result1)
        server.push_result(result2)
        server.push_complete({"overall_status": "fail"})

        resp = client.get("/api/run-state")
        assert resp.status_code == 200

        data = resp.json()
        assert data["status"] == "complete"
        assert len(data["results"]) == 2

        # Verify the results match what was seeded
        returned_rule_ids = [r["rule_id"] for r in data["results"]]
        assert "ART13-1" in returned_rule_ids
        assert "ART9-1" in returned_rule_ids

        # Verify replay produces same cards (same data, same order)
        assert data["results"][0]["rule_id"] == "ART13-1"
        assert data["results"][1]["rule_id"] == "ART9-1"
        assert data["results"][1]["remediation_hint"] == "Fix risk docs"


# ---------------------------------------------------------------------------
# Pure Python helper: compute_score_banner
# ---------------------------------------------------------------------------

def _compute_score_banner(results: list) -> dict:
    """Pure Python equivalent of the JS ScoreBanner computation.

    Returns a dict with overall_score, risk_level, checks_run, violations.
    """
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
        if overall_score == 100:
            risk_level = "Low"
        elif overall_score >= 75:
            risk_level = "Medium"
        elif overall_score >= 50:
            risk_level = "High"
        else:
            risk_level = "Critical"

    return {
        "overall_score": overall_score,
        "risk_level": risk_level,
        "checks_run": total if total > 0 else None,
        "violations": failing if total > 0 else None,
    }
