import os
import json
import logging
from pathlib import Path
from fastapi import FastAPI, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator
from raiflow.analyzer import ProjectAnalyzer
from raiflow.reporter import ReportGenerator

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("raiflow")

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="RaiFlow Control Plane",
    description="Responsible AI Compliance monitoring and audit API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

BASE_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = BASE_DIR / "raiflow_audit_trail.json"
DASHBOARD_DIR = BASE_DIR / "raiflow" / "dashboard"


# ── Request models ────────────────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    path: str

    @field_validator("path")
    @classmethod
    def validate_path(cls, v: str) -> str:
        resolved = Path(v).resolve()
        # Restrict to paths under the workspace root
        workspace = BASE_DIR.resolve()
        try:
            resolved.relative_to(workspace)
        except ValueError:
            raise ValueError(f"Path must be within the workspace: {workspace}")
        if not resolved.exists():
            raise ValueError(f"Path does not exist: {resolved}")
        return str(resolved)


# ── Global error handler ──────────────────────────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.url}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# ── API Routes ────────────────────────────────────────────────────────────────

@app.get("/api/logs")
async def get_logs():
    """Return all audit trail events."""
    if not LOG_FILE.exists():
        return []
    try:
        with open(LOG_FILE, "r") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        logger.warning("Audit trail JSON is malformed — returning empty list.")
        return []
    except Exception as e:
        logger.error(f"Failed to read audit trail: {e}")
        raise HTTPException(status_code=500, detail="Failed to read audit trail")


@app.post("/api/analyze")
async def analyze_project(req: AnalyzeRequest):
    """Analyze a local project directory for AI compliance signals."""
    logger.info(f"Analyzing project at: {req.path}")
    try:
        analyzer = ProjectAnalyzer()
        info = analyzer.analyze_directory(req.path)
        from dataclasses import asdict
        return asdict(info)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Analysis failed")


@app.get("/api/export")
async def export_report():
    """Generate and return a markdown compliance report from the audit trail."""
    try:
        if not LOG_FILE.exists():
            return {"report": "No audit data yet. Run a compliance check first."}

        with open(LOG_FILE, "r") as f:
            logs = json.load(f)

        if not logs:
            return {"report": "Audit trail is empty."}

        analyzer = ProjectAnalyzer()
        info = analyzer.analyze_directory(str(BASE_DIR))
        from dataclasses import asdict

        report_md = ReportGenerator.generate_markdown(logs, asdict(info))
        return {"report": report_md}
    except Exception as e:
        logger.error(f"Export failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Report generation failed")


@app.get("/api/health")
async def health_check():
    """Simple health check endpoint."""
    return {
        "status": "ok",
        "audit_trail_exists": LOG_FILE.exists(),
        "dashboard_exists": DASHBOARD_DIR.exists(),
    }


@app.get("/api/frameworks")
async def list_frameworks():
    """List all available compliance frameworks."""
    try:
        from raiflow.framework_registry import list_available_frameworks
        frameworks = list_available_frameworks()
        return [
            {
                "id": f.id,
                "name": f.name,
                "description": f.description,
                "jurisdiction": f.jurisdiction,
                "version": f.version,
                "categories": f.categories or [],
            }
            for f in frameworks
        ]
    except Exception as e:
        logger.error(f"Failed to list frameworks: {e}")
        raise HTTPException(status_code=500, detail="Failed to list frameworks")


# ── Static files ──────────────────────────────────────────────────────────────

@app.get("/")
async def read_index():
    index = DASHBOARD_DIR / "index.html"
    if not index.exists():
        raise HTTPException(status_code=404, detail="Dashboard not found")
    return FileResponse(str(index), media_type="text/html")


if DASHBOARD_DIR.exists():
    app.mount("/src", StaticFiles(directory=str(DASHBOARD_DIR / "src")), name="src")
    app.mount("/dashboard", StaticFiles(directory=str(DASHBOARD_DIR), html=True), name="dashboard")


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    logger.info("--- RaiFlow Control Plane Starting ---")
    logger.info(f"Audit trail: {LOG_FILE}")
    logger.info(f"Dashboard:   {DASHBOARD_DIR}")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
