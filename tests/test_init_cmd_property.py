"""Property-based tests for raiflow/scanner.py (raiflow-init feature).

**Validates: Requirements 1.1, 1.2, 1.3, 2.1, 2.2, 2.3**
"""

import tempfile
from pathlib import Path

from hypothesis import given, settings
from hypothesis import strategies as st

from raiflow.scanner import (
    ALL_FRAMEWORKS,
    EXCLUDED_DIRS,
    HIGH_RISK_FRAMEWORKS,
    LIMITED_RISK_FRAMEWORKS,
    DetectionResult,
    infer_risk_level,
    scan_directory,
)

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_framework = st.sampled_from(ALL_FRAMEWORKS)
_high_framework = st.sampled_from(HIGH_RISK_FRAMEWORKS)
_limited_framework = st.sampled_from(LIMITED_RISK_FRAMEWORKS)
_excluded_dir = st.sampled_from(sorted(EXCLUDED_DIRS))

# Safe extra text that won't accidentally contain import lines for known frameworks
_safe_extra = st.text(
    alphabet=st.characters(
        whitelist_categories=("Lu", "Ll", "Nd"),
        whitelist_characters=" _-#\n",
    ),
    max_size=80,
)


# ---------------------------------------------------------------------------
# Property 1: Scanner excludes known directories
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 1: Scanner excludes known directories
@given(excluded_dir=_excluded_dir, framework=_framework)
@settings(max_examples=100)
def test_scanner_excludes_known_dirs(excluded_dir: str, framework: str) -> None:
    """For any directory tree containing .py files inside excluded directories,
    scan_directory shall not include any framework detected exclusively from those
    excluded paths.

    **Validates: Requirements 1.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        # Place a .py file with a framework import ONLY inside the excluded directory
        excluded_subdir = root / excluded_dir
        excluded_subdir.mkdir(parents=True, exist_ok=True)
        (excluded_subdir / "hidden.py").write_text(
            f"import {framework}\n", encoding="utf-8"
        )

        result = scan_directory(root)

        assert framework not in result.frameworks, (
            f"Framework '{framework}' was detected from excluded dir '{excluded_dir}', "
            "but scan_directory should have skipped it."
        )


# ---------------------------------------------------------------------------
# Property 2: Scanner detects framework imports
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 2: Scanner detects framework imports
@given(framework=_framework, extra=_safe_extra)
@settings(max_examples=100)
def test_scanner_detects_import(framework: str, extra: str) -> None:
    """For any .py file content containing a valid import line for a framework in
    ALL_FRAMEWORKS, scan_directory shall include that framework in
    DetectionResult.frameworks.

    **Validates: Requirements 1.2, 1.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "app.py").write_text(f"import {framework}\n{extra}\n", encoding="utf-8")
        result = scan_directory(root)
        assert framework in result.frameworks, (
            f"Framework '{framework}' was not detected even though 'import {framework}' "
            "is present in a .py file at the scan root."
        )


