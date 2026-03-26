import sys
import io
import time
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT

# ── Capture stdout so we can save agent messages ─────────────────────────────
class Tee(io.TextIOBase):
    """Write to both stdout and a buffer."""
    def __init__(self, original):
        self.original = original
        self.buffer_lines = []

    def write(self, text):
        self.original.write(text)
        self.original.flush()
        if text.strip():
            self.buffer_lines.append(text)
        return len(text)

    def flush(self):
        self.original.flush()

captured = Tee(sys.stdout)
sys.stdout = captured

# ── Run TradingAgents ─────────────────────────────────────────────────────────
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.default_config import DEFAULT_CONFIG

TICKER      = "MSFT"
TRADE_DATE  = "2026-03-25"       # ← always use a past weekday, never today

config = DEFAULT_CONFIG.copy()
config["llm_provider"]      = "ollama"
config["deep_think_llm"]    = "qwen3:8b"
config["quick_think_llm"]   = "qwen3:8b"
config["max_debate_rounds"] = 1
config["max_recur_limit"]   = 5
config["human_in_the_loop"] = False

start = time.time()

sys.stdout = captured.original
sys.stdout = captured

ta = TradingAgentsGraph(debug=True, config=config)
_, decision = ta.propagate(TICKER, TRADE_DATE)

sys.stdout = captured.original
elapsed = time.time() - start
full_log = "".join(captured.buffer_lines)

# ── Build PDF ─────────────────────────────────────────────────────────────────
timestamp  = datetime.now().strftime("%Y%m%d_%H%M%S")
output_pdf = f"TradingAgents_{TICKER}_{timestamp}.pdf"

doc = SimpleDocTemplate(
    output_pdf,
    pagesize=letter,
    leftMargin=0.85 * inch,
    rightMargin=0.85 * inch,
    topMargin=1 * inch,
    bottomMargin=1 * inch,
)

styles = getSampleStyleSheet()

title_style = ParagraphStyle(
    "ReportTitle",
    parent=styles["Title"],
    fontSize=22,
    textColor=colors.HexColor("#1F497D"),
    spaceAfter=4,
    alignment=TA_CENTER,
)
subtitle_style = ParagraphStyle(
    "Subtitle",
    parent=styles["Normal"],
    fontSize=11,
    textColor=colors.HexColor("#555555"),
    spaceAfter=16,
    alignment=TA_CENTER,
)
h1_style = ParagraphStyle(
    "H1",
    parent=styles["Heading1"],
    fontSize=13,
    textColor=colors.HexColor("#1F497D"),
    spaceBefore=14,
    spaceAfter=4,
)
h2_style = ParagraphStyle(
    "H2",
    parent=styles["Heading2"],
    fontSize=11,
    textColor=colors.HexColor("#2E75B6"),
    spaceBefore=10,
    spaceAfter=3,
)
body_style = ParagraphStyle(
    "Body",
    parent=styles["Normal"],
    fontSize=9,
    leading=14,
    spaceAfter=4,
)
code_style = ParagraphStyle(
    "Code",
    parent=styles["Code"],
    fontSize=8,
    leading=12,
    backColor=colors.HexColor("#F5F5F5"),
    leftIndent=12,
    spaceAfter=4,
)
decision_style = ParagraphStyle(
    "Decision",
    parent=styles["Normal"],
    fontSize=11,
    leading=16,
    spaceAfter=6,
    leftIndent=12,
)

def divider():
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#CCCCCC"), spaceAfter=8, spaceBefore=4)

story = []

# ── Cover block ───────────────────────────────────────────────────────────────
story.append(Paragraph("TradingAgents", title_style))
story.append(Paragraph(f"AI Trading Research Report  ·  {TICKER}  ·  {TRADE_DATE}", subtitle_style))
story.append(divider())

# ── Summary metadata table ────────────────────────────────────────────────────
meta_data = [
    ["Ticker",       TICKER,                                    "Analysis Date", TRADE_DATE],
    ["LLM Provider", "Ollama",                                  "Models",        f"{config['deep_think_llm']} / {config['quick_think_llm']}"],
    ["Generated",    datetime.now().strftime("%Y-%m-%d %H:%M"), "Run Time",      f"{elapsed/60:.1f} min"],
]
meta_table = Table(meta_data, colWidths=[1.1*inch, 2.2*inch, 1.3*inch, 2.2*inch])
meta_table.setStyle(TableStyle([
    ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#EAF0F8")),
    ("BACKGROUND",    (2, 0), (2, -1), colors.HexColor("#EAF0F8")),
    ("TEXTCOLOR",     (0, 0), (-1, -1), colors.HexColor("#333333")),
    ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
    ("FONTNAME",      (2, 0), (2, -1), "Helvetica-Bold"),
    ("FONTSIZE",      (0, 0), (-1, -1), 9),
    ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#CCCCCC")),
    ("PADDING",       (0, 0), (-1, -1), 6),
    ("ROWBACKGROUNDS",(0, 0), (-1, -1), [colors.white, colors.HexColor("#FAFAFA")]),
]))
story.append(meta_table)
story.append(Spacer(1, 14))

# ── Final decision ────────────────────────────────────────────────────────────
story.append(Paragraph("Final Trading Decision", h1_style))
story.append(divider())

decision_text = str(decision) if decision else "No decision returned."
for line in decision_text.split("\n"):
    line = line.strip()
    if not line:
        story.append(Spacer(1, 4))
    elif line.startswith("===") or line.startswith("---"):
        story.append(divider())
    else:
        story.append(Paragraph(line, decision_style))
story.append(Spacer(1, 14))

# ── Agent log ─────────────────────────────────────────────────────────────────
story.append(Paragraph("Agent Pipeline Log", h1_style))
story.append(divider())
story.append(Paragraph(
    "The following is the full message trace from all agents during the analysis run.",
    body_style
))
story.append(Spacer(1, 6))

current_section = []
current_heading = None

for raw_line in full_log.split("\n"):
    line = raw_line.rstrip()
    if "Human Message" in line or "Ai Message" in line or "Tool Message" in line:
        if current_heading:
            story.append(Paragraph(current_heading, h2_style))
        if current_section:
            story.append(Paragraph("<br/>".join(current_section), code_style))
            current_section = []
        current_heading = line.strip("= ").strip()
    elif line.strip():
        safe = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        current_section.append(safe)
    else:
        if current_section:
            current_section.append("")

if current_heading:
    story.append(Paragraph(current_heading, h2_style))
if current_section:
    story.append(Paragraph("<br/>".join(current_section), code_style))

# ── Disclaimer ────────────────────────────────────────────────────────────────
story.append(Spacer(1, 20))
story.append(divider())
disclaimer = (
    "<b>Disclaimer:</b> This report is generated by an AI research framework for informational "
    "purposes only. It does not constitute financial advice. No real trades are executed. "
    "Always consult a qualified financial advisor before making investment decisions."
)
story.append(Paragraph(disclaimer, ParagraphStyle(
    "Disclaimer", parent=body_style, fontSize=8,
    textColor=colors.HexColor("#888888"), italic=True
)))

# ── Save ──────────────────────────────────────────────────────────────────────
doc.build(story)
print(f"\n✅  PDF saved: {output_pdf}")
print(f"⏱  Total run time: {elapsed/60:.1f} minutes")
