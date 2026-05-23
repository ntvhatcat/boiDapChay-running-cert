#!/usr/bin/env python3
"""
Translate UESCA course content: English -> Vietnamese
Reads  : content/all.js
Outputs: content/all_vi.js

Progress is saved to content/translate_progress.json after every file
so you can safely Ctrl+C and resume later.

Usage:
    py translate.py
"""

# ── SSL bypass (must be before any network import) ───────────────
import ssl, warnings, os
warnings.filterwarnings("ignore")
ssl._create_default_https_context = ssl._create_unverified_context
os.environ.setdefault("PYTHONHTTPSVERIFY", "0")

import urllib3
urllib3.disable_warnings()

import requests
_orig_send = requests.Session.send
def _send_no_verify(self, req, **kw):
    kw["verify"] = False
    return _orig_send(self, req, **kw)
requests.Session.send = _send_no_verify
# ────────────────────────────────────────────────────────────────

import re
import json
import time
import sys
from pathlib import Path
from bs4 import BeautifulSoup, NavigableString

try:
    from deep_translator import GoogleTranslator
except ImportError:
    print("Run: pip install deep-translator beautifulsoup4")
    sys.exit(1)

INPUT    = Path("content/all.js")
OUTPUT   = Path("content/all_vi.js")
PROGRESS = Path("content/translate_progress.json")

# ── Config ───────────────────────────────────────────────────────
MAX_CHARS  = 4500   # Google Translate hard limit
BATCH_SEP  = " [|||] "   # separator between batched texts
DELAY      = 0.4    # seconds between API calls
FILE_DELAY = 1.5    # seconds between files
MAX_RETRY  = 4

translator = GoogleTranslator(source="en", target="vi")

# ── Translation helpers ───────────────────────────────────────────

def _call(text):
    """Single Google Translate call with retry."""
    text = text.strip()
    if not text or len(text) < 2:
        return text
    for attempt in range(MAX_RETRY):
        try:
            result = translator.translate(text)
            time.sleep(DELAY)
            return result if result else text
        except Exception as exc:
            wait = 2 ** attempt
            print(f"\n    [retry {attempt+1}] {exc} — waiting {wait}s", end="")
            time.sleep(wait)
    return text  # give up: keep original


def translate_texts(texts):
    """
    Translate a list of strings.
    Tries to batch into one request; falls back to individual calls.
    """
    if not texts:
        return []

    # Single item — direct call
    if len(texts) == 1:
        return [_call(texts[0])]

    combined = BATCH_SEP.join(texts)

    if len(combined) <= MAX_CHARS:
        result = _call(combined)
        # Split back by separator (Google may add/remove spaces around it)
        parts = re.split(r'\s*\[\|\|\|\]\s*', result)
        if len(parts) == len(texts):
            return [p.strip() for p in parts]
        # Separator mangled — fall back to individual
        print(f"\n    [batch split failed, going individual for {len(texts)} items]", end="")

    # Fallback: individual
    results = []
    for t in texts:
        results.append(_call(t))
    return results


# ── HTML translator ───────────────────────────────────────────────

BLOCK_TAGS = {"h1", "h2", "h3", "h4", "p", "li"}


def translate_html(html_str):
    """Translate all text content inside block elements, preserving HTML tags."""
    soup = BeautifulSoup(html_str, "html.parser")
    elements = [el for el in soup.find_all(BLOCK_TAGS)]

    # Collect (element, plain_text) pairs
    pairs = []
    for el in elements:
        text = el.get_text(" ", strip=True)
        if text and len(text) > 1:
            pairs.append((el, text))

    if not pairs:
        return str(soup)

    # Split into batches respecting MAX_CHARS
    batches = []
    cur_batch, cur_len = [], 0
    for el, text in pairs:
        cost = len(text) + len(BATCH_SEP)
        if cur_len + cost > MAX_CHARS and cur_batch:
            batches.append(cur_batch)
            cur_batch, cur_len = [], 0
        cur_batch.append((el, text))
        cur_len += cost
    if cur_batch:
        batches.append(cur_batch)

    # Translate each batch
    for batch in batches:
        translated_list = translate_texts([t for _, t in batch])
        for (el, _), vi_text in zip(batch, translated_list):
            # Replace element's text content while keeping tag
            el.clear()
            el.string = vi_text

    return str(soup)


# ── JS file parser ────────────────────────────────────────────────

ENTRY_RE = re.compile(
    r"window\.UESCA_CONTENT\['([^']+)'\]\s*=\s*`([\s\S]*?)`\s*;",
    re.MULTILINE,
)


def escape_js(s):
    s = s.replace("\\", "\\\\")
    s = s.replace("`",  "\\`")
    s = s.replace("${", "\\${")
    return s


# ── Main ─────────────────────────────────────────────────────────

def main():
    if not INPUT.exists():
        print(f"ERROR: {INPUT} not found. Run convert_pdfs.py first.")
        sys.exit(1)

    # Load existing progress
    cache = {}
    if PROGRESS.exists():
        cache = json.loads(PROGRESS.read_text(encoding="utf-8"))
        print(f"Resuming — {len(cache)} file(s) already done.\n")

    raw = INPUT.read_text(encoding="utf-8")
    matches = list(ENTRY_RE.finditer(raw))

    if not matches:
        print("No UESCA_CONTENT entries found in content/all.js")
        sys.exit(1)

    total = len(matches)
    print(f"Translating {total} files  EN -> VI")
    print("(Progress saved after each file — safe to Ctrl+C and resume)\n")

    results = dict(cache)

    for i, m in enumerate(matches, 1):
        key  = m.group(1)
        html = m.group(2)
        name = key.split("/")[-1]

        if key in results:
            print(f"  [SKIP {i:>2}/{total}] {name}")
            continue

        print(f"  [{i:>2}/{total}] {name} ...", end="", flush=True)
        try:
            vi_html = translate_html(html)
            results[key] = vi_html
            PROGRESS.write_text(
                json.dumps(results, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(" done")
        except KeyboardInterrupt:
            print("\n\nInterrupted — progress saved. Run again to resume.")
            sys.exit(0)
        except Exception as exc:
            print(f" ERROR ({exc}) — keeping original")
            results[key] = html

        time.sleep(FILE_DELAY)

    # Write output
    lines = [
        "// Auto-generated by translate.py — do not edit by hand",
        "window.UESCA_CONTENT_VI = {};\n",
    ]
    for key, html in results.items():
        lines.append(
            f"window.UESCA_CONTENT_VI['{key}'] = `{escape_js(html)}`;\n"
        )

    OUTPUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nDone!  Saved -> {OUTPUT}")

    # Clean up progress file
    if PROGRESS.exists():
        PROGRESS.unlink()


if __name__ == "__main__":
    main()
