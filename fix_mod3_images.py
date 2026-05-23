#!/usr/bin/env python3
"""
fix_mod3_images.py
Precisely maps every Figure 3.X to the correct extracted image file,
strips old auto-generated image tags from the Mod3 MD, then re-inserts
all 46 figures at the correct locations.
Run: py fix_mod3_images.py
"""

import re
from pathlib import Path

IMG_BASE = "images/UESCA-Mod3-RunMusc3-WORD UPDATED"
MD_PATH  = Path("English/UESCA-Mod3-RunMusc3-WORD UPDATED.md")

# ── Complete figure → image mapping ──────────────────────────────
# Based on page-by-page analysis of the PDF.
# 3.7 and 3.8 already use custom user-supplied images.
FIGURE_MAP = {
    "3.1":  ("p004_i01.jpeg", "Skeletal Muscle Structure"),
    "3.2":  ("p007_i01.jpeg", "Skeletal Muscle Origin/Insertion"),
    # 3.3 is a table rendered as text — skip image
    "3.4":  ("p013_i01.jpeg", "Nerve Innervation of Muscle Fiber"),
    "3.5":  ("p018_i01.jpeg", "Skeletal Muscles – Anterior"),
    "3.6":  ("p019_i01.jpeg", "Skeletal Muscles – Posterior"),
    # 3.7 and 3.8 already placed with user images — don't override
    "3.9":  ("p023_i02.png",  "Internal Oblique"),
    "3.10": ("p024_i02.png",  "Transverse Abdominis"),
    "3.11": ("p024_i04.png",  "Diaphragm"),
    "3.12": ("p025_i02.png",  "Pelvic Floor Muscles"),
    "3.13": ("p026_i01.png",  "Multifidus"),
    "3.14": ("p027_i02.png",  "Rectus Abdominis"),
    "3.15": ("p027_i04.png",  "External Oblique"),
    "3.16": ("p028_i03.png",  "Erector Spinae"),
    "3.17": ("p028_i04.png",  "Quadratus Lumborum"),
    "3.18": ("p029_i04.png",  "Hip Flexors"),
    "3.19": ("p029_i05.png",  "Hip Adductors"),
    "3.20": ("p030_i02.png",  "Hamstrings"),
    "3.21": ("p030_i04.png",  "Rectus Femoris"),
    "3.22": ("p031_i02.png",  "Gluteus Maximus"),
    "3.23": ("p032_i02.png",  "Quadriceps"),
    "3.24": ("p033_i03.png",  "Tibialis Anterior/Posterior"),
    "3.25": ("p033_i05.png",  "Soleus"),
    "3.26": ("p034_i02.png",  "Gastrocnemius"),
    "3.27": ("p034_i05.png",  "Peroneals"),
    "3.28": ("p035_i05.png",  "Gluteals"),
    "3.29": ("p035_i06.png",  "Tensor Fasciae Latae"),
    "3.30": ("p036_i03.png",  "Piriformis"),
    "3.31": ("p036_i04.png",  "Popliteus"),
    "3.32": ("p037_i02.png",  "Sartorius"),
    "3.33": ("p038_i02.png",  "Pectoralis Major"),
    "3.34": ("p038_i04.png",  "Pectoralis Minor"),
    "3.35": ("p039_i02.png",  "Latissimus Dorsi"),
    "3.36": ("p039_i04.png",  "Trapezius"),
    "3.37": ("p040_i02.png",  "Serratus Anterior"),
    "3.38": ("p040_i05.png",  "Rhomboids"),
    "3.39": ("p041_i02.png",  "Levator Scapulae"),
    "3.40": ("p041_i04.png",  "Deltoids"),
    "3.41": ("p042_i05.png",  "Rotator Cuff Muscles"),
    "3.42": ("p043_i04.png",  "Primary Arm Muscles"),
    "3.43": ("p057_i02.png",  "Correct versus Compensated Posture"),
    "3.44": ("p056_i01.jpeg", "Muscle Synergy (Tug-of-War)"),
    "3.45": ("p045_i01.png",  "Muscle Length/Tension Relationship"),
    "3.46": ("p059_i01.jpeg", "Correct Ergonomics"),
}


def img_tag(fig_num, filename, desc):
    path = f"{IMG_BASE}/{filename}"
    return f"\n![Figure {fig_num} — {desc}]({path})\n"


def main():
    text = MD_PATH.read_text(encoding="utf-8")

    # ── 1. Strip ALL existing auto-injected image lines ──────────
    # Remove lines that reference images/UESCA-Mod3 (except user images 3.7/3.8)
    cleaned = []
    skip_gallery = False
    for line in text.splitlines():
        # Remove auto Figures gallery block
        if line.strip() == "## Figures" or skip_gallery:
            skip_gallery = True
            # Keep content after the gallery section only if it's not part of it
            if skip_gallery and line.strip().startswith("![") and IMG_BASE in line:
                continue  # skip gallery image lines
            elif skip_gallery and line.strip() == "---" and not cleaned:
                continue
        # Remove any previously injected img lines (except 3.7 and 3.8 user images)
        if line.strip().startswith("![") and IMG_BASE in line:
            # Keep user-supplied fig_3_7 and fig_3_8
            if "fig_3_7" in line or "fig_3_8" in line:
                cleaned.append(line)
            # keep these
            continue
        cleaned.append(line)

    text = "\n".join(cleaned)

    # ── 2. Remove trailing gallery section ───────────────────────
    # Strip everything from "---\n\n## Figures" onwards if present
    gallery_marker = "\n\n---\n\n## Figures\n"
    if gallery_marker in text:
        text = text[:text.index(gallery_marker)]

    # ── 3. Insert each figure image at the right location ────────
    inserted = 0
    for fig_num, (filename, desc) in FIGURE_MAP.items():
        # Check image file exists
        img_path = Path(IMG_BASE) / filename
        if not img_path.exists():
            print(f"  SKIP Figure {fig_num}: {filename} not found")
            continue

        # Already has an image for this figure?
        tag = f"![Figure {fig_num}"
        if tag in text:
            print(f"  SKIP Figure {fig_num}: already has image tag")
            continue

        # Find "Figure 3.X" or "figure 3.X" reference in the text
        pattern = re.compile(
            r'(?:Figure|figure)\s+' + re.escape(fig_num) + r'[^\w.]',
        )
        match = pattern.search(text)
        if not match:
            # Try without trailing boundary (for end-of-line cases)
            pattern2 = re.compile(r'(?:Figure|figure)\s+' + re.escape(fig_num) + r'\b')
            match = pattern2.search(text)

        if match:
            # Insert image after the end of the line containing the match
            eol = text.find('\n', match.end())
            if eol == -1:
                eol = len(text)
            insert = img_tag(fig_num, filename, desc)
            text = text[:eol] + insert + text[eol:]
            print(f"  OK  Figure {fig_num} -> {filename}")
            inserted += 1
        else:
            print(f"  WARN Figure {fig_num}: reference not found in MD text")

    MD_PATH.write_text(text, encoding="utf-8")
    print(f"\nInserted {inserted} figure images into {MD_PATH.name}")
    print("Run  py md_to_js.py  to rebuild the website bundle.")


if __name__ == "__main__":
    main()
