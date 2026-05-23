#!/usr/bin/env python3
"""
generate_quiz.py
Reads all English MD files and extracts quiz questions:
  1. Definition questions   (**Term:** description)
  2. Fact/number questions  (sentences with key figures)
  3. List-choice questions  (bullet sections → pick the correct one)

Outputs: content/quiz_data.js
Run:     py generate_quiz.py
"""

import re, json, random
from pathlib import Path

ENGLISH_DIR = Path("English")
OUTPUT      = Path("content/quiz_data.js")

# ── Module name map (stem → display title) ───────────────────────
MODULE_TITLES = {
    "UESCA-RunATC2-About this certification": "About This Certification",
    "UESCA-Mod1-RunYTC3":  "Module 1: Run Coaching 101",
    "UESCA-Mod2-RunSkele4": "Module 2: Skeletal System",
    "UESCA-Mod3-RunMusc3-WORD UPDATED": "Module 3: Muscular System",
    "UESCA-Mod4-RunEnerg3": "Module 4: Energy Systems",
    "UESCA-Mod5-RunTrain3": "Module 5: Training Principles",
    "UESCA-Mod6-RunAssess3": "Module 6: Athlete Assessment",
    "UESCA-Mod7-RunMech3":  "Module 7: Running Mechanics",
    "UESCA-Mod8-RunInj3":   "Module 8: Illness and Injuries",
    "UESCA-Mod9-RunResist3": "Module 9: Resistance Training",
    "UESCA-Mod10-RunStret3": "Module 10: Stretching & Flexibility",
    "UESCA-Mod11-RunIntake3": "Module 11: Client Intake",
    "UESCA-Mod12-RunGoal3": "Module 12: Goal Setting",
    "UESCA-Mod13-RunPeriod3": "Module 13: Periodization",
    "UESCA-Mod14-RunPgm32": "Module 14: Program Design",
    "UESCA-Mod15-RunMod3":  "Module 15: Modifying Programs",
    "UESCA-Mod16-RunPac3":  "Module 16: Pacing",
    "UESCA-Mod17-RunMent3": "Module 17: Mental Training",
    "UESCA-Mod18-RunNut3":  "Module 18: Sports Nutrition",
    "UESCA-Mod19-RunSaft31": "Module 19: Running Safety",
    "UESCA-Mod20-RunSA3":   "Module 20: Running Shoes & Apparel",
    "UESCA-Mod21-RunRaPrep31": "Module 21: Race Preparation",
    "UESCA-Mod22-RunLI3":   "Module 22: Lifestyle Integration",
    "AppA-RunET":  "Appendix A: Running Lingo & Etiquette",
    "AppB-RunRes": "Appendix B: Online Resources",
    "AppC-RunBAM": "Appendix C: Business & Marketing",
    "UESCA-RunGloss": "Glossary",
    "UESCA-RunBib2":  "Bibliography",
}

# Matches BOTH formats:
#   **Term:** definition     (colon inside bold)
#   **Term**[: —-] definition (separator outside bold)
_BOLD_DEF = re.compile(
    r'\*\*([^*\n]{2,60}?):?\*\*\s*:?[-—]?\s*(.{10,280}?)(?=\n|$)',
    re.MULTILINE
)
_NUMBER_FACT= re.compile(r'(?:approximately|about|roughly|between|up to|over|around)?\s*(\d+(?:[.,]\d+)?(?:\s*(?:percent|%|million|billion|km|miles|minutes?|seconds?|hours?|days?|weeks?|years?|times?|degrees?)))', re.IGNORECASE)
_BULLET     = re.compile(r'^[-*]\s+(.+)$', re.MULTILINE)
_HEADING    = re.compile(r'^#{1,4}\s+(.+)$', re.MULTILINE)


