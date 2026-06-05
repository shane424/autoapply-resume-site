import re
import shutil
from pathlib import Path
from app.models.resume import TailoredResumeContent, ParsedResume

STORAGE_DIR = Path(__file__).parent.parent.parent / "storage" / "tailored"


def _safe_filename(name: str) -> str:
    """Convert a name like 'Shane Smith' -> 'Shane_Smith', stripping unsafe chars."""
    name = name.strip()
    name = re.sub(r"[^\w\s-]", "", name)
    return re.sub(r"\s+", "_", name)

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
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

    NAVY   = colors.HexColor("#1B3A5C")
    GRAY   = colors.HexColor("#555555")
    BLACK  = colors.HexColor("#111111")

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=letter,
        leftMargin=inch * 0.75,
        rightMargin=inch * 0.75,
        topMargin=inch * 0.55,
        bottomMargin=inch * 0.55,
    )

    # Page width available for content
    page_w = letter[0] - inch * 1.5

    name_style = ParagraphStyle(
        "Name", fontSize=22, fontName="Helvetica-Bold",
        alignment=1, textColor=BLACK, spaceAfter=0,
    )
    contact_style = ParagraphStyle(
        "Contact", fontSize=9, fontName="Helvetica",
        alignment=1, textColor=GRAY, spaceAfter=0,
    )
    section_style = ParagraphStyle(
        "Section", fontSize=10, fontName="Helvetica-Bold",
        textColor=NAVY, spaceBefore=12, spaceAfter=0, tracking=60,
    )
    body_style = ParagraphStyle(
        "Body", fontSize=10, fontName="Helvetica",
        leading=14, spaceAfter=4, textColor=BLACK,
    )
    bullet_style = ParagraphStyle(
        "Bullet", fontSize=9.5, fontName="Helvetica",
        leading=13, leftIndent=16, firstLineIndent=-10,
        spaceAfter=2, textColor=BLACK,
    )
    job_title_style = ParagraphStyle(
        "JobTitle", fontSize=10.5, fontName="Helvetica-Bold",
        textColor=BLACK, spaceAfter=0, spaceBefore=4,
    )
    dates_style = ParagraphStyle(
        "Dates", fontSize=9.5, fontName="Helvetica",
        textColor=GRAY, alignment=2,  # right-aligned
    )
    company_style = ParagraphStyle(
        "Company", fontSize=9.5, fontName="Helvetica-Oblique",
        textColor=GRAY, spaceAfter=3,
    )

    def _hr(color=NAVY, thickness=0.75):
        t = Table([[""]], colWidths=[page_w])
        t.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), thickness, color),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return t

    def section(title: str) -> list:
        # Spacer before rule — spaceAfter on Paragraph is ignored before a Table
        return [Paragraph(title.upper(), section_style), Spacer(1, 3), _hr(), Spacer(1, 5)]

    def exp_header(title: str, dates: str) -> Table:
        # Job title left, dates right on same line
        row = [[Paragraph(title, job_title_style), Paragraph(dates, dates_style)]]
        t = Table(row, colWidths=[page_w * 0.72, page_w * 0.28])
        t.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ]))
        return t

    story = []

    # ── Header ────────────────────────────────────────────────────────────────
    name = contact.get("name", "")
    if name:
        story.append(Paragraph(name.upper(), name_style))
        story.append(Spacer(1, 10))

    contact_parts = [v for k, v in contact.items() if k != "name" and v]
    if contact_parts:
        story.append(Paragraph("  ·  ".join(contact_parts), contact_style))

    # Thin navy rule under header — explicit spacers needed because reportlab
    # ignores paragraph spaceAfter when the next element is a Table
    story.append(Spacer(1, 6))
    story.append(_hr(color=NAVY, thickness=1.0))
    story.append(Spacer(1, 8))

    # ── Summary ───────────────────────────────────────────────────────────────
    if content.summary:
        story += section("Summary")
        story.append(Paragraph(content.summary, body_style))

    # ── Skills ────────────────────────────────────────────────────────────────
    if content.skills:
        story += section("Skills & Technologies")
        story.append(Paragraph("  ·  ".join(content.skills), body_style))

    # ── Experience ────────────────────────────────────────────────────────────
    if content.experience:
        story += section("Work Experience")
        for exp in content.experience:
            story.append(exp_header(exp.title, exp.dates))
            story.append(Paragraph(exp.company, company_style))
            for bullet in exp.bullets:
                story.append(Paragraph(f"•  {bullet}", bullet_style))
            story.append(Spacer(1, 3))

    # ── Education ─────────────────────────────────────────────────────────────
    if content.education:
        story += section("Education")
        for edu in content.education:
            story.append(exp_header(edu.degree, edu.year))
            story.append(Paragraph(edu.school, company_style))

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


