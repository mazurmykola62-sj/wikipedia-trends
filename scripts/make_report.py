#!/usr/bin/env python3
"""
Assemble a one-page, shareable PDF report: title, chart, a compact stats
table per series, a confidence/limitations callout, and narrative bullets
the agent writes (findings + recommendation). This is the deliverable
the user actually shares with a co-founder or in a slide -- keep it dense
but readable, not a data dump.

The narrative text (findings/recommendation/limitations) is supplied by the
calling agent, not invented by this script, because turning numbers into a
recommendation ("which language to localize into next and why") requires
judgment the script doesn't have. This script's job is layout, not writing.

Usage:
    python make_report.py --analysis analysis.json --chart chart.png \\
        --title "Intermittent fasting: PL vs CS Wikipedia" \\
        --findings findings.json --output report.pdf

findings.json shape:
{
  "summary": "One or two sentence headline takeaway.",
  "bullets": ["finding 1", "finding 2", "..."],
  "recommendation": "One or two sentences of what to do next.",
  "limitations": ["optional extra caveat beyond the automatic confidence notes"]
}

Output (stdout): compact JSON summary with the output path.
"""
import argparse
import json
from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, KeepTogether
)

from common import print_summary, ensure_parent

SKILL_ROOT = Path(__file__).resolve().parent.parent

# Findings can be in any language the user works in (Ukrainian, Polish, Czech,
# etc.), and Helvetica's built-in reportlab encoding only covers Latin-1 --
# Cyrillic and many Latin Extended-A characters (ą, ř, ł...) render as blank
# boxes with it. Register a bundled Unicode font instead of relying on
# whatever's on the host system, so this works the same everywhere.
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"


def register_unicode_font():
    global FONT_REGULAR, FONT_BOLD
    candidates = [
        (SKILL_ROOT / "assets" / "fonts" / "DejaVuSans.ttf", SKILL_ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"),
        (Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"), Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")),
    ]
    for regular, bold in candidates:
        if regular.exists() and bold.exists():
            pdfmetrics.registerFont(TTFont("DejaVuSans", str(regular)))
            pdfmetrics.registerFont(TTFont("DejaVuSans-Bold", str(bold)))
            FONT_REGULAR, FONT_BOLD = "DejaVuSans", "DejaVuSans-Bold"
            return
    # No Unicode font found anywhere -- fall back to Helvetica. Non-Latin-1
    # text (e.g. Ukrainian findings) will render as blank boxes; warn loudly.
    import sys
    print("WARNING: no Unicode TTF font found; non-Latin-1 text (e.g. Cyrillic) "
          "will not render correctly in the PDF. Check assets/fonts/ is intact.", file=sys.stderr)


def build_styles():
    register_unicode_font()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="ReportTitle", fontSize=17, leading=21, spaceAfter=4, fontName=FONT_BOLD))
    styles.add(ParagraphStyle(name="Subtitle", fontSize=10, leading=13, textColor=colors.HexColor("#555555"), spaceAfter=10, fontName=FONT_REGULAR))
    styles.add(ParagraphStyle(name="SectionHead", fontSize=11, leading=14, spaceBefore=8, spaceAfter=4, fontName=FONT_BOLD))
    styles.add(ParagraphStyle(name="Body", fontSize=9.5, leading=13, fontName=FONT_REGULAR))
    styles.add(ParagraphStyle(name="ReportBullet", fontSize=9.5, leading=13, leftIndent=12, bulletIndent=0, fontName=FONT_REGULAR))
    styles.add(ParagraphStyle(name="Footnote", fontSize=7.5, leading=10, textColor=colors.HexColor("#777777"), fontName=FONT_REGULAR))
    return styles


def confidence_color(label: str) -> str:
    return {"High": "#2E7D32", "Medium": "#B8862B", "Low": "#C0392B"}.get(label, "#555555")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analysis", required=True)
    ap.add_argument("--chart", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--findings", required=True, help="JSON file: summary, bullets, recommendation, limitations")
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    with open(args.analysis, "r", encoding="utf-8") as f:
        analysis = json.load(f)
    with open(args.findings, "r", encoding="utf-8") as f:
        findings = json.load(f)

    styles = build_styles()
    story = []

    story.append(Paragraph(args.title, styles["ReportTitle"]))
    date_ranges = {tuple(s["date_range"]) for s in analysis["series"] if "date_range" in s}
    range_str = ", ".join(f"{a}\u2013{b}" for a, b in date_ranges)
    story.append(Paragraph(f"Source: Wikimedia Pageviews API &nbsp;|&nbsp; Period: {range_str}", styles["Subtitle"]))

    if findings.get("summary"):
        story.append(Paragraph(findings["summary"], styles["Body"]))
        story.append(Spacer(1, 6))

    story.append(Image(args.chart, width=6.6 * inch, height=6.6 * inch * 0.47))
    story.append(Spacer(1, 6))

    story.append(Paragraph("Key numbers", styles["SectionHead"]))
    table_data = [["Series", "Total views", "Annualized trend", "YoY change", "Confidence"]]
    for s in analysis["series"]:
        if "trend" not in s:
            continue
        growth = s["trend"].get("annual_growth_rate")
        growth_str = f"{growth:+.0%}" if growth is not None else "n/a"
        yoy = s.get("year_over_year_change")
        yoy_str = f"{yoy:+.0%}" if yoy is not None else "n/a"
        table_data.append([
            s["name"], f"{s['total_views']:,}", growth_str, yoy_str, s["confidence"]["label"],
        ])
    t = Table(table_data, colWidths=[1.3 * inch, 1.1 * inch, 1.3 * inch, 1.1 * inch, 1.0 * inch])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("FONTNAME", (0, 1), (-1, -1), FONT_REGULAR),
        ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
        ("LINEBELOW", (0, 0), (-1, 0), 0.75, colors.HexColor("#333333")),
        ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#dddddd")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(t)
    story.append(Spacer(1, 6))

    if findings.get("bullets"):
        story.append(Paragraph("Findings", styles["SectionHead"]))
        for b in findings["bullets"]:
            story.append(Paragraph(f"\u2022 {b}", styles["ReportBullet"]))

    if findings.get("recommendation"):
        story.append(Paragraph("Recommendation", styles["SectionHead"]))
        story.append(Paragraph(findings["recommendation"], styles["Body"]))

    limitations = list(findings.get("limitations", []))
    for s in analysis["series"]:
        for reason in s.get("confidence", {}).get("reasons", []):
            note = f"{s['name']}: {reason}"
            if note not in limitations:
                limitations.append(note)
    if limitations:
        story.append(Paragraph("Assumptions & limitations", styles["SectionHead"]))
        for l in limitations[:8]:
            story.append(Paragraph(f"\u2022 {l}", styles["ReportBullet"]))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "Pageview interest is a proxy for attention, not willingness to pay or long-term retention. "
        "Growth rates are estimated with a log-linear fit on 7-day-smoothed views; see methodology.md for details.",
        styles["Footnote"],
    ))

    out_path = ensure_parent(args.output)
    doc = SimpleDocTemplate(
        str(out_path), pagesize=letter,
        topMargin=0.55 * inch, bottomMargin=0.55 * inch, leftMargin=0.6 * inch, rightMargin=0.6 * inch,
    )
    doc.build(story)

    print_summary({"status": "ok", "output_file": str(out_path)})


if __name__ == "__main__":
    main()
