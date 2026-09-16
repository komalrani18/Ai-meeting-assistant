"""
Renders the final meeting report (summary + action items) as a downloadable PDF.
"""
from datetime import datetime
from typing import List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
)

from app.schemas import ActionItem


def render_pdf(
    output_path: str,
    filename: str,
    summary: str,
    action_items: List[ActionItem],
    duration_seconds: float = None,
    word_count: int = 0,
    num_chunks: int = 1,
):
    doc = SimpleDocTemplate(
        output_path, pagesize=letter,
        topMargin=0.75 * inch, bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleCustom", parent=styles["Title"], fontSize=20, spaceAfter=4
    )
    meta_style = ParagraphStyle(
        "Meta", parent=styles["Normal"], textColor=colors.grey, fontSize=9, spaceAfter=16
    )
    heading_style = ParagraphStyle(
        "HeadingCustom", parent=styles["Heading2"], spaceBefore=16, spaceAfter=8
    )
    body_style = ParagraphStyle("BodyCustom", parent=styles["Normal"], fontSize=11, leading=16)

    story = []
    story.append(Paragraph("Meeting Summary Report", title_style))

    duration_str = f"{duration_seconds / 60:.1f} min" if duration_seconds else "unknown"
    meta_line = (
        f"Source file: {filename} &nbsp;|&nbsp; Duration: {duration_str} &nbsp;|&nbsp; "
        f"Transcript length: {word_count} words &nbsp;|&nbsp; Chunks processed: {num_chunks} "
        f"&nbsp;|&nbsp; Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    story.append(Paragraph(meta_line, meta_style))

    story.append(Paragraph("Executive Summary", heading_style))
    story.append(Paragraph(summary or "No summary available.", body_style))

    story.append(Paragraph("Action Items", heading_style))
    if action_items:
        table_data = [["Person", "Action", "Deadline"]]
        for item in action_items:
            table_data.append([item.person, item.action, item.deadline])

        table = Table(table_data, colWidths=[1.3 * inch, 3.4 * inch, 1.3 * inch])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("FONTSIZE", (0, 0), (-1, -1), 9.5),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d1d5db")),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                    ("TOPPADDING", (0, 0), (-1, -1), 6),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        story.append(table)
    else:
        story.append(Paragraph("No action items were identified in this meeting.", body_style))

    story.append(Spacer(1, 24))
    story.append(
        Paragraph(
            "Generated automatically by the AI Meeting Assistant. Please verify action "
            "items and deadlines against the full transcript before acting on them.",
            meta_style,
        )
    )

    doc.build(story)
    return output_path