def build_resume(
    content: TailoredResumeContent,
    original_resume: ParsedResume,
    job_company: str = "",
) -> TailoredResumeContent:
    from app.config import load_app_settings, env_settings
    from datetime import datetime

    job_dir = STORAGE_DIR / content.job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    contact = original_resume.contact
    name = contact.get("name", "")
    # Title-case handles all-caps PDF names: "SHANE SMITH" → "Shane_Smith"
    stem = _safe_filename(name.title()) if name else "Resume"

    docx_path = job_dir / f"{stem}.docx"
    _build_docx(content, contact, docx_path)
    content.docx_path = str(docx_path)

    if content.cover_letter.strip():
        cl_path = job_dir / f"{stem}_Cover_Letter.txt"
        cl_path.write_text(content.cover_letter, encoding="utf-8")
        content.cover_letter_path = str(cl_path)

    if not _REPORTLAB_OK:
        raise RuntimeError(
            "reportlab is not installed. Run: pip install reportlab==4.2.5\n"
            "Your DOCX was generated successfully at: " + str(docx_path)
        )
    pdf_path = job_dir / f"{stem}.pdf"
    _build_pdf(content, contact, pdf_path)
    content.pdf_path = str(pdf_path)

    # Copy to user-configured output directory (.env OUTPUT_DIR overrides config.yaml)
    settings = load_app_settings()
    resolved_output_dir = env_settings.output_dir.strip() or settings.output_dir.strip()
    if resolved_output_dir:
        today = datetime.now()
        date_str   = f"{today.month}{today.day:02d}{today.year}"
        time_str   = f"{today.hour:02d}{today.minute:02d}"
        _generic = {"unknown company", "unknown", "unknown position", ""}
        try:
            clean_company = (job_company or "").strip()
            if clean_company.lower() not in _generic:
                company_slug = _safe_filename(clean_company).lower()
                folder = f"{company_slug}_{date_str}"
            else:
                folder = f"{date_str}_{time_str}"
            dest_dir = Path(resolved_output_dir) / folder
            dest_dir.mkdir(parents=True, exist_ok=True)
            out_pdf  = dest_dir / f"{stem}.pdf"
            out_docx = dest_dir / f"{stem}.docx"
            shutil.copy2(pdf_path,  out_pdf)
            shutil.copy2(docx_path, out_docx)
            content.pdf_path  = str(out_pdf)
            content.docx_path = str(out_docx)
            if content.cover_letter.strip():
                out_cl = dest_dir / f"{stem}_Cover_Letter.txt"
                out_cl.write_text(content.cover_letter, encoding="utf-8")
                content.cover_letter_path = str(out_cl)
            print(f"[resume_builder] Saved to: {out_pdf}")
        except Exception as e:
            import traceback
            print(f"[resume_builder] ERROR copying to output_dir '{settings.output_dir}': {e}")
            traceback.print_exc()
            print(f"[resume_builder] File is available at fallback path: {pdf_path}")
    else:
        print(f"[resume_builder] output_dir not set — file at: {pdf_path}")

    return content
