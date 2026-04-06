from app.services.job_detector import detect_secrets, format_secret_for_application
from app.services.scraper import _us_remote_status, _extract_location


# --- Secret detection ---

def test_detects_mention_word():
    desc = "Please mention the word DANKEN when applying to show you read this."
    secrets = detect_secrets(desc)
    assert any(s.secret == "DANKEN" for s in secrets)


def test_detects_tag():
    desc = "Tag ROTkuMTQ2LjE2LjE0MQ== when applying (#ROTkuMTQ2LjE2LjE0MQ==)."
    secrets = detect_secrets(desc)
    assert any("ROTkuMTQ2LjE2LjE0MQ" in s.secret for s in secrets)


def test_detects_delightfully_and_tag():
    desc = (
        "Please mention the word **DELIGHTFULLY** and tag RMTYzLjE4Mi44NC4yMzg= "
        "when applying to show you read the job post completely."
    )
    secrets = detect_secrets(desc)
    words = [s.secret for s in secrets]
    assert "DELIGHTFULLY" in words
    assert any("RMTYzLjE4Mi44NC4yMzg" in w for w in words)


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


# --- US remote status ---

def test_us_remote_normal_job():
    assert _us_remote_status("Remote Python developer role open to US.", "Remote") == "yes"


def test_eu_only_excluded():
    assert _us_remote_status("This position is EU only.", "Remote") == "no"


def test_europe_only_excluded():
    assert _us_remote_status("Candidates must be based in Europe only.", "Remote") == "no"


def test_uk_only_excluded():
    assert _us_remote_status("This is a UK-only remote role.", "Remote") == "no"


def test_no_us_applicants_excluded():
    assert _us_remote_status("No US residents please.", "Remote") == "no"


def test_must_be_in_ireland_excluded():
    assert _us_remote_status("", "Must be based in Ireland") == "no"


def test_unspecified_passes():
    assert _us_remote_status("Remote position for a backend engineer.", "Remote") == "yes"


def test_ireland_remote_is_unclear():
    assert _us_remote_status("Great role!", "Dublin, Ireland (Remote)") == "unclear"


def test_location_extraction():
    desc = "Location(s):\n Dublin, Ireland (Remote)\n\nJob Summary:"
    loc = _extract_location(desc)
    assert "Ireland" in loc


def test_location_extraction_fallback():
    assert _extract_location("No location mentioned here.", fallback="Remote") == "Remote"
