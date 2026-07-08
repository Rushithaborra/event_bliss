"""Generate PROJECT_DOCUMENTATION.pdf from PROJECT_DOCUMENTATION.md"""
from fpdf import FPDF
import re

MD_PATH  = "PROJECT_DOCUMENTATION.md"
PDF_PATH = "PROJECT_DOCUMENTATION.pdf"

# ── Colour palette ────────────────────────────────────────────────────────────
PURPLE      = (106, 76, 147)   # headings
DARK_PURPLE = (72,  48, 110)   # H1
LIGHT_BG    = (245, 243, 250)  # code block bg
BORDER_CLR  = (200, 190, 220)  # table / code borders
TEXT        = (30,  30,  40)   # body text
MUTED       = (100, 90, 120)   # table header text
WHITE       = (255, 255, 255)
TABLE_HDR   = (220, 212, 235)  # table header row fill
TABLE_ROW1  = (255, 255, 255)
TABLE_ROW2  = (248, 245, 253)


ARIAL_UNICODE = "/Library/Fonts/Arial Unicode.ttf"

class DocPDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_font("AU", style="",  fname=ARIAL_UNICODE, uni=True)
        self.add_font("AU", style="B", fname=ARIAL_UNICODE, uni=True)
        self.add_font("AU", style="I", fname=ARIAL_UNICODE, uni=True)

    def header(self):
        self.set_font("AU", "B", 9)
        self.set_text_color(*PURPLE)
        self.cell(0, 8, "EventBliss — Event Management System", align="L")
        self.set_draw_color(*PURPLE)
        self.set_line_width(0.4)
        self.line(self.l_margin, self.get_y() + 8,
                  self.w - self.r_margin, self.get_y() + 8)
        self.ln(10)
        self.set_draw_color(0, 0, 0)

    def footer(self):
        self.set_y(-13)
        self.set_font("AU", "", 8)
        self.set_text_color(*MUTED)
        self.cell(0, 10,
                  f"Project by Rushitha Borra  |  Page {self.page_no()}",
                  align="C")


