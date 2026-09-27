#!/usr/bin/env python3
"""One fact, one value.

facts.json holds every figure the site states, each with the file or command it came from.
The pages carry them as <span data-fact="key">value</span>, and blocks that appear on more
than one page live once in fragments/NAME.html, carried as
<!-- fragment:NAME --> ... <!-- /fragment:NAME -->.

    python tools/facts.py            rewrite every page from facts.json and fragments/
    python tools/facts.py --check    exit 1 if any page disagrees (what CI runs)

Fragments may themselves contain data-fact spans; they are filled after insertion.
"""
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
FACT = re.compile(r'(<span data-fact="([a-z0-9_.]+)">)(.*?)(</span>)', re.S)
FRAG = re.compile(r'(<!-- fragment:([a-z0-9_-]+) -->)(.*?)(<!-- /fragment:\2 -->)', re.S)


def load_facts():
    raw = json.loads((ROOT / "facts.json").read_text(encoding="utf-8"))
    return {k: v["value"] for k, v in raw["facts"].items()}


def render(text, facts, fragments, problems, name):
    def frag(m):
        key = m.group(2)
        if key not in fragments:
            problems.append(f"{name}: unknown fragment '{key}'")
            return m.group(0)
        return m.group(1) + "\n" + fragments[key].strip() + "\n" + m.group(4)

    def fact(m):
        key = m.group(2)
        if key not in facts:
            problems.append(f"{name}: unknown fact '{key}'")
            return m.group(0)
        return m.group(1) + facts[key] + m.group(4)

    return FACT.sub(fact, FRAG.sub(frag, text))


def main():
    check = "--check" in sys.argv[1:]
    facts = load_facts()
    fragments = {p.stem: p.read_text(encoding="utf-8") for p in (ROOT / "fragments").glob("*.html")}
    problems, drift, used = [], [], set()
    for page in sorted(ROOT.glob("*.html")) + sorted(ROOT.glob("docs/*.html")):
        old = page.read_text(encoding="utf-8")
        new = render(old, facts, fragments, problems, page.name)
        used.update(m.group(2) for m in FACT.finditer(new))
        if new != old:
            drift.append(page.name)
            if not check:
                page.write_text(new, encoding="utf-8", newline="")
    unused = sorted(set(facts) - used)
    for p in problems:
        print("error:", p)
    if unused:
        print("note: facts defined but not shown:", ", ".join(unused))
    if check and drift:
        print("drift: these pages disagree with facts.json or fragments/:", ", ".join(drift))
        print("run: python tools/facts.py")
        return 1
    if not check:
        print("rendered:", ", ".join(drift) if drift else "nothing changed")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
