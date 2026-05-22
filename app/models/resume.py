from pydantic import BaseModel
from typing import Optional


class ExperienceEntry(BaseModel):
    title: str
    company: str
    dates: str
    bullets: list[str]


class EducationEntry(BaseModel):
    degree: str
    school: str
    year: str


class ParsedResume(BaseModel):
    raw_text: str
    contact: dict = {}
    summary: str = ""
    experience: list[ExperienceEntry] = []
    skills: list[str] = []
    education: list[EducationEntry] = []
    file_path: str = ""
    file_name: str = ""


class TailoredResumeContent(BaseModel):
    job_id: str
    summary: str
    experience: list[ExperienceEntry]
    skills: list[str]
    education: list[EducationEntry]
    keywords_added: list[str] = []
    cover_letter: str = ""
    pdf_path: Optional[str] = None
    docx_path: Optional[str] = None
    cover_letter_path: Optional[str] = None
