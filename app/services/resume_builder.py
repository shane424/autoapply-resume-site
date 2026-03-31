from pathlib import Path
from jinja2 import Environment, FileSystemLoader

from app.models.resume import TailoredResumeContent, ParsedResume

TEMPLATES_DIR = Path(__file__).parent.parent.parent / "frontend" / "templates"
STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "tailored"

_jinja_env = Environment(loader=FileSystemLoader(str(TEMPLATES_DIR)))


def _render_html(content: TailoredResumeContent, contact: dict) -> str:
    tmpl = _jinja_env.get_template("resume_template.html")
    return tmpl.render(
        contact=contact,
        summary=content.summary,
        experience=content.experience,
        skills=content.skills,
        education=content.education,
    )


def _build_pdf(html: str, out_path: Path) -> None:
    from weasyprint import HTML
    HTML(string=html).write_pdf(str(out_path))


def _build_docx(content: TailoredResumeContent, contact: dict, out_path: Path) -> None:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    # Name heading
    name = contact.get("name", "")
    if name:
        h = doc.add_heading(name, level=0)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Contact line
    contact_parts = [v for k, v in contact.items() if k != "name" and v]
    if contact_parts:
        p = doc.add_paragraph(" · ".join(contact_parts))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.size = Pt(9)

    def add_section(title: str):
        h = doc.add_heading(title, level=2)
        return h

    # Summary
    if content.summary:
        add_section("Summary")
        doc.add_paragraph(content.summary)

    # Skills
    if content.skills:
        add_section("Skills")
        doc.add_paragraph(" · ".join(content.skills))

    # Experience
    if content.experience:
        add_section("Experience")
        for exp in content.experience:
            p = doc.add_paragraph()
            p.add_run(exp.title).bold = True
            p.add_run(f"  —  {exp.company}")
            p.add_run(f"  ({exp.dates})").italic = True
            for bullet in exp.bullets:
                bp = doc.add_paragraph(bullet, style="List Bullet")
                bp.runs[0].font.size = Pt(10)

    # Education
    if content.education:
        add_section("Education")
        for edu in content.education:
            p = doc.add_paragraph()
            p.add_run(edu.degree).bold = True
            p.add_run(f"  —  {edu.school}  ({edu.year})")

    doc.save(str(out_path))


def build_resume(content: TailoredResumeContent, original_resume: ParsedResume) -> TailoredResumeContent:
    job_dir = STORAGE_DIR / content.job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    contact = original_resume.contact

    html = _render_html(content, contact)

    pdf_path = job_dir / "resume.pdf"
    docx_path = job_dir / "resume.docx"

    _build_pdf(html, pdf_path)
    _build_docx(content, contact, docx_path)

    content.pdf_path = str(pdf_path)
    content.docx_path = str(docx_path)
    return content
