#!/usr/bin/env python3
"""
extract_images.py  —  Extract raster images from UESCA PDFs and embed in MD files.

Run:  py extract_images.py
Then: py md_to_js.py   (rebuilds the website bundle with images)
"""

import fitz      # PyMuPDF
import re
from pathlib import Path

ENGLISH_DIR = Path("English")
IMAGES_DIR  = Path("images")   # relative to UESCA/ root (same level as index.html)

# Minimum image dimensions to keep (filters out tiny icons / bullets)
MIN_W, MIN_H = 80, 60


# ── Image extraction ─────────────────────────────────────────────
def extract_images(pdf_path: Path) -> list[dict]:
    """Return list of saved image dicts for one PDF."""
    stem    = pdf_path.stem
    out_dir = IMAGES_DIR / stem
    out_dir.mkdir(parents=True, exist_ok=True)

    doc     = fitz.open(str(pdf_path))
    seen    = set()
    results = []

    for page_num, page in enumerate(doc, start=1):
        for img_idx, img_info in enumerate(page.get_images(full=True), start=1):
            xref = img_info[0]
            if xref in seen:
                continue
            seen.add(xref)

            try:
                base  = doc.extract_image(xref)
                w, h  = base["width"], base["height"]
                if w < MIN_W or h < MIN_H:
                    continue                         # skip tiny decorative images

                ext      = base["ext"]
                filename = f"p{page_num:03d}_i{img_idx:02d}.{ext}"
                abs_path = out_dir / filename
                abs_path.write_bytes(base["image"])

                # relative path from index.html perspective
                rel = f"images/{stem}/{filename}"
                results.append({"page": page_num, "path": rel, "w": w, "h": h})
                print(f"      {filename}  ({w}×{h})")
            except Exception as exc:
                print(f"      xref {xref}: {exc}")

    doc.close()
    return results


# ── Figure caption extraction ─────────────────────────────────────
# Matches  "Figure 7.1 Some description"  or  "Fig. 3 Something"
_FIG_RE = re.compile(
    r'\bFig(?:ure|\.?)\s+([\d]+[.\-][\d]+|[\d]+)\s+([^\n]+)',
    re.IGNORECASE
)

def figure_captions(pdf_path: Path) -> list[dict]:
    """Return list of {page, fig_id, desc} for every figure caption found."""
    doc   = fitz.open(str(pdf_path))
    found = []
    for page_num, page in enumerate(doc, start=1):
        for m in _FIG_RE.finditer(page.get_text()):
            found.append({
                "page":   page_num,
                "fig_id": m.group(1).strip(),
                "desc":   m.group(2).strip()[:80],
            })
    doc.close()
    return found


# ── MD injection ──────────────────────────────────────────────────
def _img_tag(rel_path: str, alt: str) -> str:
    return f"\n![{alt}]({rel_path})\n"


def inject_images(md_path: Path, images: list[dict], captions: list[dict]) -> None:
    """Insert image references into the MD file at figure-reference locations.
    Falls back to appending a Figures gallery if captions cannot be matched."""

    if not md_path.exists() or not images:
        return

    text = md_path.read_text(encoding="utf-8")

    # Build page → images map
    page_imgs: dict[int, list[dict]] = {}
    for img in images:
        page_imgs.setdefault(img["page"], []).append(img)

    # Try to match each caption to an image on the same page
    matched: list[tuple[str, str, str]] = []   # (fig_id, img_path, alt_text)
    used_xrefs = set()
    for cap in sorted(captions, key=lambda c: (c["page"], c["fig_id"])):
        pg_imgs = [i for i in page_imgs.get(cap["page"], [])
                   if i["path"] not in used_xrefs]
        if pg_imgs:
            img = pg_imgs[0]
            used_xrefs.add(img["path"])
            alt = f"Figure {cap['fig_id']} — {cap['desc']}"
            matched.append((cap["fig_id"], img["path"], alt))

    if matched:
        # Insert image after the first line that mentions "Figure X.Y" or "figure X.Y"
        for fig_id, img_path, alt in matched:
            # Already embedded?
            if img_path in text:
                continue
            pattern = re.compile(
                r'(?:Figure|figure|Fig\.?)\s+' + re.escape(fig_id) + r'[^\w]',
            )
            m = pattern.search(text)
            if m:
                # Find end of the line containing this reference
                end_of_line = text.find('\n', m.end())
                if end_of_line == -1:
                    end_of_line = len(text)
                insert = _img_tag(img_path, alt)
                text = text[:end_of_line] + insert + text[end_of_line:]
            # If reference not found in MD text, we'll add to gallery below

    # Remaining unmatched images → append gallery
    gallery_imgs = [img for img in images if img["path"] not in text]
    if gallery_imgs:
        gallery = "\n\n---\n\n## Figures\n\n"
        for img in gallery_imgs:
            gallery += _img_tag(img["path"], f"Page {img['page']} figure")
        text = text.rstrip() + "\n" + gallery

    md_path.write_text(text, encoding="utf-8")


# ── Main ──────────────────────────────────────────────────────────
def main():
    IMAGES_DIR.mkdir(exist_ok=True)

    pdfs = sorted(ENGLISH_DIR.glob("*.pdf"))
    print(f"Found {len(pdfs)} PDFs in {ENGLISH_DIR}/\n")

    total = 0
    for pdf_path in pdfs:
        md_path = pdf_path.with_suffix(".md")
        if not md_path.exists():
            print(f"  SKIP  {pdf_path.name}  (no .md file yet)")
            continue

        print(f"  {pdf_path.name}")
        images   = extract_images(pdf_path)
        captions = figure_captions(pdf_path)
        print(f"    -> {len(images)} images, {len(captions)} figure captions found")

        inject_images(md_path, images, captions)
        total += len(images)

    print(f"\nDone! {total} images extracted.")
    print("Run  py md_to_js.py  to rebuild content/all_md.js with images.")


if __name__ == "__main__":
    main()
