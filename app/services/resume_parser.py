import re
from pathlib import Path
from app.models.resume import ParsedResume, ExperienceEntry, EducationEntry


SECTION_HEADERS = {
    "summary": re.compile(r"^\s*(summary|professional summary|objective|profile)\s*$", re.IGNORECASE),
    "experience": re.compile(r"^\s*(experience|work experience|employment|employment history|work history)\s*$", re.IGNORECASE),
    "skills": re.compile(r"^\s*(skills|technical skills|core competencies|competencies|technologies)\s*$", re.IGNORECASE),
    "education": re.compile(r"^\s*(education|academic background|academic history)\s*$", re.IGNORECASE),
}


def _extract_text_from_pdf(path: Path) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n".join(text_parts)


def _extract_text_from_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return "\n".join(p.text for p in doc.paragraphs)


def _detect_section(line: str) -> str | None:
    for section, pattern in SECTION_HEADERS.items():
        if pattern.match(line):
            return section
    return None


def _parse_sections(raw_text: str) -> dict:
    sections: dict[str, list[str]] = {
        "summary": [],
        "experience": [],
        "skills": [],
        "education": [],
        "header": [],
    }
    current = "header"
    for line in raw_text.splitlines():
        section = _detect_section(line)
        if section:
            current = section
            continue
        sections[current].append(line)
    return sections


def _extract_contact(header_lines: list[str]) -> dict:
    contact: dict[str, str] = {}
    email_re = re.compile(r"[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}")
    phone_re = re.compile(r"[\+]?[\d\s\-\(\)]{7,15}")
    linkedin_re = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)

    full_text = " ".join(header_lines)
    email_m = email_re.search(full_text)
    if email_m:
        contact["email"] = email_m.group()
    phone_m = phone_re.search(full_text)
    if phone_m:
        contact["phone"] = phone_m.group().strip()
    linkedin_m = linkedin_re.search(full_text)
    if linkedin_m:
        contact["linkedin"] = linkedin_m.group()
    # First non-empty, non-contact line is likely the name
    for line in header_lines:
        line = line.strip()
        if line and not email_re.search(line) and not linkedin_re.search(line):
            contact["name"] = line
            break
    return contact


def _parse_experience(lines: list[str]) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    current: dict | None = None
    date_re = re.compile(r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|\d{4}|present|current)", re.IGNORECASE)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        # Heuristic: line with a date pattern and no leading bullet is a job header
        if date_re.search(stripped) and not stripped.startswith(("•", "-", "*", "–")):
            if current:
                entries.append(ExperienceEntry(**current))
            current = {"title": stripped, "company": "", "dates": stripped, "bullets": []}
        elif stripped.startswith(("•", "-", "*", "–")) and current:
            current["bullets"].append(stripped.lstrip("•-*– ").strip())
        elif current and not current["company"]:
            current["company"] = stripped

    if current:
        entries.append(ExperienceEntry(**current))
    return entries


def _parse_skills(lines: list[str]) -> list[str]:
    skills = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skills are often comma or pipe separated
        for skill in re.split(r"[,|•]", line):
            skill = skill.strip().lstrip("-*•– ")
            if skill:
                skills.append(skill)
    return skills


def _parse_education(lines: list[str]) -> list[EducationEntry]:
    entries = []
    year_re = re.compile(r"\b(19|20)\d{2}\b")
    current: dict | None = None
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        if year_re.search(stripped):
            if current:
                entries.append(EducationEntry(**current))
            current = {"degree": stripped, "school": "", "year": year_re.search(stripped).group()}
        elif current and not current["school"]:
            current["school"] = stripped
    if current:
        entries.append(EducationEntry(**current))
    return entries


def parse_resume(file_path: str) -> ParsedResume:
    path = Path(file_path)
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        raw_text = _extract_text_from_pdf(path)
    elif suffix in (".docx", ".doc"):
        raw_text = _extract_text_from_docx(path)
    else:
        raise ValueError(f"Unsupported file type: {suffix}")

    sections = _parse_sections(raw_text)
    contact = _extract_contact(sections["header"])
    experience = _parse_experience(sections["experience"])
    skills = _parse_skills(sections["skills"])
    education = _parse_education(sections["education"])
    summary = " ".join(l.strip() for l in sections["summary"] if l.strip())

    return ParsedResume(
        raw_text=raw_text,
        contact=contact,
        summary=summary,
        experience=experience,
        skills=skills,
        education=education,
        file_path=str(path),
        file_name=path.name,
    )