# Feature: raiflow-init, Property 2 (from-import variant): Scanner detects framework imports
@given(framework=_framework, extra=_safe_extra)
@settings(max_examples=100)
def test_scanner_detects_from_import(framework: str, extra: str) -> None:
    """For any .py file content containing a valid `from <framework> import ...` line,
    scan_directory shall include that framework in DetectionResult.frameworks.

    **Validates: Requirements 1.2, 1.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        (root / "app.py").write_text(
            f"from {framework} import something\n{extra}\n", encoding="utf-8"
        )
        result = scan_directory(root)
        assert framework in result.frameworks, (
            f"Framework '{framework}' was not detected even though "
            f"'from {framework} import something' is present in a .py file."
        )


# ---------------------------------------------------------------------------
# Property 3: Risk level inference covers all tiers
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 3: Risk level inference covers all tiers
@given(frameworks=st.lists(_high_framework, min_size=1))
@settings(max_examples=100)
def test_infer_risk_high(frameworks: list) -> None:
    """For any non-empty list of frameworks from HIGH_RISK_FRAMEWORKS,
    infer_risk_level returns "high".

    **Validates: Requirements 2.1**
    """
    assert infer_risk_level(frameworks) == "high", (
        f"Expected 'high' for high-risk frameworks {frameworks}, "
        f"got '{infer_risk_level(frameworks)}'"
    )


# Feature: raiflow-init, Property 3: Risk level inference covers all tiers
@given(frameworks=st.lists(_limited_framework, min_size=1))
@settings(max_examples=100)
def test_infer_risk_limited(frameworks: list) -> None:
    """For any non-empty list of frameworks drawn exclusively from
    LIMITED_RISK_FRAMEWORKS, infer_risk_level returns "limited".

    **Validates: Requirements 2.2**
    """
    assert infer_risk_level(frameworks) == "limited", (
        f"Expected 'limited' for limited-risk frameworks {frameworks}, "
        f"got '{infer_risk_level(frameworks)}'"
    )


# Feature: raiflow-init, Property 3: Risk level inference covers all tiers
def test_infer_risk_minimal() -> None:
    """For an empty list, infer_risk_level returns "minimal".

    **Validates: Requirements 2.3**
    """
    assert infer_risk_level([]) == "minimal"


# ===========================================================================
# Scaffolder property-based tests (sub-tasks 3.1 – 3.10)
# ===========================================================================

import contextlib
import io
import tempfile

from raiflow.scaffolder import (
    HIGH_ARTICLES,
    LIMITED_ARTICLES,
    SummaryResult,
    WriteResult,
    build_summary,
    print_summary,
    render_manifest,
    write_manifest,
    write_workflow,
)

_detection_strategy = st.builds(
    DetectionResult,
    frameworks=st.lists(st.sampled_from(ALL_FRAMEWORKS), max_size=5),
    risk_level=st.sampled_from(["high", "limited", "minimal"]),
    skipped_files=st.just([]),
)

_detection_with_frameworks = st.builds(
    DetectionResult,
    frameworks=st.lists(st.sampled_from(ALL_FRAMEWORKS), min_size=1, max_size=5),
    risk_level=st.sampled_from(["high", "limited", "minimal"]),
    skipped_files=st.just([]),
)


# ---------------------------------------------------------------------------
# Property 4: Manifest comment references detected frameworks
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 4: Manifest comment references detected frameworks
@given(detection=_detection_with_frameworks)
@settings(max_examples=100)
def test_manifest_comment_references_detected_frameworks(detection: DetectionResult) -> None:
    """For any DetectionResult with at least one detected framework, render_manifest
    shall contain a YAML comment (#) that includes at least one of the detected
    framework names.

    **Validates: Requirements 2.4**
    """
    manifest = render_manifest(detection, "myproject")
    comment_lines = [line for line in manifest.splitlines() if "#" in line]
    assert any(
        fw in line for line in comment_lines for fw in detection.frameworks
    ), (
        f"No comment line references any of {detection.frameworks}.\n"
        f"Comment lines found: {comment_lines}"
    )


# ---------------------------------------------------------------------------
# Property 5: system_name uses directory basename
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 5: system_name uses directory basename
@given(
    detection=_detection_strategy,
    dirname=st.text(
        alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="-_"),
        min_size=1,
        max_size=30,
    ),
)
@settings(max_examples=100)
def test_manifest_system_name_uses_basename(detection: DetectionResult, dirname: str) -> None:
    """For any directory path, render_manifest shall contain the basename of that
    directory as the value of system_name.

    **Validates: Requirements 3.2**
    """
    manifest = render_manifest(detection, dirname)
    assert f'system_name: "{dirname}"' in manifest, (
        f"Expected 'system_name: \"{dirname}\"' in manifest but not found."
    )


# ---------------------------------------------------------------------------
# Property 6: eu_ai_act_articles matches risk level
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 6: eu_ai_act_articles matches risk level
@given(
    detection=st.builds(
        DetectionResult,
        frameworks=st.lists(st.sampled_from(ALL_FRAMEWORKS), max_size=5),
        risk_level=st.sampled_from(["high", "limited", "minimal"]),
        skipped_files=st.just([]),
    )
)
@settings(max_examples=100)
def test_manifest_articles_match_risk_level(detection: DetectionResult) -> None:
    """For risk_level=='high', rendered manifest contains all 6 articles.
    For risk_level=='limited' or 'minimal', rendered manifest contains only Article 13.

    **Validates: Requirements 3.3**
    """
    manifest = render_manifest(detection, "myproject")
    # Extract only the eu_ai_act_articles block (between the key and the next top-level key)
    import re as _re
    articles_block_match = _re.search(
        r"eu_ai_act_articles:\s*\n((?:\s+-.*\n)*)", manifest
    )
    assert articles_block_match, "eu_ai_act_articles block not found in manifest."
    articles_block = articles_block_match.group(0)

    if detection.risk_level == "high":
        for article in HIGH_ARTICLES:
            assert article in articles_block, (
                f"Expected '{article}' in high-risk articles block but not found."
            )
    else:
        assert "Article 13" in articles_block, "Expected 'Article 13' in non-high articles block."
        for article in HIGH_ARTICLES:
            if article != "Article 13":
                assert article not in articles_block, (
                    f"Unexpected '{article}' in {detection.risk_level}-risk articles block."
                )


# ---------------------------------------------------------------------------
# Property 7: model_metadata.name derived from first detected framework
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 7: model_metadata.name derived from first detected framework
@given(detection=_detection_strategy)
@settings(max_examples=100)
def test_manifest_model_name_derived_from_framework(detection: DetectionResult) -> None:
    """For non-empty frameworks list, rendered manifest contains model name including
    first framework name. For empty frameworks list, contains 'my-ai-model'.

    **Validates: Requirements 3.4**
    """
    manifest = render_manifest(detection, "myproject")
    if detection.frameworks:
        first_fw = detection.frameworks[0]
        assert first_fw in manifest, (
            f"Expected first framework '{first_fw}' in model name section of manifest."
        )
    else:
        assert "my-ai-model" in manifest, (
            "Expected 'my-ai-model' as model name when no frameworks detected."
        )


# ---------------------------------------------------------------------------
# Property 8: Manifest boolean invariants
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 8: Manifest boolean invariants
@given(detection=_detection_strategy)
@settings(max_examples=100)
def test_manifest_boolean_invariants(detection: DetectionResult) -> None:
    """For any DetectionResult, render_manifest always contains
    'disclosure_flag: true' and 'middleware_active: true'.

    **Validates: Requirements 3.5, 3.6**
    """
    manifest = render_manifest(detection, "myproject")
    assert "disclosure_flag: true" in manifest, (
        "Expected 'disclosure_flag: true' in manifest."
    )
    assert "middleware_active: true" in manifest, (
        "Expected 'middleware_active: true' in manifest."
    )


# ---------------------------------------------------------------------------
# Property 9: Manifest contains inline comments
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 9: Manifest contains inline comments
@given(detection=_detection_strategy)
@settings(max_examples=100)
def test_manifest_contains_inline_comments(detection: DetectionResult) -> None:
    """For any DetectionResult, render_manifest contains at least one YAML comment
    line (a line containing #).

    **Validates: Requirements 3.7**
    """
    manifest = render_manifest(detection, "myproject")
    comment_lines = [line for line in manifest.splitlines() if "#" in line]
    assert len(comment_lines) >= 1, (
        "Expected at least one comment line in manifest but found none."
    )


# ---------------------------------------------------------------------------
# Property 10: No overwrite without --force
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 10: No overwrite without --force
@given(
    original_content=st.text(min_size=1, max_size=500),
    new_content=st.text(max_size=500),
    detection=_detection_strategy,
)
@settings(max_examples=100)
def test_no_overwrite_without_force(
    original_content: str, new_content: str, detection: DetectionResult
) -> None:
    """For any pre-existing file content, calling write_manifest or write_workflow
    with force=False leaves the file content byte-for-byte identical to the original.

    **Validates: Requirements 3.8, 4.3, 6.1**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Test write_manifest
        manifest_path = root / "raiflow.yaml"
        manifest_path.write_text(original_content, encoding="utf-8", newline="")
        result = write_manifest(new_content, root, force=False)
        assert result.action == "skipped", (
            f"Expected action='skipped' but got '{result.action}'"
        )
        assert manifest_path.read_bytes() == original_content.encode("utf-8"), (
            "write_manifest with force=False modified the existing file."
        )

        # Test write_workflow
        workflows_dir = root / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = workflows_dir / "rai-compliance.yml"
        workflow_path.write_text(original_content, encoding="utf-8", newline="")
        result_wf = write_workflow(root, force=False)
        assert result_wf.action == "skipped", (
            f"Expected action='skipped' for workflow but got '{result_wf.action}'"
        )
        assert workflow_path.read_bytes() == original_content.encode("utf-8"), (
            "write_workflow with force=False modified the existing file."
        )


# ---------------------------------------------------------------------------
# Property 11: Overwrite with --force
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 11: Overwrite with --force
@given(
    original_content=st.text(min_size=1, max_size=500),
    detection=_detection_strategy,
)
@settings(max_examples=100)
def test_overwrite_with_force(original_content: str, detection: DetectionResult) -> None:
    """For any pre-existing file, calling write_manifest or write_workflow with
    force=True replaces the file content and returns WriteResult.action=='overwritten'.

    **Validates: Requirements 3.9, 4.4**
    """
    new_manifest_content = render_manifest(detection, "testproject")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)

        # Test write_manifest with force=True
        manifest_path = root / "raiflow.yaml"
        manifest_path.write_text(original_content, encoding="utf-8")
        result = write_manifest(new_manifest_content, root, force=True)
        assert result.action == "overwritten", (
            f"Expected action='overwritten' but got '{result.action}'"
        )
        assert manifest_path.read_text(encoding="utf-8") == new_manifest_content, (
            "write_manifest with force=True did not replace file content."
        )

        # Test write_workflow with force=True
        workflows_dir = root / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        workflow_path = workflows_dir / "rai-compliance.yml"
        workflow_path.write_text(original_content, encoding="utf-8")
        result_wf = write_workflow(root, force=True)
        assert result_wf.action == "overwritten", (
            f"Expected action='overwritten' for workflow but got '{result_wf.action}'"
        )


# ---------------------------------------------------------------------------
# Property 12: Summary output contains required elements
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 12: Summary output contains required elements
@given(
    detection=_detection_strategy,
    extra_written=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/_-."),
            min_size=1,
            max_size=40,
        ),
        max_size=3,
    ),
    extra_skipped=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd"), whitelist_characters="/_-."),
            min_size=1,
            max_size=40,
        ),
        max_size=2,
    ),
)
@settings(max_examples=100)
def test_summary_contains_required_elements(
    detection: DetectionResult,
    extra_written: list,
    extra_skipped: list,
) -> None:
    """For any SummaryResult, print_summary stdout contains: each detected framework
    name, inferred risk_level value, path of every written/overwritten file, string
    'raiflow check --stage ci', and a notice for every skipped file.

    **Validates: Requirements 5.1, 5.2, 5.4**
    """
    write_results = (
        [WriteResult(path=Path(p), action="written") for p in extra_written]
        + [WriteResult(path=Path(p), action="skipped") for p in extra_skipped]
    )
    summary = build_summary(detection, write_results)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        print_summary(summary)

    stdout_output = stdout_buf.getvalue()

    # Each detected framework name must appear in stdout
    for fw in detection.frameworks:
        assert fw in stdout_output, (
            f"Framework '{fw}' not found in summary stdout."
        )

    # Inferred risk_level must appear in stdout
    assert detection.risk_level in stdout_output, (
        f"risk_level '{detection.risk_level}' not found in summary stdout."
    )

    # Path of every written/overwritten file must appear in stdout
    for wr in write_results:
        if wr.action in ("written", "overwritten"):
            assert str(wr.path) in stdout_output, (
                f"Written path '{wr.path}' not found in summary stdout."
            )

    # Next-step command must appear
    assert "raiflow check --stage ci" in stdout_output, (
        "'raiflow check --stage ci' not found in summary stdout."
    )

    # Notice for every skipped file
    for wr in write_results:
        if wr.action == "skipped":
            assert str(wr.path) in stdout_output, (
                f"Skipped path '{wr.path}' not found in summary stdout."
            )


