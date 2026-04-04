import pytest
from app.services.apply_playwright import detect_ats


def test_detect_greenhouse():
    assert detect_ats("https://boards.greenhouse.io/acme/jobs/123") == "greenhouse"


def test_detect_lever():
    assert detect_ats("https://jobs.lever.co/acme/abc-123") == "lever"


def test_detect_workable():
    assert detect_ats("https://apply.workable.com/acme/j/ABC123/") == "workable"


def test_detect_ashby():
    assert detect_ats("https://jobs.ashbyhq.com/acme/role") == "ashby"


def test_detect_unknown():
    assert detect_ats("https://careers.some-company.com/jobs/123") == "unknown"
