from pathlib import Path
from app.models.resume import TailoredResumeContent, ParsedResume

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "tailored"

try:
    import reportlab  # noqa: F401
    _REPORTLAB_OK = True
except ImportError:
    _REPORTLAB_OK = False

# Points per inch / millimetre helpers for reportlab
_PT_PER_MM = 2.8346


def _mm(mm: float) -> float:
    return mm * _PT_PER_MM


def _build_pdf(content: TailoredResumeContent, contact: dict, out_path: Path) -> None:
    """Build a clean PDF resume using reportlab (pure Python, no system deps)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=inch * 0.75,
        rightMargin=inch * 0.75,
        topMargin=inch * 0.6,
        bottomMargin=inch * 0.6,
    )

    styles = getSampleStyleSheet()

    name_style = ParagraphStyle(
        "Name", fontSize=18, fontName="Helvetica-Bold",
        alignment=1, spaceAfter=4,
    )
    contact_style = ParagraphStyle(
        "Contact", fontSize=9, fontName="Helvetica",
        alignment=1, textColor=colors.HexColor("#444444"), spaceAfter=8,
    )
    section_style = ParagraphStyle(
        "Section", fontSize=11, fontName="Helvetica-Bold",
        textColor=colors.HexColor("#111111"), spaceBefore=10, spaceAfter=2,
    )
    body_style = ParagraphStyle(
        "Body", fontSize=10, fontName="Helvetica",
        leading=14, spaceAfter=3,
    )
    bullet_style = ParagraphStyle(
        "Bullet", fontSize=10, fontName="Helvetica",
        leading=13, leftIndent=14, bulletIndent=4, spaceAfter=1,
    )
    job_title_style = ParagraphStyle(
        "JobTitle", fontSize=10, fontName="Helvetica-Bold",
        spaceAfter=1,
    )
    job_meta_style = ParagraphStyle(
        "JobMeta", fontSize=9, fontName="Helvetica-Oblique",
        textColor=colors.HexColor("#555555"), spaceAfter=2,
    )

    def _hr():
        # Table-based horizontal rule — avoids HRFlowable Windows bug
        t = Table([[""]], colWidths=["100%"])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.75, colors.HexColor("#333333")),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return t

    def section(title: str) -> list:
        return [Paragraph(title.upper(), section_style), _hr()]

    story = []

    # Name
    name = contact.get("name", "")
    if name:
        story.append(Paragraph(name, name_style))

    # Contact
    contact_parts = [v for k, v in contact.items() if k != "name" and v]
    if contact_parts:
        story.append(Paragraph(" · ".join(contact_parts), contact_style))

    # Summary
    if content.summary:
        story += section("Summary")
        story.append(Paragraph(content.summary, body_style))

    # Skills
    if content.skills:
        story += section("Skills & Technologies")
        story.append(Paragraph(" · ".join(content.skills), body_style))

    # Experience
    if content.experience:
        story += section("Work Experience")
        for exp in content.experience:
            story.append(Paragraph(exp.title, job_title_style))
            story.append(Paragraph(f"{exp.company}  —  {exp.dates}", job_meta_style))
            for bullet in exp.bullets:
                story.append(Paragraph(f"• {bullet}", bullet_style))
            story.append(Spacer(1, 4))

    # Education
    if content.education:
        story += section("Education")
        for edu in content.education:
            story.append(Paragraph(edu.degree, job_title_style))
            story.append(Paragraph(f"{edu.school}  —  {edu.year}", job_meta_style))

    doc.build(story)


def _build_docx(content: TailoredResumeContent, contact: dict, out_path: Path) -> None:
    from docx import Document
    from docx.shared import Pt
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    doc = Document()

    name = contact.get("name", "")
    if name:
        h = doc.add_heading(name, level=0)
        h.alignment = WD_ALIGN_PARAGRAPH.CENTER

    contact_parts = [v for k, v in contact.items() if k != "name" and v]
    if contact_parts:
        p = doc.add_paragraph(" · ".join(contact_parts))
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.runs[0].font.size = Pt(9)

    def add_section(title: str):
        doc.add_heading(title, level=2)

    if content.summary:
        add_section("Summary")
        doc.add_paragraph(content.summary)

    if content.skills:
        add_section("Skills")
        doc.add_paragraph(" · ".join(content.skills))

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
    docx_path = job_dir / "resume.docx"

    # DOCX always — python-docx is pure Python, no system deps
    _build_docx(content, contact, docx_path)
    content.docx_path = str(docx_path)

    # PDF — requires reportlab; give a clear error if missing
    if not _REPORTLAB_OK:
        raise RuntimeError(
            "reportlab is not installed. Run: pip install reportlab==4.2.5\n"
            "Your DOCX was generated successfully at: " + str(docx_path)
        )
    pdf_path = job_dir / "resume.pdf"
    _build_pdf(content, contact, pdf_path)
    content.pdf_path = str(pdf_path)

    return content
