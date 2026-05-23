#!/usr/bin/env python3
"""
MD → content/all_md.js  (UESCA website)
Reads every .md file in English/ that has a matching .pdf, converts to HTML,
and writes content/all_md.js.  Load all_md.js AFTER all.js so it overrides
the Python-extracted content with the cleaner MD-derived version.

Run:  python md_to_js.py
"""

import re
from pathlib import Path

ENGLISH_DIR = Path("English")
OUTPUT_DIR  = Path("content")
OUTPUT_FILE = OUTPUT_DIR / "all_md.js"


# ── Inline markdown → HTML ────────────────────────────────────────
def inline(text):
    # Bold-italic must come first
    text = re.sub(r'\*\*\*(.*?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.*?)\*\*',     r'<strong>\1</strong>',           text)
    text = re.sub(r'\*(.*?)\*',         r'<em>\1</em>',                   text)
    text = re.sub(r'`([^`]+)`',         r'<code>\1</code>',               text)
    # Convert bare URLs (not already in HTML)
    text = re.sub(r'(?<!["\'])https?://\S+', lambda m: f'<a href="{m.group()}">{m.group()}</a>', text)
    return text


# ── Block markdown → HTML ─────────────────────────────────────────
def md_to_html(md_text):
    lines      = md_text.split('\n')
    out        = []
    buf        = []        # accumulate paragraph lines
    list_stack = []        # [(indent, tag), ...]
    in_table   = False
    table_buf  = []

    def flush_buf():
        if buf:
            text = ' '.join(l.strip() for l in buf if l.strip())
            if text:
                out.append(f'<p>{inline(text)}</p>')
            buf.clear()

    def close_all_lists():
        while list_stack:
            _, tag = list_stack.pop()
            out.append(f'</{tag}>')

    def ensure_list(indent, tag):
        # If current top is same level & tag, do nothing.
        # If deeper → open new nested list.
        # If shallower → close until we match.
        if not list_stack:
            out.append(f'<{tag}>')
            list_stack.append((indent, tag))
        elif indent > list_stack[-1][0]:
            out.append(f'<{tag}>')
            list_stack.append((indent, tag))
        elif indent < list_stack[-1][0]:
            while list_stack and list_stack[-1][0] > indent:
                _, t = list_stack.pop()
                out.append(f'</{t}>')
            if not list_stack or list_stack[-1][0] != indent:
                out.append(f'<{tag}>')
                list_stack.append((indent, tag))

    def flush_table():
        nonlocal table_buf
        if not table_buf:
            return
        out.append('<table style="border-collapse:collapse;width:100%;margin:16px 0">')
        header_written = False
        for tl in table_buf:
            stripped = tl.strip()
            if re.match(r'^\|[-:| ]+\|$', stripped):
                continue  # separator row
            cells = [c.strip() for c in stripped.strip('|').split('|')]
            if not header_written:
                row = ''.join(
                    f'<th style="border:1px solid #e2e8f0;padding:8px 12px;background:#f1f5f9;text-align:left">{inline(c)}</th>'
                    for c in cells
                )
                out.append(f'<thead><tr>{row}</tr></thead><tbody>')
                header_written = True
            else:
                row = ''.join(
                    f'<td style="border:1px solid #e2e8f0;padding:8px 12px">{inline(c)}</td>'
                    for c in cells
                )
                out.append(f'<tr>{row}</tr>')
        if header_written:
            out.append('</tbody>')
        out.append('</table>')
        table_buf = []

    i = 0
    while i < len(lines):
        line = lines[i]

        # ── Image ────────────────────────────────────────────────────
        m = re.match(r'!\[([^\]]*)\]\(([^)]+)\)', line.strip())
        if m:
            flush_buf()
            close_all_lists()
            alt = m.group(1)
            src = m.group(2)
            out.append(
                f'<figure style="text-align:center;margin:24px 0">'
                f'<img src="{src}" alt="{alt}" '
                f'style="max-width:100%;height:auto;border-radius:6px;'
                f'box-shadow:0 2px 8px rgba(0,0,0,.12)">'
                f'<figcaption style="font-size:13px;color:#64748b;margin-top:8px">'
                f'<em>{alt}</em></figcaption></figure>'
            )
            i += 1
            continue

        # ── Table detection ─────────────────────────────────────────
        if line.strip().startswith('|'):
            flush_buf()
            close_all_lists()
            table_buf.append(line)
            i += 1
            continue
        elif table_buf:
            flush_table()

        # ── Blank line ──────────────────────────────────────────────
        if not line.strip():
            flush_buf()
            close_all_lists()
            i += 1
            continue

        # ── Horizontal rule ──────────────────────────────────────────
        if re.match(r'^\s*---+\s*$', line):
            flush_buf()
            close_all_lists()
            out.append('<hr style="border:none;border-top:1px solid #e2e8f0;margin:28px 0">')
            i += 1
            continue

        # ── Heading ──────────────────────────────────────────────────
        m = re.match(r'^(#{1,6})\s+(.*)', line)
        if m:
            flush_buf()
            close_all_lists()
            level   = len(m.group(1))
            content = inline(m.group(2).strip())
            if level == 1:
                out.append(f'<h1>{content}</h1>')
            elif level == 2:
                out.append(f'<h2 class="section-head">{content}</h2>')
            elif level == 3:
                out.append(f'<h3>{content}</h3>')
            elif level == 4:
                out.append(f'<h4>{content}</h4>')
            else:
                out.append(f'<h{level}>{content}</h{level}>')
            i += 1
            continue

        # ── Blockquote ───────────────────────────────────────────────
        if line.strip().startswith('>'):
            flush_buf()
            close_all_lists()
            content = inline(re.sub(r'^>\s*', '', line.strip()))
            out.append(
                f'<blockquote style="border-left:4px solid #00a86b;padding:12px 16px;'
                f'margin:16px 0;background:#f0faf5;border-radius:0 8px 8px 0">'
                f'<em>{content}</em></blockquote>'
            )
            i += 1
            continue

        # ── Unordered list ───────────────────────────────────────────
        m = re.match(r'^(\s*)[-*]\s+(.*)', line)
        if m:
            flush_buf()
            indent  = len(m.group(1))
            content = inline(m.group(2))
            ensure_list(indent, 'ul')
            out.append(f'<li>{content}</li>')
            i += 1
            continue

        # ── Ordered list ─────────────────────────────────────────────
        m = re.match(r'^(\s*)\d+\.\s+(.*)', line)
        if m:
            flush_buf()
            indent  = len(m.group(1))
            content = inline(m.group(2))
            ensure_list(indent, 'ol')
            out.append(f'<li>{content}</li>')
            i += 1
            continue

        # ── Regular line → paragraph buffer ─────────────────────────
        close_all_lists()
        buf.append(line)
        i += 1

    # Flush remaining
    if table_buf:
        flush_table()
    flush_buf()
    close_all_lists()

    return '\n'.join(out)


