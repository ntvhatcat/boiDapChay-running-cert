#!/usr/bin/env python3
"""
translate_to_pdf.py
Reads English MD files, translates to Vietnamese via Google Translate,
and generates Vietnamese PDFs in the Vietnamese/ folder.

Run:  py translate_to_pdf.py
Deps: pip install fpdf2 deep-translator
"""

import sys, re, time, textwrap
from pathlib import Path

# ── Auto-install deps ─────────────────────────────────────────────
def ensure(module, pkg):
    try:
        __import__(module)
    except ImportError:
        import subprocess
        print(f"Installing {pkg}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", pkg, "-q"])

ensure("fpdf", "fpdf2")
ensure("deep_translator", "deep-translator")

import ssl, urllib.request
ssl._create_default_https_context = ssl._create_unverified_context   # corporate proxy fix

import requests
requests.packages.urllib3.disable_warnings()
_orig_send = requests.Session.send
def _no_verify_send(self, *a, **kw):
    kw['verify'] = False
    return _orig_send(self, *a, **kw)
requests.Session.send = _no_verify_send

from fpdf import FPDF
from deep_translator import GoogleTranslator

# ── Paths ─────────────────────────────────────────────────────────
ENGLISH_DIR    = Path("English")
VIETNAMESE_DIR = Path("Vietnamese")
VIETNAMESE_DIR.mkdir(exist_ok=True)

# Windows fonts that support Vietnamese
FONT_REG  = "C:/Windows/Fonts/arial.ttf"
FONT_BOLD = "C:/Windows/Fonts/arialbd.ttf"
FONT_ITAL = "C:/Windows/Fonts/ariali.ttf"

# Fallback: use built-in helvetica (may not render tones perfectly)
USE_UNICODE = Path(FONT_REG).exists()

# ── Translator ────────────────────────────────────────────────────
translator = GoogleTranslator(source="en", target="vi")

def translate(text: str) -> str:
    """Translate a chunk of text, retry on failure."""
    text = text.strip()
    if not text or len(text) < 3:
        return text
    # Don't translate image paths or URLs
    if text.startswith("![") or text.startswith("http"):
        return text
    for attempt in range(3):
        try:
            result = translator.translate(text)
            time.sleep(0.15)   # gentle rate-limit
            return result or text
        except Exception as e:
            if attempt == 2:
                print(f"    [translate failed: {e}]")
                return text
            time.sleep(1)
    return text


# ── PDF class ─────────────────────────────────────────────────────
class VIPDF(FPDF):
    def __init__(self):
        super().__init__()
        self.set_margins(18, 18, 18)
        self.set_auto_page_break(True, margin=18)
        if USE_UNICODE:
            self.add_font("fnt",  "",  FONT_REG)
            self.add_font("fnt",  "B", FONT_BOLD)
            try:
                self.add_font("fnt", "I", FONT_ITAL)
            except Exception:
                pass
            self._fname = "fnt"
        else:
            self._fname = "Helvetica"

    def footer(self):
        self.set_y(-13)
        self.set_font(self._fname, "", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 8, f"Trang {self.page_no()}", align="C")
        self.set_text_color(0, 0, 0)

    def _f(self, style="", size=11):
        self.set_font(self._fname, style, size)

    def h1(self, text):
        self._f("B", 20)
        self.set_text_color(26, 58, 107)
        self.multi_cell(0, 10, text, align="L")
        self.ln(2)
        self.set_draw_color(26, 58, 107)
        self.set_line_width(0.5)
        self.line(self.get_x(), self.get_y(), self.w - 18, self.get_y())
        self.ln(4)
        self.set_text_color(0, 0, 0)

    def h2(self, text):
        self.ln(3)
        self._f("B", 14)
        self.set_text_color(0, 122, 77)
        self.multi_cell(0, 8, text, align="L")
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def h3(self, text):
        self.ln(2)
        self._f("B", 12)
        self.set_text_color(51, 65, 85)
        self.multi_cell(0, 7, text, align="L")
        self.ln(1)
        self.set_text_color(0, 0, 0)

    def h4(self, text):
        self.ln(1)
        self._f("B", 11)
        self.multi_cell(0, 7, text, align="L")
        self.set_text_color(0, 0, 0)

    def para(self, text):
        self._f("", 10.5)
        self.set_x(self.l_margin)
        try:
            self.multi_cell(self.epw, 6, text, align="J")
        except Exception:
            pass
        self.ln(2)

    def bullet(self, text, level=0):
        self._f("", 10.5)
        indent = 4 + level * 5
        bullet_char = "-" if level == 0 else ("*" if level == 1 else "+")
        self.set_x(self.l_margin + indent)
        try:
            self.multi_cell(self.epw - indent, 6, f"{bullet_char}  {text}", align="L")
        except Exception:
            pass
        self.ln(0.5)

    def blockquote(self, text):
        self._f("I", 10)
        self.set_text_color(71, 85, 105)
        self.set_fill_color(241, 245, 249)
        self.set_x(24)
        self.multi_cell(self.w - 42, 6, text, align="L", fill=True)
        self.ln(2)
        self.set_text_color(0, 0, 0)

    def hr(self):
        self.ln(3)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.3)
        self.line(18, self.get_y(), self.w - 18, self.get_y())
        self.ln(4)

    def note(self, text):
        """Callout box for > blockquotes."""
        self.blockquote(text)