# ---------------------------------------------------------------------------
# Property 13: Output routing (stdout vs stderr)
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 13: Output routing (stdout vs stderr)
@given(detection=_detection_strategy)
@settings(max_examples=100)
def test_output_routing_stdout_vs_stderr(detection: DetectionResult) -> None:
    """For any execution of print_summary, all informational content goes to stdout
    and all warning/error content goes to stderr — the two streams shall not be mixed.

    **Validates: Requirements 5.5**
    """
    write_results = [
        WriteResult(path=Path("raiflow.yaml"), action="written"),
        WriteResult(path=Path(".github/workflows/rai-compliance.yml"), action="skipped"),
    ]
    summary = build_summary(detection, write_results)

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
        print_summary(summary)

    stdout_output = stdout_buf.getvalue()
    stderr_output = stderr_buf.getvalue()

    # Informational content (risk level, next step) must be on stdout, not stderr
    assert detection.risk_level in stdout_output, (
        f"risk_level '{detection.risk_level}' should be on stdout."
    )
    assert "raiflow check --stage ci" in stdout_output, (
        "'raiflow check --stage ci' should be on stdout."
    )

    # Informational content must NOT appear on stderr
    assert detection.risk_level not in stderr_output, (
        f"risk_level '{detection.risk_level}' should not appear on stderr."
    )
    assert "raiflow check --stage ci" not in stderr_output, (
        "'raiflow check --stage ci' should not appear on stderr."
    )


