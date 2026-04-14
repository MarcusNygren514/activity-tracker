"""
Layout-validering för web_app.py.
Körs automatiskt som pre-commit hook.
Kontrollerar strukturella invarianter i den inbäddade HTML:en.
"""

import re
import sys
from bs4 import BeautifulSoup

# Windows-terminaler hanterar inte alltid UTF-8
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Extrahera HTML-strängen ur web_app.py ─────────────────────
with open("web_app.py", encoding="utf-8") as f:
    source = f.read()

# HTML:en är definierad som HTML = r"""..."""
match = re.search(r'HTML\s*=\s*r"""(.*?)"""', source, re.DOTALL)
if not match:
    print("check_layout: kunde inte hitta HTML-strängen i web_app.py")
    sys.exit(1)

html = match.group(1)
soup = BeautifulSoup(html, "html.parser")

errors = []

# ── Regler ────────────────────────────────────────────────────

# proj-summary ska INTE ligga inuti .filters
for summary in soup.select(".proj-summary"):
    sid = summary.get("id", "?")
    if summary.find_parent(class_="filters"):
        errors.append(
            f"#{sid} ligger inuti .filters – ska vara utanför (eget block under filtren)"
        )

# Varje sida med datumfilter ska ha en Uppdatera-knapp INNAN .quick-dates
for page in soup.select(".page"):
    pid = page.get("id", "?")
    filters_div = page.find(class_="filters")
    if not filters_div:
        continue
    children = list(filters_div.children)
    update_idx = None
    quick_idx = None
    for i, el in enumerate(children):
        if not hasattr(el, "get"):
            continue
        cls = el.get("class", [])
        text = el.get_text(strip=True)
        if "quick-dates" in cls:
            quick_idx = i
        if el.name == "button" and "Uppdatera" in text:
            update_idx = i
    if update_idx is not None and quick_idx is not None:
        if update_idx > quick_idx:
            errors.append(
                f"#{pid}: Uppdatera-knappen ligger EFTER .quick-dates – ska vara fore"
            )

# Varje flik med projekt-dropdown ska ha ett proj-summary utanför .filters
for page in soup.select(".page"):
    pid = page.get("id", "?")
    has_proj_select = page.find("select", id=re.compile(r".*-project$"))
    if not has_proj_select:
        continue
    summary_outside = page.find(class_="proj-summary", recursive=False)
    if not summary_outside:
        # Kolla direkt under page (ett steg ner)
        summary_outside = next(
            (c for c in page.children
             if hasattr(c, "get") and "proj-summary" in (c.get("class") or [])),
            None
        )
    if not summary_outside:
        errors.append(
            f"#{pid} har projekt-dropdown men saknar proj-summary utanför .filters"
        )

# ── Resultat ──────────────────────────────────────────────────
if errors:
    print("\ncheck_layout: MISSLYCKADES\n")
    for e in errors:
        print(f"  FEL: {e}")
    print()
    sys.exit(1)
else:
    print("check_layout: OK")
    sys.exit(0)