def render_pdf(md_path, pdf_path):
    with open(md_path, encoding="utf-8") as f:
        lines = f.readlines()

    pdf = DocPDF(orientation="P", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_margins(18, 18, 18)
    pdf.add_page()

    # ── state ─────────────────────────────────────────────────────────────────
    in_code   = False
    in_table  = False
    code_buf  = []
    tbl_rows  = []
    tbl_sep   = []   # which row indices are separator rows

    def flush_code():
        nonlocal code_buf
        if not code_buf:
            return
        pw = pdf.w - pdf.l_margin - pdf.r_margin
        pad = 4
        line_h = 5.2
        block_h = len(code_buf) * line_h + pad * 2

        # Background box
        x0, y0 = pdf.get_x(), pdf.get_y()
        if y0 + block_h > pdf.h - pdf.b_margin:
            pdf.add_page()
            x0, y0 = pdf.get_x(), pdf.get_y()

        pdf.set_fill_color(*LIGHT_BG)
        pdf.set_draw_color(*BORDER_CLR)
        pdf.set_line_width(0.3)
        pdf.rect(x0, y0, pw, block_h, style="FD")

        pdf.set_font("AU", "", 8)
        pdf.set_text_color(*TEXT)
        pdf.set_x(x0 + pad)
        pdf.set_y(y0 + pad)

        for cl in code_buf:
            cl = cl.rstrip("\n")
            # Truncate very long lines
            while pdf.get_string_width(cl) > pw - pad * 2 - 2:
                cl = cl[:-1]
            pdf.set_x(x0 + pad)
            pdf.cell(pw - pad * 2, line_h, cl, ln=True)

        pdf.set_y(y0 + block_h + 2)
        pdf.set_draw_color(0, 0, 0)
        pdf.set_line_width(0.2)
        code_buf = []

    def flush_table():
        nonlocal tbl_rows, tbl_sep
        if not tbl_rows:
            return

        pw     = pdf.w - pdf.l_margin - pdf.r_margin
        n_cols = max(len(r) for r in tbl_rows)
        if n_cols == 0:
            tbl_rows, tbl_sep = [], []
            return

        # Auto-column widths: equal split
        col_w = pw / n_cols
        row_h = 6.5

        for ridx, row in enumerate(tbl_rows):
            is_header = (ridx == 0)
            fill = TABLE_HDR if is_header else (TABLE_ROW1 if ridx % 2 == 0 else TABLE_ROW2)

            # Check page break
            if pdf.get_y() + row_h > pdf.h - pdf.b_margin:
                pdf.add_page()

            pdf.set_fill_color(*fill)
            pdf.set_draw_color(*BORDER_CLR)
            pdf.set_line_width(0.2)

            # Pad row to n_cols
            while len(row) < n_cols:
                row.append("")

            for cidx, cell in enumerate(row[:n_cols]):
                cell = cell.strip()
                # Strip inline markdown bold
                cell = re.sub(r'\*\*(.+?)\*\*', r'\1', cell)
                cell = re.sub(r'`(.+?)`', r'\1', cell)
                if is_header:
                    pdf.set_font("AU", "B", 8)
                    pdf.set_text_color(*DARK_PURPLE)
                else:
                    pdf.set_font("AU", "", 8)
                    pdf.set_text_color(*TEXT)
                pdf.cell(col_w, row_h, cell, border=1, fill=True)
            pdf.ln()

        pdf.ln(2)
        tbl_rows, tbl_sep = [], []

    def emit_text(txt, bold=False, italic=False, size=10, color=TEXT, indent=0, gap=5):
        # Strip inline markdown
        txt = re.sub(r'\*\*(.+?)\*\*', r'\1', txt)
        txt = re.sub(r'\*(.+?)\*',   r'\1', txt)
        txt = re.sub(r'`(.+?)`',     r'\1', txt)
        txt = txt.strip()
        if not txt:
            return
        style = ""
        if bold:   style += "B"
        if italic: style += "I"
        pdf.set_font("AU", style, size)
        pdf.set_text_color(*color)
        pdf.set_x(pdf.l_margin + indent)
        pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - indent,
                       gap, txt, align="L")

    # ── parse ─────────────────────────────────────────────────────────────────
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()

        # ── code fence ───────────────────────────────────────────────────────
        if stripped.startswith("```"):
            if not in_code:
                in_code = True
                code_buf = []
            else:
                in_code = False
                flush_code()
            i += 1
            continue

        if in_code:
            code_buf.append(raw.rstrip("\n"))
            i += 1
            continue

        # ── table ─────────────────────────────────────────────────────────────
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            # Separator row?
            if all(re.match(r'^[-:]+$', c.replace(" ","")) for c in cells if c):
                pass  # skip separator row
            else:
                tbl_rows.append(cells)
            in_table = True
            i += 1
            continue
        else:
            if in_table:
                flush_table()
                in_table = False

        # ── blank line ────────────────────────────────────────────────────────
        if not stripped:
            pdf.ln(3)
            i += 1
            continue

        # ── H1 ───────────────────────────────────────────────────────────────
        if stripped.startswith("# ") and not stripped.startswith("## "):
            flush_code(); flush_table()
            txt = stripped[2:].strip()
            pdf.ln(2)
            pdf.set_font("AU", "B", 18)
            pdf.set_text_color(*DARK_PURPLE)
            pdf.multi_cell(0, 9, txt, align="C")
            # underline
            y = pdf.get_y()
            pdf.set_draw_color(*PURPLE)
            pdf.set_line_width(0.8)
            pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
            pdf.ln(5)
            pdf.set_draw_color(0, 0, 0)
            i += 1
            continue

        # ── H2 ───────────────────────────────────────────────────────────────
        if stripped.startswith("## ") and not stripped.startswith("### "):
            flush_code(); flush_table()
            txt = stripped[3:].strip()
            pdf.ln(4)
            pdf.set_fill_color(*PURPLE)
            pdf.set_text_color(*WHITE)
            pdf.set_font("AU", "B", 13)
            pdf.set_x(pdf.l_margin)
            pdf.cell(pdf.w - pdf.l_margin - pdf.r_margin, 8, f"  {txt}", fill=True, ln=True)
            pdf.ln(3)
            i += 1
            continue

        # ── H3 ───────────────────────────────────────────────────────────────
        if stripped.startswith("### "):
            flush_code(); flush_table()
            txt = stripped[4:].strip()
            # Strip backtick wrapping
            txt = re.sub(r'`(.+?)`', r'\1', txt)
            pdf.ln(3)
            pdf.set_font("AU", "B", 11)
            pdf.set_text_color(*PURPLE)
            pdf.multi_cell(0, 6, txt, align="L")
            # thin underline
            y = pdf.get_y()
            pdf.set_draw_color(*BORDER_CLR)
            pdf.set_line_width(0.3)
            pdf.line(pdf.l_margin, y, pdf.l_margin + 80, y)
            pdf.ln(3)
            pdf.set_draw_color(0, 0, 0)
            i += 1
            continue

        # ── H4 ───────────────────────────────────────────────────────────────
        if stripped.startswith("#### "):
            txt = stripped[5:].strip()
            txt = re.sub(r'`(.+?)`', r'\1', txt)
            pdf.ln(2)
            emit_text(txt, bold=True, size=10, color=DARK_PURPLE, gap=6)
            pdf.ln(1)
            i += 1
            continue

        # ── horizontal rule ──────────────────────────────────────────────────
        if stripped in ("---", "***", "___"):
            pdf.set_draw_color(*BORDER_CLR)
            pdf.set_line_width(0.4)
            pdf.line(pdf.l_margin, pdf.get_y(),
                     pdf.w - pdf.r_margin, pdf.get_y())
            pdf.ln(4)
            pdf.set_draw_color(0, 0, 0)
            i += 1
            continue

        # ── bullet list ──────────────────────────────────────────────────────
        bullet_m = re.match(r'^(\s*)([-*+])\s+(.*)', stripped)
        if bullet_m:
            indent = 4 + len(bullet_m.group(1)) * 2
            txt = "•  " + bullet_m.group(3)
            emit_text(txt, size=9.5, color=TEXT, indent=indent, gap=5.5)
            i += 1
            continue

        # ── numbered list ─────────────────────────────────────────────────────
        num_m = re.match(r'^\d+\.\s+(.*)', stripped)
        if num_m:
            emit_text(num_m.group(1), size=9.5, color=TEXT, indent=6, gap=5.5)
            i += 1
            continue

        # ── bold-only line (used as mini-heading sometimes) ──────────────────
        if stripped.startswith("**") and stripped.endswith("**"):
            emit_text(stripped, bold=True, size=10, color=DARK_PURPLE, gap=6)
            i += 1
            continue

        # ── normal paragraph ─────────────────────────────────────────────────
        emit_text(stripped, size=9.5, color=TEXT, gap=5.5)
        i += 1

    flush_code()
    flush_table()

    pdf.output(pdf_path)
    print(f"PDF saved: {pdf_path}  ({pdf.page} pages)")


if __name__ == "__main__":
    render_pdf(MD_PATH, PDF_PATH)
