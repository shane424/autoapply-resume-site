"""
Dependency checker — run at startup to detect missing packages early.
Also used by the /api/health endpoint.
"""

# Map: import name -> pip install name
REQUIRED = {
    "fastapi":        "fastapi",
    "uvicorn":        "uvicorn[standard]",
    "jinja2":         "jinja2",
    "multipart":      "python-multipart",
    "pdfplumber":     "pdfplumber",
    "docx":           "python-docx",
    "reportlab":      "reportlab==4.2.5",
    "anthropic":      "anthropic",
    "httpx":          "httpx",
    "bs4":            "beautifulsoup4",
    "yaml":           "pyyaml",
    "dotenv":         "python-dotenv",
    "pydantic_settings": "pydantic-settings",
}

OPTIONAL = {
    "playwright":     "playwright  (then: playwright install chromium)",
}


def check_dependencies() -> dict[str, str]:
    """Return a dict of {import_name: status} where status is 'ok' or an error string."""
    import importlib
    results: dict[str, str] = {}

    for import_name, pip_name in {**REQUIRED, **OPTIONAL}.items():
        try:
            importlib.import_module(import_name)
            results[import_name] = "ok"
        except ImportError:
            results[import_name] = f"MISSING — run: pip install {pip_name}"
        except BaseException as e:
            # Catches non-ImportError failures like pyo3 PanicException
            # from broken native extensions — treat as missing for health display
            results[import_name] = f"ERROR — {type(e).__name__}: {e}"

    return results


def assert_required(results: dict[str, str]) -> list[str]:
    """Return list of error strings for required-but-missing packages."""
    errors = []
    for name in REQUIRED:
        if results.get(name, "").startswith("MISSING"):
            errors.append(results[name])
    return errors


def print_startup_check() -> None:
    results = check_dependencies()
    errors = assert_required(results)
    if errors:
        print("\n" + "=" * 60)
        print("MISSING REQUIRED DEPENDENCIES — install before starting:")
        for e in errors:
            print(f"  {e}")
        print("=" * 60 + "\n")
    else:
        optional_missing = [v for k, v in results.items() if k in OPTIONAL and v.startswith("MISSING")]
        if optional_missing:
            print("[AutoApply] Optional deps missing (auto-apply disabled):")
            for m in optional_missing:
                print(f"  {m}")
        else:
            print("[AutoApply] All dependencies OK.")
