"""Generate a sample Hebrew PDF with text + table for testing."""
import os
import sys

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


def main(out_path: str) -> int:
    # Register a Unicode-capable font that supports Hebrew.
    pdfmetrics.registerFont(TTFont("Arial", "C:/Windows/Fonts/Arial.ttf"))
    pdfmetrics.registerFont(TTFont("ArialBold", "C:/Windows/Fonts/Arialbd.ttf"))

    styles = getSampleStyleSheet()
    rtl_style = ParagraphStyle(
        name="RTL",
        parent=styles["Normal"],
        fontName="Arial",
        fontSize=12,
        alignment=2,  # right
        leading=16,
    )
    title_style = ParagraphStyle(
        name="RTLTitle",
        parent=styles["Heading1"],
        fontName="ArialBold",
        fontSize=16,
        alignment=2,
        leading=20,
    )

    doc = SimpleDocTemplate(out_path, pagesize=A4)
    story = []

    story.append(Paragraph("דוח מכירות רבעוני", title_style))
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "בשנת 2024 הציגה החברה צמיחה משמעותית במכירות. "
            "הרבעון הראשון הסתיים עם הכנסות של 1,250,000 ש\"ח, "
            "והרבעון השני עלה ל-1,480,000 ש\"ח. ",
            rtl_style,
        )
    )
    story.append(Spacer(1, 0.5 * cm))

    table_data = [
        ["סך הכל", "מערב", "מרכז", "צפון", "אזור / רבעון"],
        ["1,250,000", "300,000", "500,000", "450,000", "Q1 2024"],
        ["1,480,000", "380,000", "600,000", "500,000", "Q2 2024"],
        ["1,620,000", "420,000", "650,000", "550,000", "Q3 2024"],
        ["1,790,000", "470,000", "720,000", "600,000", "Q4 2024"],
    ]
    tbl = Table(table_data, hAlign="RIGHT")
    tbl.setStyle(
        TableStyle(
            [
                ("FONT", (0, 0), (-1, -1), "Arial", 11),
                ("FONT", (0, 0), (-1, 0), "ArialBold", 11),
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 0.5 * cm))
    story.append(
        Paragraph(
            "סיכום: סך המכירות לשנה עמד על 6,140,000 ש\"ח. "
            "אזור המרכז הוביל בכל הרבעונים.",
            rtl_style,
        )
    )

    doc.build(story)
    print(f"Wrote {out_path}, size={os.path.getsize(out_path)} bytes")
    return 0


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "tools/scripts/sample_hebrew.pdf"
    sys.exit(main(out))
