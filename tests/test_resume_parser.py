import pytest
from app.services.resume_parser import _extract_contact, _parse_skills, _parse_sections


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
