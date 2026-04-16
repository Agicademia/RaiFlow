"""Property-based tests for raiflow/manifest.py.

Validates: Requirements 1.6
"""

import tempfile
from pathlib import Path

import yaml
import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from raiflow.manifest import load_manifest, RaiFlowManifest

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_safe_text = st.text(
    alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_. "),
    min_size=1,
    max_size=40,
)

_risk_level = st.sampled_from(["high", "limited", "minimal"])

_article_id = st.sampled_from(
    ["Article 9", "Article 10", "Article 12", "Article 13", "Article 14"]
)

_model_metadata_strategy = st.fixed_dictionaries(
    {
        "name": _safe_text,
        "version": st.one_of(st.just(""), _safe_text),
        "disclosure_flag": st.booleans(),
    }
)

_logging_strategy = st.fixed_dictionaries({"middleware_active": st.booleans()})

_manifest_strategy = st.fixed_dictionaries(
    {
        "system_name": _safe_text,
        "risk_level": _risk_level,
        "eu_ai_act_articles": st.lists(_article_id, max_size=5),
        "model_metadata": _model_metadata_strategy,
        "logging": _logging_strategy,
        "risk_management": st.fixed_dictionaries(
            {"assessment_path": st.one_of(st.none(), _safe_text)}
        ),
        "oversight": st.fixed_dictionaries(
            {"override_endpoints": st.lists(_safe_text, max_size=3)}
        ),
        "data_governance": st.fixed_dictionaries(
            {
                "dataset_path": st.one_of(st.none(), _safe_text),
                "format": st.one_of(st.none(), st.sampled_from(["csv", "json", "parquet"])),
                "protected_attributes": st.lists(_safe_text, max_size=3),
            }
        ),
        "robustness": st.fixed_dictionaries(
            {
                "red_team_prompts_path": st.one_of(st.none(), _safe_text),
                "toxicity_threshold": st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            }
        ),
        "banned_models": st.lists(_safe_text, max_size=3),
    }
)


# ---------------------------------------------------------------------------
# Property 1: Round-trip parse → serialise → parse produces an equivalent object
# ---------------------------------------------------------------------------


@given(_manifest_strategy)
@settings(max_examples=50)
def test_manifest_round_trip(manifest_dict: dict) -> None:
    """Round-trip parse → serialise → parse produces an equivalent object.

    Validates: Requirements 1.6
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        first_path = Path(tmpdir) / "raiflow_first.yaml"
        second_path = Path(tmpdir) / "raiflow_second.yaml"

        # Write the raw dict to a YAML file and parse it
        with open(first_path, "w") as f:
            yaml.safe_dump(manifest_dict, f)

        first_manifest: RaiFlowManifest = load_manifest(str(first_path))

        # Serialise and write again, then parse a second time
        serialised = first_manifest.model_dump()
        with open(second_path, "w") as f:
            yaml.safe_dump(serialised, f)

        second_manifest: RaiFlowManifest = load_manifest(str(second_path))

        # Both parsed objects must be equivalent
        assert first_manifest.model_dump() == second_manifest.model_dump(), (
            "Round-trip produced a different manifest object.\n"
            f"First:  {first_manifest.model_dump()}\n"
            f"Second: {second_manifest.model_dump()}"
        )
