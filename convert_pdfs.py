#!/usr/bin/env python3
"""
UESCA PDF -> content/all.js  (with inline images)
Reads every PDF in English/, extracts text + images interleaved by
vertical position, and bundles everything into content/all.js.

Run:  py convert_pdfs.py
"""

import re
import html as html_lib
from pathlib import Path
from collections import Counter

try:
    import fitz
except ImportError:
    print("Run: pip install pymupdf")
    exit(1)

ENGLISH_DIR = Path("English")
OUTPUT_DIR  = Path("content")
OUTPUT_FILE = OUTPUT_DIR / "all.js"
IMAGES_DIR  = Path("images")

SECTION_CHAR = ""   # Wingdings bullet used as UESCA section marker
MIN_IMG_W, MIN_IMG_H = 80, 60   # skip tiny decorative images


# ── Helpers ──────────────────────────────────────────────────────

def dominant_size(doc):
    counts = Counter()
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0: continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"].strip():
                        counts[round(span["size"], 1)] += 1
    return counts.most_common(1)[0][0] if counts else 11.0


def spans_to_html(spans):
    out = []
    for span in spans:
        t = span["text"]
        if not t: continue
        flags = span.get("flags", 0)
        font  = span.get("font", "")
        bold   = bool(flags & 16) or "Bold"   in font
        italic = bool(flags & 2)  or "Italic" in font or "Oblique" in font
        t = html_lib.escape(t)
        if bold and italic:  t = f"<strong><em>{t}</em></strong>"
        elif bold:           t = f"<strong>{t}</strong>"
        elif italic:         t = f"<em>{t}</em>"
        out.append(t)
    return "".join(out)


def size_tag(size, body):
    r = size / body if body else 1.0
    if r >= 2.5: return "h1"
    if r >= 1.9: return "h1"
    if r >= 1.4: return "h2"
    if r >= 1.15: return "h3"
    return "p"


BULLET_CHARS = set("•·●○■□▸▹◆◇◦‣⁃")

def is_plain_bullet(text):
    return bool(text) and text[0] in BULLET_CHARS

def is_o_bullet(text):
    return bool(re.match(r'^o\s', text))

def is_numbered(text):
    return bool(re.match(r'^\d+[.)]\s', text)) or bool(re.match(r'^[a-z][.)]\s', text))

def strip_bullet_prefix_html(html_str):
    html_str = re.sub(r'^[•·●○■□▸▹◆◇◦‣⁃]\s*', '', html_str)
    html_str = re.sub(r'^o\s+', '', html_str)
    html_str = re.sub(r'^\d+[.)]\s+', '', html_str)
    html_str = re.sub(r'^[a-z][.)]\s+', '', html_str)
    return html_str.strip()


class ListItem:
    __slots__ = ("html", "children", "numbered")
    def __init__(self, html, numbered=False):
        self.html     = html
        self.children = []
        self.numbered = numbered

    def to_html(self):
        s = f"<li>{self.html}"
        if self.children:
            tag = "ol" if self.children[0].numbered else "ul"
            s += f"<{tag}>"
            for c in self.children: s += c.to_html()
            s += f"</{tag}>"
        s += "</li>"
        return s


def build_nested_list(line_data):
    if not line_data: return ""
    def snap(x): return round(x / 5) * 5
    x_vals = sorted(set(snap(d["x"]) for d in line_data))
    def level(x):
        sx = snap(x)
        for i, xv in enumerate(x_vals):
            if abs(sx - xv) <= 5: return i
        return 0
    root_items = []
    stack = []
    for d in line_data:
        lv  = level(d["x"])
        html_t = strip_bullet_prefix_html(d["html"])
        numbered = d.get("numbered", False)
        item = ListItem(html_t, numbered)
        if lv == 0 or not stack:
            root_items.append(item)
            stack = [(0, item)]
        else:
            while stack and stack[-1][0] >= lv:
                stack.pop()
            if stack:
                stack[-1][1].children.append(item)
            else:
                root_items.append(item)
            stack.append((lv, item))
    if not root_items: return ""
    tag = "ol" if root_items[0].numbered else "ul"
    return f"<{tag}>" + "".join(it.to_html() for it in root_items) + f"</{tag}>"


def is_junk_line(plain, page_h, y):
    if y < page_h * 0.06 or y > page_h * 0.90:
        return True
    stripped = plain.strip().rstrip("\t\r \xa0")
    if stripped.isdigit() and len(stripped) <= 3:
        return True
    return False


# ── Image extraction helper ───────────────────────────────────────

def extract_page_images(doc, page, page_num, pdf_stem):
    """Return list of (y0, html_str) for images on this page."""
    out_dir = IMAGES_DIR / pdf_stem
    out_dir.mkdir(parents=True, exist_ok=True)

    seen = set()
    results = []

    for img_idx, img_info in enumerate(page.get_images(full=True)):
        xref = img_info[0]
        if xref in seen: continue
        seen.add(xref)

        try:
            base = doc.extract_image(xref)
            w, h = base["width"], base["height"]
            if w < MIN_IMG_W or h < MIN_IMG_H:
                continue

            ext      = base["ext"]
            filename = f"p{page_num:03d}_i{img_idx+1:02d}.{ext}"
            abs_path = out_dir / filename
            abs_path.write_bytes(base["image"])

            rel_path = f"images/{pdf_stem}/{filename}"

            # Find image bbox on page to get vertical position
            # Use image list bbox if available
            rects = page.get_image_rects(xref)
            y0 = rects[0].y0 if rects else (page_num * 1000)

            img_html = (
                f'<figure style="text-align:center;margin:16px 0">'
                f'<img src="{rel_path}" alt="Figure page {page_num}" '
                f'style="max-width:100%;height:auto;border-radius:4px;'
                f'box-shadow:0 2px 8px rgba(0,0,0,.1)">'
                f'</figure>'
            )
            results.append((y0, img_html))
        except Exception:
            pass

    return results