# ── JS escaping ───────────────────────────────────────────────────
def escape_js(s):
    return s.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')


# ── Main ──────────────────────────────────────────────────────────
def main():
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Collect pairs: (md_path, js_key)
    pairs = []
    for md_path in sorted(ENGLISH_DIR.glob('*.md')):
        pdf_path = md_path.with_suffix('.pdf')
        if not pdf_path.exists():
            # Try case-insensitive match
            matches = [p for p in ENGLISH_DIR.glob('*.pdf')
                       if p.stem.lower() == md_path.stem.lower()]
            if matches:
                pdf_path = matches[0]
            else:
                print(f'  SKIP  {md_path.name} — no matching PDF')
                continue
        key = f'English/{pdf_path.name}'
        pairs.append((md_path, key))

    if not pairs:
        print(f'No .md files with matching .pdfs found in {ENGLISH_DIR}/')
        return

    print(f'Converting {len(pairs)} MD files -> {OUTPUT_FILE}\n')

    lines = [
        '// Auto-generated by md_to_js.py — do not edit',
        '// Overrides all.js entries for files that have been converted to MD.',
        'window.UESCA_CONTENT = window.UESCA_CONTENT || {};\n',
    ]

    ok = 0
    for md_path, key in pairs:
        try:
            md_text = md_path.read_text(encoding='utf-8')
            body    = md_to_html(md_text)
            esc     = escape_js(body)
            lines.append(
                f"window.UESCA_CONTENT['{key}'] = "
                f'`<div class="content-body">\n{esc}\n</div>`;\n'
            )
            print(f'  OK  {md_path.name}')
            ok += 1
        except Exception as exc:
            print(f'  FAIL  {md_path.name}: {exc}')

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))

    print(f'\nDone! {ok}/{len(pairs)} converted -> {OUTPUT_FILE}')
    print('Reload index.html in your browser to see the updated content.')


if __name__ == '__main__':
    main()
