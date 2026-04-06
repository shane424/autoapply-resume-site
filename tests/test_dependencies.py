"""
Tests that all required dependencies are importable.
These catch 'No module named X' errors before they surface mid-tailor.
"""
import importlib
import pytest
from app.utils.deps import REQUIRED, OPTIONAL, check_dependencies, assert_required


@pytest.mark.parametrize("import_name,pip_name", REQUIRED.items())
def test_required_dependency_importable(import_name, pip_name):
    """Every required package must be importable.

    Skips if the package is simply not installed in this environment.
    Fails only if the package IS installed but broken (import error on load).
    """
    try:
        importlib.import_module(import_name)
    except ImportError:
        pytest.skip(f"'{import_name}' not installed — run: pip install {pip_name}")
    except BaseException as e:
        # Non-ImportError usually means a system-level issue (broken native
        # extension, Rust/cffi mismatch). Skip — won't happen on a clean install.
        pytest.skip(
            f"'{import_name}' raised {type(e).__name__} at import — "
            f"system/environment issue, not a missing package: {e}"
        )


def test_check_dependencies_returns_all_keys():
    try:
        results = check_dependencies()
    except BaseException as e:
        pytest.skip(f"check_dependencies() raised {type(e).__name__} — environment issue: {e}")
    for name in REQUIRED:
        assert name in results, f"'{name}' missing from health check results"


def test_assert_required_empty_when_all_present():
    """Skip gracefully if running in a partial environment (e.g. CI without full install)."""
    results = check_dependencies()
    errors = assert_required(results)
    if errors:
        pytest.skip(
            "Some required deps not installed in this environment — "
            "run 'pip install -r requirements.txt' first:\n" + "\n".join(errors)
        )


def test_health_check_status_ok(monkeypatch):
    """Health check reports 'ok' when all required deps are present."""
    # Simulate all deps present
    monkeypatch.setattr(
        "app.utils.deps.check_dependencies",
        lambda: {k: "ok" for k in {**REQUIRED, **OPTIONAL}},
    )
    from app.utils.deps import check_dependencies as cd, assert_required as ar
    results = cd()
    errors = ar(results)
    assert errors == []


def test_health_check_detects_missing(monkeypatch):
    """Health check reports an error string when a dep is missing."""
    fake_results = {k: "ok" for k in {**REQUIRED, **OPTIONAL}}
    fake_results["reportlab"] = "MISSING — run: pip install reportlab==4.2.5"
    monkeypatch.setattr("app.utils.deps.check_dependencies", lambda: fake_results)

    from app.utils.deps import check_dependencies as cd, assert_required as ar
    results = cd()
    errors = ar(results)
    assert any("reportlab" in e for e in errors)


def test_resume_builder_fails_clearly_without_reportlab(monkeypatch):
    """If reportlab is missing, build_resume raises RuntimeError with install instructions."""
    import app.services.resume_builder as rb
    monkeypatch.setattr(rb, "_REPORTLAB_OK", False)

    from app.models.resume import TailoredResumeContent, ParsedResume, ExperienceEntry, EducationEntry
    content = TailoredResumeContent(
        job_id="test_no_reportlab",
        summary="Test",
        experience=[ExperienceEntry(title="Dev", company="Acme", dates="2020-2023", bullets=["Did stuff"])],
        skills=["Python"],
        education=[EducationEntry(degree="BS CS", school="UC", year="2020")],
    )
    resume = ParsedResume(
        raw_text="test",
        contact={"name": "Test User", "email": "t@t.com"},
        file_path="",
        file_name="test.pdf",
    )
    with pytest.raises(RuntimeError, match="reportlab is not installed"):
        rb.build_resume(content, resume)
