from app.services.job_detector import detect_secrets, format_secret_for_application
from app.services.scraper import _is_us_remote


# --- Secret detection ---

def test_detects_mention_word():
    desc = "Please mention the word DANKEN when applying to show you read this."
    secrets = detect_secrets(desc)
    assert any(s.secret == "DANKEN" for s in secrets)


def test_detects_tag():
    desc = "Tag ROTkuMTQ2LjE2LjE0MQ== when applying (#ROTkuMTQ2LjE2LjE0MQ==)."
    secrets = detect_secrets(desc)
    assert any("ROTkuMTQ2LjE2LjE0MQ" in s.secret for s in secrets)


def test_detects_include_phrase():
    desc = "Include the phrase coffee_lover in your cover letter."
    secrets = detect_secrets(desc)
    assert any(s.secret == "coffee_lover" for s in secrets)


def test_no_false_positives_on_normal_text():
    desc = "We are looking for a Python developer to join our team. Please apply via the link below."
    secrets = detect_secrets(desc)
    assert len(secrets) == 0


def test_format_secrets_for_application():
    desc = "Please mention DANKEN when applying."
    secrets = detect_secrets(desc)
    result = format_secret_for_application(secrets)
    assert "DANKEN" in result


# --- US remote filter ---

def test_us_remote_normal_job():
    assert _is_us_remote("We are looking for a remote Python developer in the US.") is True


def test_eu_only_excluded():
    assert _is_us_remote("This position is EU only. US applicants need not apply.") is False


def test_europe_only_excluded():
    assert _is_us_remote("Candidates must be based in Europe only.") is False


def test_uk_only_excluded():
    assert _is_us_remote("This is a UK-only remote role.") is False


def test_no_us_applicants_excluded():
    assert _is_us_remote("No US residents please.") is False


def test_must_be_in_germany_excluded():
    assert _is_us_remote("Must be based in Germany to apply.") is False


def test_unspecified_passes():
    assert _is_us_remote("Remote position for a backend engineer.") is True
