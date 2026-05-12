import re
from pathlib import Path
from app.models.resume import ParsedResume, ExperienceEntry, EducationEntry

# Phrases that indicate prompt injection attempts hidden in resume PDFs
_INJECTION_PATTERNS = re.compile(
    r"ignore\s+(?:all\s+)?(?:previous|prior|above)\s+instructions?"
    r"|disregard\s+(?:all\s+)?(?:previous|prior|above)"
    r"|you\s+are\s+now\s+(?:a\s+)?(?:an?\s+)?\w+"
    r"|(?:approve|hire|select|recommend)\s+this\s+(?:candidate|resume|applicant)"
    r"|act\s+as\s+(?:if\s+)?(?:you\s+are|a[n]?\s+)",
    re.IGNORECASE,
)


def _sanitize_resume_text(text: str) -> str:
    """Strip lines containing prompt injection attempts from extracted PDF text."""
    clean_lines = []
    for line in text.splitlines():
        if _INJECTION_PATTERNS.search(line):
            print(f"[resume_parser] Stripped injection attempt: {line[:80]!r}")
            continue
        clean_lines.append(line)
    return "\n".join(clean_lines)


def _extract_text_from_pdf(path: Path) -> str:
    import pdfplumber
    text_parts = []
    with pdfplumber.open(str(path)) as pdf:
        for page in pdf.pages:
            # layout=True uses positional info to better handle multi-column layouts
            t = page.extract_text(layout=True)
            if not t:
                t = page.extract_text()
            if t:
                text_parts.append(t)
    return _sanitize_resume_text("\n".join(text_parts))


def _extract_text_from_docx(path: Path) -> str:
    from docx import Document
    doc = Document(str(path))
    return _sanitize_resume_text("\n".join(p.text for p in doc.paragraphs))


def _detect_section(line: str) -> str | None:
    """Flexible section detection — matches as long as the key word appears in a short heading line."""
    stripped = line.strip()
    if not stripped or len(stripped) > 80:
        return None
    lower = stripped.lower()

    if re.search(r'\b(summary|professional summary|objective|profile)\b', lower):
        return "summary"
    if re.search(r'\b(work experience|experience|employment|work history)\b', lower):
        return "experience"
    if re.search(r'\b(skills|competencies|technologies)\b', lower):
        return "skills"
    if re.search(r'\b(education|academic)\b', lower):
        return "education"
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
    # Require at least one digit cluster like "937-499-3269" or "(937) 499-3269"
    phone_re = re.compile(r"[\+]?\(?\d{3}\)?[\s.\-]\d{3}[\s.\-]\d{4}")
    linkedin_re = re.compile(r"linkedin\.com/in/[\w-]+", re.IGNORECASE)
    # "City, ST" — each city word must start uppercase then have lowercase letters
    # (e.g. "Cincinnati", "New York") which excludes all-caps names like "SHANE SMITH"
    city_re = re.compile(r"\b([A-Z][a-z][a-zA-Z]*(?:\s[A-Z][a-z][a-zA-Z]*)?),\s*([A-Z]{2})\b")

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
    city_m = city_re.search(full_text)
    if city_m:
        contact["location"] = city_m.group()

    for line in header_lines:
        line = line.strip()
        if line and not email_re.search(line) and not linkedin_re.search(line) and not phone_re.search(line):
            contact["name"] = line
            break
    return contact


# Matches date ranges like "11/2024 - 11/2025", "Jan 2020 - Present", "2018 - 2020"
DATE_RANGE_RE = re.compile(
    r"(\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\s*\d{4}\s*[-–]\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)?\s*(?:\d{4}|present|current)|\d{2}/\d{4}\s*[-–]\s*\d{2}/\d{4})",
    re.IGNORECASE,
)
BULLET_RE = re.compile(r"^[\s]*[•●\-\*–]\s*")


def _is_bullet(line: str) -> bool:
    return bool(BULLET_RE.match(line))


def _clean_bullet(line: str) -> str:
    return BULLET_RE.sub("", line).strip()


# Matches "Agency - Client" or "Agency LLC - Client Corp" patterns in company names.
# Both sides must start with a capital letter so we don't confuse hyphens in dates.
_AGENCY_CLIENT_RE = re.compile(r'^(.+?)\s+-\s+([A-Z].+)$')


def _normalize_company(name: str) -> str:
    """Convert 'Agency - Client' to 'Agency (Client)' for better ATS compatibility.

    e.g. 'AGR LLC - GE Aviation'  -> 'AGR LLC (GE Aviation)'
         'ActOne - JP Morgan Chase' -> 'ActOne (JP Morgan Chase)'
         'Pure Storage'             -> 'Pure Storage'  (unchanged)
    """
    m = _AGENCY_CLIENT_RE.match(name.strip())
    if m:
        return f"{m.group(1)} ({m.group(2)})"
    return name


