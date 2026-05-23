#!/usr/bin/env python3
"""Re-translate the 3 appendix files that were cached in English."""
import ssl, warnings, os, urllib3, requests
warnings.filterwarnings("ignore")
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["PYTHONHTTPSVERIFY"] = "0"
urllib3.disable_warnings()
_orig = requests.Session.send
def _no_ssl(self, req, **kw):
    kw["verify"] = False
    return _orig(self, req, **kw)
requests.Session.send = _no_ssl

import re, time
from pathlib import Path
from bs4 import BeautifulSoup
from deep_translator import GoogleTranslator

translator = GoogleTranslator(source="en", target="vi")
TARGETS = ["AppA-RunET.pdf", "AppB-RunRes.pdf", "AppC-RunBAM.pdf"]

def translate_html(html_str):
    soup = BeautifulSoup(html_str, "html.parser")
    for el in soup.find_all(["h1","h2","h3","h4","p","li"]):
        text = el.get_text(" ", strip=True)
        if text and len(text) > 2:
            try:
                vi = translator.translate(text)
                el.string = vi if vi else text
                time.sleep(0.35)
            except Exception:
                pass
    return str(soup)

def escape_js(s):
    s = s.replace("\\", "\\\\").replace("`", "\\`").replace("${", "\\${")
    return s

en_js = Path("content/all.js").read_text(encoding="utf-8")
vi_js = Path("content/all_vi.js").read_text(encoding="utf-8")

for fname in TARGETS:
    key = f"English/{fname}"
    m = re.search(
        r"window\.UESCA_CONTENT\['" + re.escape(key) + r"'\] = `([\s\S]*?)`\s*;",
        en_js
    )
    if not m:
        print(f"SKIP {fname} - not found")
        continue
    print(f"Translating {fname} ...", end="", flush=True)
    vi_html = translate_html(m.group(1))
    escaped = escape_js(vi_html)
    vi_js = re.sub(
        r"window\.UESCA_CONTENT_VI\['" + re.escape(key) + r"'\] = `[\s\S]*?`\s*;",
        f"window.UESCA_CONTENT_VI['{key}'] = `{escaped}`;",
        vi_js,
        flags=re.MULTILINE
    )
    print(" done")

Path("content/all_vi.js").write_text(vi_js, encoding="utf-8")
print("Saved content/all_vi.js")