# ===========================================================================
# CLI integration property-based tests (sub-task 5.1)
# ===========================================================================

from click.testing import CliRunner
from raiflow.cli import init


# ---------------------------------------------------------------------------
# Property 14: Idempotency
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 14: Idempotency
@given(frameworks=st.lists(st.sampled_from(ALL_FRAMEWORKS)))
@settings(max_examples=100)
def test_idempotency(frameworks: list) -> None:
    """For any valid project directory, running raiflow init (without --force) a second
    time shall leave raiflow.yaml and .github/workflows/rai-compliance.yml byte-for-byte
    identical to the files produced by the first run.

    **Validates: Requirements 6.1, 6.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)

        # Create a .py file importing the given frameworks
        if frameworks:
            imports = "\n".join(f"import {fw}" for fw in frameworks)
        else:
            imports = "# no frameworks"
        (target_dir / "app.py").write_text(imports + "\n", encoding="utf-8")

        runner = CliRunner()

        # First run
        result1 = runner.invoke(init, ["--directory", str(target_dir)])
        assert result1.exit_code == 0, (
            f"First run failed with exit code {result1.exit_code}.\nOutput: {result1.output}"
        )

        manifest_path = target_dir / "raiflow.yaml"
        workflow_path = target_dir / ".github" / "workflows" / "rai-compliance.yml"

        content_manifest_1 = manifest_path.read_bytes()
        content_workflow_1 = workflow_path.read_bytes()

        # Second run (no --force)
        result2 = runner.invoke(init, ["--directory", str(target_dir)])
        assert result2.exit_code == 0, (
            f"Second run failed with exit code {result2.exit_code}.\nOutput: {result2.output}"
        )

        content_manifest_2 = manifest_path.read_bytes()
        content_workflow_2 = workflow_path.read_bytes()

        assert content_manifest_1 == content_manifest_2, (
            "raiflow.yaml changed between first and second run (without --force)."
        )
        assert content_workflow_1 == content_workflow_2, (
            "rai-compliance.yml changed between first and second run (without --force)."
        )


# ---------------------------------------------------------------------------
# Property 15: --directory option scans specified directory
# ---------------------------------------------------------------------------

# Feature: raiflow-init, Property 15: --directory option scans specified directory
@given(framework=st.sampled_from(ALL_FRAMEWORKS))
@settings(max_examples=100)
def test_directory_option_scans_specified_directory(framework: str) -> None:
    """For any valid directory path passed via --directory, scan_directory shall be
    called with that path as root, and all written files shall be placed relative to
    that path rather than the process working directory.

    **Validates: Requirements 7.3**
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        target_dir = Path(tmpdir)
        # Place a .py file importing the framework in the target directory
        (target_dir / "app.py").write_text(f"import {framework}\n", encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(init, ["--directory", str(target_dir)])

        assert result.exit_code == 0, (
            f"Expected exit code 0 but got {result.exit_code}.\nOutput: {result.output}"
        )

        # raiflow.yaml must be in the specified directory, not cwd
        assert (target_dir / "raiflow.yaml").exists(), (
            "raiflow.yaml was not created in the specified --directory."
        )

        # .github/workflows/rai-compliance.yml must be in the specified directory
        assert (target_dir / ".github" / "workflows" / "rai-compliance.yml").exists(), (
            ".github/workflows/rai-compliance.yml was not created in the specified --directory."
        )