# Words that strongly indicate a job title component.
# We split at the first word NOT in this set (after consuming at least one title word).
_ROLE_WORDS = {
    'senior', 'junior', 'lead', 'principal', 'staff', 'associate', 'chief',
    'software', 'backend', 'frontend', 'fullstack', 'full-stack',
    'engineer', 'developer', 'architect', 'manager', 'director', 'analyst',
    'designer', 'consultant', 'specialist', 'administrator', 'coordinator',
    'python', 'java', 'javascript', 'typescript', 'react', 'node', 'golang',
    'data', 'cloud', 'devops', 'platform', 'systems', 'security', 'network',
    'application', 'hvr', 'sql', 'database', 'web', 'mobile', 'ios', 'android',
    'machine', 'learning', 'ai', 'ml', 'support', 'site', 'reliability',
    'full', 'stack', 'quality', 'assurance', 'qa', 'product', 'technical',
    'solutions', 'integration', 'embedded', 'infrastructure', 'operations',
}


def _split_by_role_words(text: str) -> tuple[str, str]:
    """Fallback: split 'Python Developer DMI' -> ('Python Developer', 'DMI').

    Consumes words that look like job-title words; splits at the first word
    that doesn't — that word and everything after it is the company name.
    Requires at least one title word before splitting.
    """
    words = text.split()
    split_idx = len(words)  # default: all words are title
    found_role_word = False
    for i, word in enumerate(words):
        if word.lower() in _ROLE_WORDS:
            found_role_word = True
        elif found_role_word:
            split_idx = i
            break

    if split_idx < len(words):
        return " ".join(words[:split_idx]), _normalize_company(" ".join(words[split_idx:]))
    return text.strip(), ""


def _split_title_company(remainder: str) -> tuple[str, str]:
    """Split 'Title   Company' into (title, company).

    Strategy (in order):
    1. 2+ spaces — preserves 'AGR LLC - GE Aviation' as one company chunk.
    2. Em/en-dash separator.
    3. ' | ' or ' · ' separator.
    4. Role-word heuristic — 'Python Developer DMI' -> ('Python Developer', 'DMI').
    5. Give up — return whole string as title.
    """
    for pattern in (r"\s{2,}", r"[—–]", r"\s[|·]\s"):
        parts = [p.strip() for p in re.split(pattern, remainder) if p.strip()]
        if len(parts) >= 2:
            return parts[0], _normalize_company(parts[1])

    # Fallback: use role-word heuristic for single-spaced text
    title, company = _split_by_role_words(remainder)
    if company:
        return title, company

    return remainder.strip(), ""


def _parse_experience(lines: list[str]) -> list[ExperienceEntry]:
    entries: list[ExperienceEntry] = []
    current: dict | None = None
    seen_bullets: set[str] = set()  # deduplicate repeated bullets (multi-column artifact)

    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue

        date_match = DATE_RANGE_RE.search(stripped)

        if date_match and not _is_bullet(stripped):
            # This looks like a job header line: "Title   Company   Date"
            if current:
                entries.append(ExperienceEntry(**current))
            seen_bullets = set()

            dates = date_match.group().strip()
            # Remove the date range from the line, then split into title + company
            remainder = DATE_RANGE_RE.sub("", stripped).strip().strip("—–").strip()
            title, company = _split_title_company(remainder)

            current = {"title": title, "company": company, "dates": dates, "bullets": []}

        elif _is_bullet(stripped) and current is not None:
            bullet = _clean_bullet(stripped)
            if bullet and bullet not in seen_bullets:
                seen_bullets.add(bullet)
                current["bullets"].append(bullet)

        elif current is not None and not current["company"] and not _is_bullet(stripped):
            # Second line after header — likely the company name if not captured
            if not DATE_RANGE_RE.search(stripped):
                current["company"] = stripped

    if current:
        entries.append(ExperienceEntry(**current))

    return entries


def _parse_skills(lines: list[str]) -> list[str]:
    skills = []
    seen = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Skills are often comma, pipe, or bullet separated
        for skill in re.split(r"[,|•●]", line):
            skill = skill.strip().lstrip("-*•●– ")
            if skill and skill not in seen:
                seen.add(skill)
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
            year = year_re.findall(stripped)[0]
            current = {"degree": stripped, "school": "", "year": year}
        elif current and not current["school"]:
            current["school"] = stripped

    if current:
        entries.append(EducationEntry(**current))
    return entries


def parse_resume_text(raw_text: str) -> ParsedResume:
    """Parse resume from already-extracted text (e.g. sent from the browser extension)."""
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
    )


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