# ── Core converter ────────────────────────────────────────────────

def pdf_to_html(pdf_path):
    doc      = fitz.open(str(pdf_path))
    body     = dominant_size(doc)
    pdf_stem = pdf_path.stem

    parts = []

    for page in doc:
        page_num = page.number + 1
        page_h   = page.rect.height
        page_w   = page.rect.width

        # Collect text blocks with their y positions
        text_items = []   # list of (y0, html_str)

        blocks = page.get_text("dict", sort=True)["blocks"]
        for block in blocks:
            if block.get("type") != 0:
                continue

            line_data = []
            for line in block.get("lines", []):
                spans = line.get("spans", [])
                plain = "".join(s["text"] for s in spans).strip()
                if not plain: continue
                x0 = line["bbox"][0]
                y0 = line["bbox"][1]
                if is_junk_line(plain, page_h, y0): continue
                html_t   = spans_to_html(spans)
                max_size = max((s["size"] for s in spans), default=body)
                all_bold = all(
                    bool(s.get("flags", 0) & 16) or "Bold" in s.get("font", "")
                    for s in spans if s["text"].strip()
                )
                line_data.append({
                    "plain": plain, "html": html_t, "size": max_size,
                    "x": x0, "bold": all_bold, "numbered": is_numbered(plain),
                    "y0": y0,
                })

            if not line_data: continue

            block_y0 = block["bbox"][1]
            sec_lines = [d for d in line_data if SECTION_CHAR in d["plain"]]
            line_data  = [d for d in line_data if SECTION_CHAR not in d["plain"]]

            for d in sec_lines:
                heading = d["plain"].replace("v" + SECTION_CHAR, "").replace(SECTION_CHAR, "").strip()
                if heading:
                    display = heading.title() if heading == heading.upper() else heading
                    text_items.append((d["y0"], f'<h2 class="section-head">{html_lib.escape(display)}</h2>'))

            if not line_data: continue

            block_max_size = max(d["size"] for d in line_data)
            first_plain    = line_data[0]["plain"]

            if block_max_size > body * 1.1 and len(line_data) <= 4:
                html_parts = []
                for d in line_data:
                    tag = size_tag(d["size"], body)
                    if d["bold"] and tag == "p": tag = "h4"
                    html_parts.append(f"<{tag}>{d['html']}</{tag}>")
                text_items.append((block_y0, "\n".join(html_parts)))
                continue

            is_list = (
                is_plain_bullet(first_plain) or is_o_bullet(first_plain) or
                is_numbered(first_plain) or
                any(is_plain_bullet(d["plain"]) for d in line_data)
            )
            if is_list:
                html_list = build_nested_list(line_data)
                if html_list:
                    text_items.append((block_y0, html_list))
                continue

            joined = " ".join(d["html"] for d in line_data)
            text_items.append((block_y0, f"<p>{joined}</p>"))

        # Collect images for this page
        img_items = extract_page_images(doc, page, page_num, pdf_stem)

        # Merge text and images by vertical position
        all_items = sorted(text_items + img_items, key=lambda x: x[0])
        for _, html_str in all_items:
            parts.append(html_str)

    doc.close()
    return "\n".join(parts)


# ── JS writer ─────────────────────────────────────────────────────

def escape_js(s):
    return s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")


def main():
    OUTPUT_DIR.mkdir(exist_ok=True)
    IMAGES_DIR.mkdir(exist_ok=True)
    pdfs = sorted(ENGLISH_DIR.glob("*.pdf"))

    if not pdfs:
        print(f"No PDFs found in {ENGLISH_DIR}/")
        return

    print(f"Converting {len(pdfs)} PDFs -> {OUTPUT_FILE}\n")

    lines = [
        "// Auto-generated by convert_pdfs.py (with images) -- do not edit",
        "window.UESCA_CONTENT = {};\n",
    ]

    ok = 0
    for pdf in pdfs:
        key = f"English/{pdf.name}"
        try:
            raw  = pdf_to_html(pdf)
            esc  = escape_js(raw)
            lines.append(
                f"window.UESCA_CONTENT['{key}'] = "
                f"`<div class=\"content-body\">\n{esc}\n</div>`;\n"
            )
            print(f"  OK  {pdf.name}")
            ok += 1
        except Exception as exc:
            print(f"  FAIL  {pdf.name}: {exc}")
            lines.append(
                f"window.UESCA_CONTENT['{key}'] = "
                f"'<p class=\"conv-error\">Conversion failed: {html_lib.escape(pdf.name)}</p>';\n"
            )

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nDone! {ok}/{len(pdfs)} converted -> {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
