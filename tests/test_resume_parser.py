import pytest
from app.services.resume_parser import _extract_contact, _parse_skills, _parse_sections, _normalize_company, _split_title_company


def test_extract_contact_email():
    lines = ["Jane Doe", "jane@example.com | +1-555-0100 | linkedin.com/in/janedoe"]
    contact = _extract_contact(lines)
    assert contact["email"] == "jane@example.com"
    assert "janedoe" in contact.get("linkedin", "")


def test_parse_skills_comma():
    lines = ["Python, FastAPI, PostgreSQL, Docker"]
    skills = _parse_skills(lines)
    assert "Python" in skills
    assert "Docker" in skills


def test_parse_skills_pipe():
    lines = ["React | Node.js | TypeScript"]
    skills = _parse_skills(lines)
    assert "React" in skills
    assert "TypeScript" in skills


def test_normalize_company_agency_dash_client():
    assert _normalize_company("AGR LLC - GE Aviation") == "AGR LLC (GE Aviation)"
    assert _normalize_company("ActOne - JP Morgan Chase") == "ActOne (JP Morgan Chase)"


def test_normalize_company_no_change():
    assert _normalize_company("Pure Storage") == "Pure Storage"
    assert _normalize_company("DMI") == "DMI"


def test_split_title_company_wide_spaces():
    title, company = _split_title_company("Python Developer    DMI")
    assert title == "Python Developer"
    assert company == "DMI"


def test_split_title_company_agency_client_preserved():
    # The company name with a dash must not be split further
    title, company = _split_title_company("HVR Application Engineer    AGR LLC - GE Aviation")
    assert title == "HVR Application Engineer"
    assert company == "AGR LLC (GE Aviation)"


def test_detect_sections():
    text = """Jane Doe
jane@example.com

Summary
Experienced engineer.

Skills
Python, FastAPI

Experience
Software Engineer — Acme Corp (2020-2023)
• Built APIs
"""
    sections = _parse_sections(text)
    assert any("Experienced" in l for l in sections["summary"])
    assert any("Python" in l for l in sections["skills"])
    assert any("Acme" in l for l in sections["experience"])
