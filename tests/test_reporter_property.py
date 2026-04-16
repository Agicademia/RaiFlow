"""Property-based tests for raiflow/reporter.py.

**Validates: Requirements 9.3**
"""

import json
import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from raiflow.reporter import write_report

# ---------------------------------------------------------------------------
# Strategies — generate valid report dicts matching the v1.0 schema
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_. "),
    min_size=1,
    max_size=40,
)

_status = st.sampled_from(["pass", "fail", "skipped"])

_check_entry = st.fixed_dictionaries(
    {
        "article_id": _safe_text,
        "rule_id": _safe_text,
        "check_name": _safe_text,
        "status": _status,
        "score": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        "threshold": st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        "remediation_hint": st.one_of(st.just(""), _safe_text),
    }
)

_report_strategy = st.fixed_dictionaries(
    {
        "schema_version": st.just("1.0"),
        "generated_at": _safe_text,
        "git_sha": _safe_text,
        "stage": st.sampled_from(["pre-commit", "ci", "pre-deploy", "post-deploy"]),
        "system_name": _safe_text,
        "overall_status": st.sampled_from(["pass", "fail"]),
        "checks": st.lists(_check_entry, max_size=5),
    }
)


# ---------------------------------------------------------------------------
# Property 2: Deserialise → re-serialise produces byte-identical JSON
# ---------------------------------------------------------------------------


@given(_report_strategy)
@settings(max_examples=50)
def test_report_round_trip_serialisation(report: dict) -> None:
    """Deserialise → re-serialise produces byte-identical JSON.

    **Validates: Requirements 9.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "report.json"

        # Write the report to disk using write_report
        write_report(report, str(output_path))

        # Read it back and re-serialise with the same settings
        with open(output_path) as f:
            loaded = json.load(f)

        re_serialised = json.dumps(loaded, indent=2, sort_keys=True)

        # The file on disk must be byte-identical to the re-serialised form
        on_disk = output_path.read_text()
        assert on_disk == re_serialised, (
            "Round-trip produced different bytes.\n"
            f"On disk:\n{on_disk}\n\nRe-serialised:\n{re_serialised}"
        )
