"""Property-based test for TestGenerator generate -> run -> pass round-trip.

**Validates: Requirements 4.5**
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st

from raiflow.generator import TestGenerator

# Workspace root so generated tests can import raiflow
_WORKSPACE_ROOT = str(Path(__file__).parent.parent.resolve())

# ---------------------------------------------------------------------------
# Minimal compliant raiflow.yaml content
# ---------------------------------------------------------------------------

_COMPLIANT_MANIFEST = {
    "system_name": "Test System",
    "risk_level": "high",
    "eu_ai_act_articles": ["Article 9", "Article 10", "Article 12", "Article 13", "Article 14"],
    "model_metadata": {
        "name": "test-model",
        "version": "1.0.0",
        "disclosure_flag": True,
    },
    "logging": {"middleware_active": True},
    "risk_management": {"assessment_path": None},
    "oversight": {"override_endpoints": []},
    "data_governance": {
        "dataset_path": None,
        "format": None,
        "protected_attributes": [],
    },
    "robustness": {
        "red_team_prompts_path": None,
        "toxicity_threshold": 0.7,
    },
    "banned_models": [],
}

# ---------------------------------------------------------------------------
# Property 3: Generated test files for a compliant project exit pytest with code 0
# ---------------------------------------------------------------------------


@given(st.just(None))
@settings(max_examples=1, suppress_health_check=[HealthCheck.too_slow], deadline=None)
def test_generate_run_pass_round_trip(_: None) -> None:
    """Generated article test files for a compliant project exit pytest with code 0.

    **Validates: Requirements 4.5**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Write a compliant raiflow.yaml into the temp dir
        manifest_path = tmp / "raiflow.yaml"
        with open(manifest_path, "w") as f:
            yaml.safe_dump(_COMPLIANT_MANIFEST, f)

        # Generate test files into a sub-directory of the temp dir
        gen_dir = tmp / "generated"
        gen = TestGenerator("policies/eu_ai_act.yaml")
        gen.generate(str(gen_dir))

        # Collect only article test files (skip logging and bias which need extra setup)
        article_files = sorted(gen_dir.glob("test_article_*.py"))
        assert article_files, "TestGenerator must produce at least one article test file"

        for test_file in article_files:
            env = os.environ.copy()
            env["PYTHONPATH"] = _WORKSPACE_ROOT + os.pathsep + env.get("PYTHONPATH", "")
            result = subprocess.run(
                [sys.executable, "-m", "pytest", str(test_file), "--tb=short", "-q"],
                cwd=str(tmp),
                capture_output=True,
                text=True,
                env=env,
            )
            assert result.returncode == 0, (
                f"Generated test file {test_file.name} failed with exit code "
                f"{result.returncode}.\n"
                f"stdout:\n{result.stdout}\n"
                f"stderr:\n{result.stderr}"
            )
