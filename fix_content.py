#!/usr/bin/env python3
"""
Fix UESCA section markers in content/all.js and content/all_vi.js.

The UESCA PDFs use the Wingdings character U+F076 as a section-header marker,
extracted as 'v <strong>HEADING TEXT</strong>'.

This script converts every occurrence into a proper
  <h2 class="section-head">Heading Text</h2>
element, splitting the surrounding paragraph if the marker appears mid-text.
"""

import re
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

MARKER = ''          # the Wingdings bullet extracted by PyMuPDF
MARKER_PAT = re.compile(r'v')

# ── helpers ──────────────────────────────────────────────────────

def to_title(text):
    """ALL CAPS → Title Case; leave mixed-case text untouched."""
    t = text.strip()
    if t == t.upper() and len(t) > 2:
        return t.title()
    return t


def fix_html(html_str):
    """
    Parse the HTML, find every 'v' text node, and convert the
    surrounding block element into a <h2 class="section-head">.
    Returns the fixed HTML string.
    """
    soup = BeautifulSoup(html_str, 'html.parser')

    # Keep looping until no more markers are found
    while True:
        marker_node = None
        for node in soup.find_all(string=MARKER_PAT):
            marker_node = node
            break                  # process one at a time (DOM changes each pass)
        if marker_node is None:
            break

        raw        = str(marker_node)
        m_pos      = raw.find('v' + MARKER)
        before_raw = raw[:m_pos].strip()
        after_raw  = raw[m_pos + 2:].strip()  # skip 'v' + MARKER char

        parent = marker_node.parent            # direct parent tag

        # ── Collect heading text ──
        # It may already be in `after_raw`, or it may live in a following <strong>
        heading_text = after_raw
        strong_to_remove = None

        sib = marker_node.next_sibling
        while sib is not None:
            if isinstance(sib, NavigableString):
                t = str(sib).strip()
                if t:
                    heading_text = (heading_text + ' ' + t).strip()
                    # we'll erase this sibling below
                    break
            elif hasattr(sib, 'name'):
                heading_text = (heading_text + ' ' + sib.get_text()).strip()
                strong_to_remove = sib
                break
            sib = sib.next_sibling

        # ── Build the new <h2> ──
        h2 = soup.new_tag('h2', **{'class': 'section-head'})
        h2.string = to_title(heading_text)

        # ── Find the nearest block-level ancestor ──
        BLOCK = {'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'li'}
        block_el = parent
        while block_el and block_el.name not in BLOCK:
            block_el = block_el.parent
        if block_el is None:
            block_el = parent

        # ── Clean up the original element ──
        if strong_to_remove:
            strong_to_remove.decompose()
        # Also remove any plain-text sibling that held the heading text
        if sib and not strong_to_remove and isinstance(sib, NavigableString):
            sib.replace_with('')
        marker_node.replace_with(before_raw)

        # Check what's left in block_el after the cleanup
        remaining = block_el.get_text().strip()

        if remaining and len(remaining) > 2:
            # There's real content before the marker → keep block_el, add h2 after
            block_el.insert_after(h2)
        else:
            # Block element is now empty (or just whitespace) → replace it with h2
            block_el.replace_with(h2)

    return str(soup)


# ── JS-file processing ───────────────────────────────────────────

ENTRY_RE = re.compile(
    r"(window\.UESCA_CONTENT(?:_VI)?\['[^']+'\]\s*=\s*)`([\s\S]*?)`(\s*;)",
    re.MULTILINE,
)

def escape_js(s):
    return s.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')


def process_file(path: Path) -> int:
    content = path.read_text(encoding='utf-8')
    fixed_count = 0

    def replacer(m):
        nonlocal fixed_count
        html   = m.group(2)
        fixed  = fix_html(html)
        if fixed != html:
            fixed_count += 1
        return m.group(1) + '`' + escape_js(fixed) + '`' + m.group(3)

    new_content = ENTRY_RE.sub(replacer, content)
    path.write_text(new_content, encoding='utf-8')
    return fixed_count


# ── main ─────────────────────────────────────────────────────────

def main():
    targets = [
        Path('content/all.js'),
        Path('content/all_vi.js'),
    ]
    for f in targets:
        if not f.exists():
            print(f'  SKIP  {f.name}  (not found)')
            continue
        n = process_file(f)
        print(f'  OK    {f.name}  — {n} blocks updated')

    # Cleanup temp files
    for tmp in [Path('content/debug.txt'), Path('content/chars.txt')]:
        if tmp.exists():
            tmp.unlink()

if __name__ == '__main__':
    print('Fixing section headers...')
    main()
    print('Done.')
