"""DashboardServer — FastAPI server for the live compliance dashboard.

Serves raiflow/dashboard/index.html, exposes /api/run-state and /api/events (SSE).
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import queue
import socket
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Literal, Optional

import requests
import uvicorn
from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel

from raiflow.gate import CheckResult, CheckRunner
from raiflow.manifest import load_manifest
from raiflow.reporter import build_report


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SSE_Event:
    type: str   # "check_result" | "run_complete" | "run_error"
    payload: dict


@dataclass
class RunState:
    results: List[dict] = field(default_factory=list)
    report: Optional[dict] = None
    status: str = "idle"          # "idle" | "running" | "complete" | "error"
    error_message: Optional[str] = None

    def reset(self) -> None:
        self.results.clear()
        self.report = None
        self.status = "idle"
        self.error_message = None


class RunRequest(BaseModel):
    stage: Literal["pre-commit", "ci", "pre-deploy", "post-deploy"]
    framework: Literal["eu_ai_act", "nist_ai_rmf", "iso_42001"] = "eu_ai_act"


# ---------------------------------------------------------------------------
# DashboardServer
# ---------------------------------------------------------------------------

_DASHBOARD_HTML = Path(__file__).parent / "dashboard" / "index.html"


class DashboardServer:
    def __init__(self, port: int = 8000, manifest_path: str = "raiflow.yaml") -> None:
        self._port = port
        self._actual_port: int = port
        self._manifest_path = manifest_path
        self._system_name: str = self._load_system_name()
        self._run_state = RunState()
        # Thread-safe queue for SSE events (used from sync push_* methods)
        self._queue: queue.SimpleQueue = queue.SimpleQueue()
        self._running_lock = threading.Lock()
        self._app = self._build_app()
        self._server_thread: Optional[threading.Thread] = None

    def _load_system_name(self) -> str:
        """Try to read system_name from the manifest; fall back gracefully."""
        try:
            return load_manifest(self._manifest_path).system_name
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # FastAPI app
    # ------------------------------------------------------------------

    def _build_app(self) -> FastAPI:
        app = FastAPI()

        @app.get("/")
        async def serve_index():
            return FileResponse(str(_DASHBOARD_HTML), media_type="text/html")

        @app.get("/raiflow-icon.svg")
        async def serve_icon():
            icon_path = Path(__file__).resolve().parent.parent / "docs" / "assets" / "raiflow-icon.png"
            if icon_path.exists():
                return FileResponse(str(icon_path), media_type="image/png")
            # fallback: serve the banner
            banner = Path(__file__).resolve().parent / "dashboard" / "raiflow-icon.png"
            return FileResponse(str(banner), media_type="image/png")

        @app.get("/api/run-state")
        async def run_state():
            data = dataclasses.asdict(self._run_state)
            data["system_name"] = self._system_name
            return data

        @app.get("/api/events")
        async def events():
            return StreamingResponse(
                self._sse_generator(),
                media_type="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "X-Accel-Buffering": "no",
                },
            )

        @app.post("/api/run", status_code=202)
        async def trigger_run(body: RunRequest):
            """Start CheckRunner.run_streaming in a background thread. Returns 202 or 409/422."""
            acquired = self._running_lock.acquire(blocking=False)
            if not acquired:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=409,
                    content={"error": "run already in progress"},
                )
            # Lock acquired — check if already running
            if self._run_state.status == "running":
                self._running_lock.release()
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=409,
                    content={"error": "run already in progress"},
                )
            self.reset_run_state()
            self._run_state.status = "running"
            t = threading.Thread(
                target=self._run_checks_in_background,
                args=(body.stage, body.framework),
                daemon=True,
            )
            t.start()
            return {"status": "accepted"}

        return app

    async def _sse_generator(self):
        """Drain the queue and yield SSE-formatted strings; send keep-alive every 15 s."""
        last_ping = time.monotonic()
        try:
            while True:
                # Drain all pending events
                while True:
                    try:
                        event: SSE_Event = self._queue.get_nowait()
                        data = json.dumps(event.payload)
                        yield f"event: {event.type}\ndata: {data}\n\n"
                    except queue.Empty:
                        break

                # Keep-alive ping every 15 seconds
                now = time.monotonic()
                if now - last_ping >= 15:
                    yield ": ping\n\n"
                    last_ping = now

                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            pass

    # ------------------------------------------------------------------
    # Run management
    # ------------------------------------------------------------------

    def reset_run_state(self) -> None:
        """Clear RunState and drain the event queue for a fresh run."""
        self._run_state.reset()
        # Drain any pending events from the queue
        while True:
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

    def _run_checks_in_background(self, stage: str, framework: str = "eu_ai_act") -> None:
        """Target for the background thread: runs CheckRunner, pushes results."""
        try:
            manifest = load_manifest(self._manifest_path)
            # Framework selection: only eu_ai_act is fully implemented; others are stubs
            if framework != "eu_ai_act":
                self.push_error(
                    f"Framework '{framework}' is not yet implemented. "
                    f"Only 'eu_ai_act' is supported in this version."
                )
                return
            runner = CheckRunner(manifest)
            results = runner.run_streaming(stage, on_result=self.push_result)
            report = build_report(stage=stage, manifest=manifest, checks=results)
            self.push_complete(report)
        except Exception as exc:
            self.push_error(str(exc))
        finally:
            self._running_lock.release()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> int:
        """Start uvicorn in a daemon thread. Returns the actual bound port."""
        port = self._port
        for attempt in range(11):
            if attempt == 10:
                raise OSError(
                    f"Could not bind to any port in range {self._port}–{self._port + 9}"
                )
            if self._port_available(port):
                break
            port += 1

        self._actual_port = port
        print(f"Dashboard server starting on http://127.0.0.1:{port}/", file=sys.stderr)

        config = uvicorn.Config(
            self._app,
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
        server = uvicorn.Server(config)

        def _run():
            server.run()

        t = threading.Thread(target=_run, daemon=True)
        t.start()
        self._server_thread = t
        return port

    @staticmethod
    def _port_available(port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False

    def wait_ready(self, timeout: float = 5.0) -> bool:
        """Poll /api/run-state until the server responds or timeout expires."""
        url = f"http://127.0.0.1:{self._actual_port}/api/run-state"
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                resp = requests.get(url, timeout=0.5)
                if resp.status_code == 200:
                    return True
            except Exception:
                pass
            time.sleep(0.1)
        return False

    def serve_forever(self) -> None:
        """Block until KeyboardInterrupt (used by cli.py after run completes)."""
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            pass

    # ------------------------------------------------------------------
    # Push methods
    # ------------------------------------------------------------------

    def push_result(self, result: CheckResult) -> None:
        """Append serialised CheckResult to RunState and enqueue a check_result SSE_Event."""
        payload = {
            "article_id": result.article_id,
            "rule_id": result.rule_id,
            "check_name": result.check_name,
            "status": result.status,
            "score": result.score,
            "threshold": result.threshold,
            "remediation_hint": result.remediation_hint,
        }
        self._run_state.results.append(payload)
        self._queue.put(SSE_Event(type="check_result", payload=payload))

    def push_complete(self, report: dict) -> None:
        """Set RunState.report and status='complete', enqueue run_complete event."""
        self._run_state.report = report
        self._run_state.status = "complete"
        self._queue.put(SSE_Event(type="run_complete", payload=report))

    def push_error(self, message: str) -> None:
        """Set RunState.error_message and status='error', enqueue run_error event."""
        self._run_state.error_message = message
        self._run_state.status = "error"
        self._queue.put(SSE_Event(type="run_error", payload={"message": message}))

    # ------------------------------------------------------------------
    # Accessors
    # ------------------------------------------------------------------

    def get_run_state(self) -> RunState:
        """Return the current RunState."""
        return self._run_state

    def get_exit_code(self) -> int:
        """Return 0 if all checks passed, 1 if any failed."""
        for result in self._run_state.results:
            if result.get("status") == "fail":
                return 1
        return 0