# ── Markdown parser → PDF ─────────────────────────────────────────
_BOLD_RE   = re.compile(r'\*\*(.+?)\*\*')
_ITALIC_RE = re.compile(r'\*(.+?)\*')

def strip_md_inline(text):
    """Remove inline markdown markers for plain text."""
    text = _BOLD_RE.sub(r'\1', text)
    text = _ITALIC_RE.sub(r'\1', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', '', text)   # remove images
    return text.strip()


def render_md_to_pdf(pdf: VIPDF, lines: list[str]):
    """Walk through translated MD lines and write to PDF."""
    i = 0
    while i < len(lines):
        line = lines[i]
        raw  = line.rstrip()

        # Blank line
        if not raw:
            i += 1
            continue

        # HR
        if re.match(r'^---+$', raw):
            pdf.hr()
            i += 1
            continue

        # Headings
        m = re.match(r'^(#{1,4})\s+(.*)', raw)
        if m:
            level = len(m.group(1))
            text  = strip_md_inline(m.group(2))
            if level == 1:   pdf.h1(text)
            elif level == 2: pdf.h2(text)
            elif level == 3: pdf.h3(text)
            else:            pdf.h4(text)
            i += 1
            continue

        # Blockquote
        if raw.startswith('>'):
            text = strip_md_inline(raw.lstrip('> '))
            pdf.note(text)
            i += 1
            continue

        # Bullet list
        m = re.match(r'^(\s*)[-*]\s+(.*)', raw)
        if m:
            level = len(m.group(1)) // 2
            text  = strip_md_inline(m.group(2))
            pdf.bullet(text, level)
            i += 1
            continue

        # Numbered list
        m = re.match(r'^(\s*)\d+\.\s+(.*)', raw)
        if m:
            level = len(m.group(1)) // 2
            text  = strip_md_inline(m.group(2))
            pdf.bullet(text, level)
            i += 1
            continue

        # Table – skip (complex to render, just skip)
        if raw.startswith('|'):
            while i < len(lines) and lines[i].startswith('|'):
                i += 1
            continue

        # Regular paragraph – collect continuation lines
        para_lines = [raw]
        i += 1
        while i < len(lines) and lines[i].strip() and not lines[i].startswith('#') \
              and not lines[i].startswith('>') and not re.match(r'^\s*[-*\d]', lines[i]) \
              and not lines[i].startswith('|') and not re.match(r'^---+$', lines[i]):
            para_lines.append(lines[i].rstrip())
            i += 1

        text = strip_md_inline(' '.join(para_lines))
        if text:
            pdf.para(text)


# ── Main ──────────────────────────────────────────────────────────
def translate_md_file(md_path: Path) -> list[str]:
    """Read an MD file and return a list of translated lines."""
    raw_lines = md_path.read_text(encoding="utf-8").splitlines()
    translated = []

    # Group lines into chunks for translation to reduce API calls
    chunk_lines = []

    def flush_chunk():
        if not chunk_lines: return
        joined = "\n".join(chunk_lines)
        result = translate(joined)
        translated.extend(result.splitlines())
        chunk_lines.clear()

    for line in raw_lines:
        stripped = line.strip()

        # Pass structural markers through untouched
        if (not stripped or
            stripped.startswith('#') or
            stripped.startswith('---') or
            stripped.startswith('|') or
            stripped.startswith('![') or
            re.match(r'^[-*]\s', stripped) or
            re.match(r'^\d+\.\s', stripped) or
            stripped.startswith('>')):

            flush_chunk()
            # Translate the label text in headings/bullets
            m = re.match(r'^(#{1,4}\s+)(.*)', stripped)
            if m:
                prefix = m.group(1)
                text   = m.group(2)
                translated.append(prefix + translate(text))
            elif re.match(r'^(\s*[-*]\s+)(.*)', stripped):
                mm = re.match(r'^(\s*[-*]\s+)(.*)', stripped)
                translated.append(mm.group(1) + translate(mm.group(2)))
            elif re.match(r'^(\s*\d+\.\s+)(.*)', stripped):
                mm = re.match(r'^(\s*\d+\.\s+)(.*)', stripped)
                translated.append(mm.group(1) + translate(mm.group(2)))
            elif stripped.startswith('>'):
                translated.append('> ' + translate(stripped.lstrip('> ')))
            else:
                translated.append(line)
        else:
            # Accumulate paragraph text
            chunk_lines.append(line)

    flush_chunk()
    return translated


def process_module(md_path: Path):
    stem       = md_path.stem
    out_path   = VIETNAMESE_DIR / (stem + ".pdf")

    if out_path.exists():
        print(f"  SKIP  {stem} (already exists)")
        return

    print(f"  Translating  {stem} ...")
    translated_lines = translate_md_file(md_path)

    print(f"  Generating PDF ...")
    pdf = VIPDF()
    pdf.add_page()
    render_md_to_pdf(pdf, translated_lines)

    pdf.output(str(out_path))
    print(f"  -> {out_path}")


def main():
    md_files = sorted(ENGLISH_DIR.glob("*.md"))
    if not md_files:
        print("No .md files found in English/. Run md_to_js.py first.")
        return

    print(f"Found {len(md_files)} MD files to translate\n")
    for md in md_files:
        process_module(md)

    print(f"\nDone! Vietnamese PDFs saved to {VIETNAMESE_DIR}/")
    print("Update index.html ITEMS to point to Vietnamese/ folder when VI is selected.")


if __name__ == "__main__":
    main()