def strip_md(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
    text = re.sub(r'\*(.+?)\*',     r'\1', text)
    text = re.sub(r'`(.+?)`',       r'\1', text)
    return text.strip().rstrip('.')


def truncate(text: str, n=120) -> str:
    text = strip_md(text)
    return text[:n] + '…' if len(text) > n else text


# ── Extractor 1: Definition questions ────────────────────────────
def extract_definition_questions(text: str, all_definitions: list) -> list:
    questions = []
    found = _BOLD_DEF.findall(text)
    for term, definition in found:
        term       = strip_md(term).strip().rstrip(':–—-').strip()
        definition = truncate(definition)
        if len(term) < 2 or len(definition) < 10: continue
        # Skip low-quality entries
        if term.endswith('?') or '\n' in term: continue
        if definition.strip().startswith('http'): continue
        if 'http' in term: continue
        if len(term.split()) > 7: continue   # term too long = sentence, not a term

        other_defs  = [d for t, d in all_definitions if t.lower() != term.lower() and len(d) > 10]
        other_terms = [t for t, d in all_definitions if t.lower() != term.lower() and len(t) > 1]
        if len(other_defs) < 3 or len(other_terms) < 3: continue

        # Q1: term → definition  ("What does X mean?")
        distractors = random.sample(other_defs, 3)
        opts = [definition] + [truncate(d) for d in distractors]
        random.shuffle(opts)
        questions.append({
            "q":       f'What is the correct definition of "{term}"?',
            "options": opts,
            "correct": opts.index(definition),
            "hint":    f'{term}: {definition}'
        })

        # Q2: definition → term  ("Which term is described as: …?")
        wrong_terms = random.sample(other_terms, 3)
        opts2 = [term] + wrong_terms
        random.shuffle(opts2)
        questions.append({
            "q":       f'Which term is described as: "{definition}"?',
            "options": opts2,
            "correct": opts2.index(term),
            "hint":    f'{term}: {definition}'
        })
    return questions


# ── Extractor 2: True/False fact questions ────────────────────────
_FACT_SENT = re.compile(
    r'(?<!\w)([A-Z][^.!?\n]{30,180}(?:\d+%|\d+\s*percent|\d+\s*miles|\d+\s*minutes?|\d+\s*hours?|\d+\s*days?)[^.!?\n]{0,60})[.!]',
)

def extract_fact_questions(text: str) -> list:
    questions = []
    for m in _FACT_SENT.finditer(text):
        sentence = strip_md(m.group(1)).strip()
        if len(sentence) < 20 or len(sentence) > 200: continue
        # Find the number in the sentence
        num_match = re.search(r'(\d+(?:[.,]\d+)?(?:\s*(?:percent|%|miles|minutes?|hours?|days?|km))?)', sentence, re.I)
        if not num_match: continue
        num_str  = num_match.group(1)
        num_val  = float(re.sub(r'[^\d.]', '', num_str) or '0')
        if num_val == 0: continue

        # Generate 3 wrong numbers
        def wrong_num(v):
            factor = random.choice([0.5, 0.6, 0.75, 1.25, 1.5, 2.0])
            candidate = round(v * factor)
            # Keep same suffix
            suffix_m = re.search(r'[^\d.,]+$', num_str)
            suffix   = suffix_m.group(0) if suffix_m else ''
            return str(candidate) + suffix

        wrong_nums = list({wrong_num(num_val) for _ in range(6)})[:3]
        if len(wrong_nums) < 3: continue

        correct_opt = sentence
        wrong_opts  = [sentence.replace(num_str, w, 1) for w in wrong_nums]
        options = [correct_opt] + wrong_opts
        random.shuffle(options)
        correct = options.index(correct_opt)
        questions.append({
            "q":       "Which of the following statements is CORRECT?",
            "options": [truncate(o, 140) for o in options],
            "correct": correct,
            "hint":    truncate(sentence, 140)
        })
    return questions


# ── Extractor 3: List-choice questions ───────────────────────────
def extract_list_questions(text: str) -> list:
    """Find sections with ≥4 bullet items and make pick-the-correct/incorrect Qs."""
    questions = []
    # Split into sections by headings
    sections = re.split(r'\n#{1,4} ', '\n' + text)
    for section in sections:
        lines   = section.strip().splitlines()
        if not lines: continue
        heading = strip_md(lines[0])
        bullets = []
        for line in lines[1:]:
            m = re.match(r'^\s*[-*]\s+(.+)', line)
            if m:
                b = strip_md(m.group(1))
                if 5 < len(b) < 120:
                    bullets.append(b)

        if len(bullets) < 4: continue

        # Q type A: "Which is a [heading]?" — pick one correct from 4
        sample = random.sample(bullets, min(4, len(bullets)))
        correct_item = sample[0]
        # Get distractors from OTHER sections
        # (we'll collect them globally; for now use the sample itself and shuffle)
        options = sample[:]
        random.shuffle(options)
        correct = options.index(correct_item)
        questions.append({
            "q":       f'Which of the following is related to "{truncate(heading, 60)}"?',
            "options": [truncate(o) for o in options],
            "correct": correct,
            "hint":    f'All items in this list are related to {heading}'
        })

        # Q type B: "Which is NOT in the list of [heading]?" — one fake item
        if len(bullets) >= 4:
            real_items  = random.sample(bullets, 3)
            # Fake item: grab a bullet from a random OTHER section
            # We'll mark it with a sentinel and replace later
            fake_item   = "__FAKE__"
            options2    = real_items + [fake_item]
            random.shuffle(options2)
            correct2    = options2.index(fake_item)
            questions.append({
                "q":         f'Which of the following is NOT part of "{truncate(heading, 60)}"?',
                "options":   [truncate(o) for o in options2],
                "correct":   correct2,
                "hint":      f'The other three ARE related to {heading}',
                "_real":     real_items,
                "_heading":  heading,
            })
    return questions


def resolve_fakes(all_questions_by_module: dict):
    """Replace __FAKE__ placeholders with real items from OTHER modules."""
    # Collect all real bullet items across all modules
    all_bullets = []
    for qs in all_questions_by_module.values():
        for q in qs:
            if "_real" in q:
                all_bullets.extend(q["_real"])

    for qs in all_questions_by_module.values():
        for q in qs:
            if "__FAKE__" in q["options"]:
                # Pick a random item that isn't in real
                real_set = set(q.get("_real", []))
                candidates = [b for b in all_bullets if b not in real_set and len(b) > 5]
                fake = random.choice(candidates) if candidates else "None of the above"
                idx = q["options"].index("__FAKE__")
                q["options"][idx] = truncate(fake)
                # Clean up internal keys
                q.pop("_real", None)
                q.pop("_heading", None)


# ── Main ──────────────────────────────────────────────────────────
def main():
    all_definitions = []  # global pool for distractors

    # First pass: collect all definitions
    for md in sorted(ENGLISH_DIR.glob("*.md")):
        text = md.read_text(encoding="utf-8")
        for term, defn in _BOLD_DEF.findall(text):
            term = strip_md(term).strip().rstrip(':–—-').strip()
            defn = truncate(defn)
            if (len(term) >= 2 and len(defn) >= 10
                and not term.endswith('?')
                and not defn.strip().startswith('http')
                and 'http' not in term
                and len(term.split()) <= 7):     # skip sentence-length "terms"
                all_definitions.append((term, defn))

    print(f"Collected {len(all_definitions)} definitions from all modules\n")

    questions_by_module = {}

    for md in sorted(ENGLISH_DIR.glob("*.md")):
        stem  = md.stem
        title = MODULE_TITLES.get(stem, stem)
        text  = md.read_text(encoding="utf-8")

        qs = []
        qs += extract_definition_questions(text, all_definitions)
        qs += extract_fact_questions(text)
        # List/NOT questions removed — too ambiguous

        # Deduplicate by question text
        seen  = set()
        dedup = []
        for q in qs:
            key = q["q"][:60]
            if key not in seen:
                seen.add(key)
                dedup.append(q)

        if dedup:
            questions_by_module[title] = dedup
            print(f"  {title}: {len(dedup)} questions")

    # Write quiz_data.js
    Path("content").mkdir(exist_ok=True)
    js = "// Auto-generated by generate_quiz.py — do not edit\n"
    js += "window.QUIZ_DATA = " + json.dumps(questions_by_module, ensure_ascii=False, indent=2) + ";\n"
    OUTPUT.write_text(js, encoding="utf-8")
    total = sum(len(v) for v in questions_by_module.values())
    print(f"\nTotal: {total} questions across {len(questions_by_module)} modules -> {OUTPUT}")


if __name__ == "__main__":
    random.seed(42)
    main()
