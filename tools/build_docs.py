#!/usr/bin/env python3
"""Generate the documentation pages under docs/ from a SANKHYA checkout.

    python tools/build_docs.py --solver ../SANKHYA
    python tools/build_docs.py --solver ../SANKHYA --check-external

Nothing in docs/ is written by hand. Each page is a solver document converted from
Markdown at one pinned commit, wrapped in the site's shell; the technical report is
content/report.md with its {{include ...}} directives resolved from the same commit.
The run refuses a dirty solver tree, is deterministic, and fails on any broken link,
on any table whose row count differs from its source, and on any number in a page
that does not appear in the source it came from.
"""
import argparse
import html
import json
import posixpath
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import markdown

sys.path.insert(0, str(Path(__file__).resolve().parent))
import facts as site_facts  # noqa: E402  (the site's own one-fact-one-value renderer)

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs"
REPO = "https://github.com/thegoodengineers/SANKHYA"
SITE_REPO = "https://github.com/thegoodengineers/sankhya-web"
MD_VERSION = "3.7"

# slug, title, source in the solver repo (None: assembled in this repo), hub sentence.
DOCS = [
    ("benchmarks", "Benchmarks", "docs/BENCHMARKS.md",
     "Every measured result, the file it came from, and what each number does and does not say."),
    ("report", "Technical report", None,
     "The solver end to end, assembled from the documents below: design, engines, method, results and limits."),
    ("coverage", "Problem statement coverage", "docs/PS26119_COVERAGE.md",
     "What the problem statement asks for, row by row, against what exists on main."),
    ("architecture", "Architecture", "docs/ARCHITECTURE.md",
     "How a solve flows through the modules, and the promises every engine is held to."),
    ("provenance", "Provenance", "docs/PROVENANCE.md",
     "Every dependency and algorithm with its licence or citation, and why none of them is a solver."),
    ("negative-results", "Negative results", "docs/NEGATIVE-RESULTS.md",
     "What was built and then demoted, left opt-in or withdrawn, and the measurement that decided it."),
    ("gpu-plan", "GPU plan", "docs/GPU_PLAN.md",
     "The plan written before the GPU existed, and what the hardware lets the project claim."),
    ("adding-an-engine", "Adding an engine", "docs/ADDING_AN_ENGINE.md",
     "How a new engine plugs into the one solve entry point, step by step."),
    ("case-study-refinery", "Refinery case study", "docs/case_studies/refinery.md",
     "A multi-period refinery planning model: its structure, its size ladder and what a planner reads."),
    ("engineering-rules", "Engineering rules", "ENGINEERING_RULES.md",
     "The rules the team works under: provenance, evidence, tolerances and the definition of done."),
]
REPORT_SOURCE = "content/report.md"
SOURCE_TO_SLUG = {src: slug for slug, _, src, _ in DOCS if src}
SUB = ' class="sub"'

FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
LINK = re.compile(r'(!?\[(?:[^\]\\]|\\.)*\])\(\s*<?([^)\s>]+)>?(\s+"[^"]*")?\s*\)')
INCLUDE = re.compile(r'^\{\{include\s+(\S+)(?:\s+(lead|section\s+"([^"]+)"|rows((?:\s+"[^"]+")+)))?\s*\}\}\s*$')
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


class BuildError(Exception):
    pass


# ---------------------------------------------------------------- the solver checkout
def git(solver, *args):
    return subprocess.run(["git", "-C", str(solver), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


def pin(solver):
    if git(solver, "status", "--porcelain"):
        raise BuildError(f"{solver} has uncommitted changes; generate only from a clean checkout")
    full = git(solver, "rev-parse", "HEAD")
    date = git(solver, "log", "-1", "--format=%cd", "--date=short")
    files = set(git(solver, "ls-tree", "-r", "--name-only", "HEAD").splitlines())
    dirs = {posixpath.dirname(f) for f in files}
    while "" in dirs:
        dirs.discard("")
    for d in list(dirs):
        while d:
            dirs.add(d)
            d = posixpath.dirname(d)
    return full, date, files, dirs


def read(solver, path):
    return (Path(solver) / path).read_text(encoding="utf-8").replace("\r\n", "\n")


# ---------------------------------------------------------------- markdown, fence-aware
def outside_fences(lines):
    """Yield (index, line, in_fence) so callers never touch fenced code."""
    fence = None
    for i, line in enumerate(lines):
        m = FENCE.match(line)
        if m:
            mark = m.group(1)
            if fence is None:
                fence = mark[0] * 3
                yield i, line, True
                continue
            if mark.startswith(fence):
                fence = None
                yield i, line, True
                continue
        yield i, line, fence is not None


def canonical(target, src):
    """Rewrite one link target to sankhya:///path#anchor, or leave it alone."""
    for prefix in (REPO + "/blob/main/", REPO + "/tree/main/"):
        if target.startswith(prefix):
            return "sankhya:///" + target[len(prefix):]
    if re.match(r"^[a-z][a-z0-9+.-]*:", target, re.I):
        return target
    path, _, anchor = target.partition("#")
    if not path and src == REPORT_SOURCE:
        return target
    if not path:
        resolved = src
    else:
        resolved = posixpath.normpath(posixpath.join(posixpath.dirname(src), path))
    return "sankhya:///" + resolved + ("#" + anchor if anchor else "")


def prepare(text, src):
    """Drop the H1, and turn every link into a canonical target relative to nothing."""
    lines = text.split("\n")
    out, dropped_h1 = [], False
    for _, line, in_fence in outside_fences(lines):
        if not in_fence:
            if not dropped_h1 and line.startswith("# "):
                dropped_h1 = True
                continue
            line = LINK.sub(lambda m: m.group(1) + "(" + canonical(m.group(2), src)
                            + (m.group(3) or "") + ")", line)
        out.append(line)
    return "\n".join(out).strip("\n") + "\n"


def headings(text):
    return [(i, len(m.group(1)), m.group(2)) for i, line, f in outside_fences(text.split("\n"))
            if not f and (m := HEADING.match(line))]


def extract(text, mode, name, src):
    lines = text.split("\n")
    hs = headings(text)
    if mode is None:
        start = hs[0][0] + 1 if hs and hs[0][1] == 1 else 0
        return "\n".join(lines[start:]), 2
    if mode == "lead":
        if not hs or hs[0][1] != 1:
            raise BuildError(f"{src}: no title heading to take the lead from")
        end = next((i for i, lvl, _ in hs[1:]), len(lines))
        return "\n".join(lines[hs[0][0] + 1:end]), None
    exact = [h for h in hs if h[2] == name]
    found = exact or [h for h in hs if h[2].startswith(name)]
    if len(found) != 1:
        raise BuildError(f'{src}: section "{name}" matches {len(found)} headings')
    i, level, _ = found[0]
    end = next((j for j, lvl, _ in hs if j > i and lvl <= level), len(lines))
    return "\n".join(lines[i:end]), level


def extract_rows(text, names, src):
    """The table rows whose first cell is one of names, under that table's own header."""
    want = [n.strip() for n in names]
    lines = text.split("\n")
    best = None
    i = 0
    while i < len(lines):
        if lines[i].lstrip().startswith("|") and i + 1 < len(lines) and re.match(r"^\s*\|?\s*:?-{3,}", lines[i + 1]):
            j = i + 2
            rows = []
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                first = lines[j].strip().strip("|").split("|")[0].strip().strip("*").strip()
                if first in want:
                    rows.append((want.index(first), lines[j]))
                j += 1
            if rows and (best is None or len(rows) > len(best[1])):
                best = (lines[i:i + 2], rows)
            i = j
        else:
            i += 1
    found = {k for k, _ in best[1]} if best else set()
    missing = [n for k, n in enumerate(want) if k not in found]
    if missing:
        raise BuildError(f"{src}: no table row named {missing}")
    return "\n".join(best[0] + [line for _, line in best[1]])


def shift(text, delta):
    if not delta:
        return text
    out = []
    for _, line, in_fence in outside_fences(text.split("\n")):
        m = None if in_fence else HEADING.match(line)
        if m:
            line = "#" * max(1, min(6, len(m.group(1)) + delta)) + " " + m.group(2)
        out.append(line)
    return "\n".join(out)


def assemble_report(solver):
    """content/report.md with its include directives resolved. Returns (markdown, sources used)."""
    text = (ROOT / REPORT_SOURCE).read_text(encoding="utf-8").replace("\r\n", "\n")
    check_report_prose(text)
    out, used = [], []
    for line in text.split("\n"):
        m = INCLUDE.match(line.strip())
        if not m:
            out.append(line)
            continue
        path, mode = m.group(1), m.group(2)
        body = read(solver, path)
        if mode and mode.startswith("rows"):
            names = re.findall(r'"([^"]+)"', m.group(4))
            piece = prepare("# drop\n" + extract_rows(body, names, path), path)
            label = f"{path} · rows: {', '.join(names)}"
        else:
            mode = "lead" if mode == "lead" else (None if mode is None else "section")
            piece, level = extract(body, mode, m.group(3), path)
            piece = prepare(piece if mode == "section" else "# drop\n" + piece, path)
            if level:
                piece = shift(piece, 3 - level)
            label = f"{path} · " + (m.group(3) and next(h for _, _, h in headings(body)
                                                        if h == m.group(3) or h.startswith(m.group(3)))
                                    or ("the opening, before the first section" if mode == "lead" else "the whole document"))
        used.append(path)
        label = html.escape(re.sub(r"[`*]", "", label))
        out.append(f'<details class="included" markdown="1">\n<summary>{label}</summary>\n\n{piece}\n\n</details>')
    return prepare("\n".join(out), REPORT_SOURCE), used


def check_report_prose(text):
    """The connecting prose may carry no measured number: only section numbers and issue refs."""
    for n, line in enumerate(text.split("\n"), 1):
        if INCLUDE.match(line.strip()) or HEADING.match(line):
            continue
        scrub = re.sub(r"https?://\S+", "", re.sub(r"<[^>]+>", "", line))
        scrub = re.sub(r"\]\(#[^)]*\)", "]", scrub)
        scrub = re.sub(r"^\*\*\d+ ", "**", scrub.strip())
        scrub = re.sub(r"#\d+", "", scrub)
        if re.search(r"\d", scrub):
            raise BuildError(f"{REPORT_SOURCE}:{n}: a number in the connecting prose: {line.strip()}")


# ---------------------------------------------------------------- html
def gh_slug(text, seen):
    base = re.sub(r"[^\w\- ]", "", html.unescape(re.sub(r"<[^>]+>", "", text)).strip().lower()).replace(" ", "-")
    slug, n = base, seen.get(base, 0)
    if n:
        slug = f"{base}-{n}"
    seen[base] = n + 1
    return slug


def to_html(md_text):
    body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists", "md_in_html"], output_format="html")
    seen, toc = {}, []

    def head(m):
        level, inner = int(m.group(1)), m.group(2)
        slug = gh_slug(inner, seen)
        if level in (2, 3):
            label = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
            if len(label) > 90:
                label = label[:87].rstrip() + "..."
            toc.append((level, slug, html.escape(label)))
        return f'<h{level} id="{slug}">{inner}</h{level}>'

    body = re.sub(r"<h([1-6])>(.*?)</h\1>", head, body, flags=re.S)
    body = re.sub(r"<table>", '<div class="table-wrap"><table class="doc-table">', body)
    body = body.replace("</table>", "</table></div>")
    return body, toc


def resolve_links(body, slug, full, files, dirs, images):
    def one(m):
        attr, target = m.group(1), html.unescape(m.group(2))
        if not target.startswith("sankhya:///"):
            return m.group(0)
        path, _, anchor = target[len("sankhya:///"):].partition("#")
        frag = "#" + anchor if anchor else ""
        if path in SOURCE_TO_SLUG:
            dest = SOURCE_TO_SLUG[path]
            url = frag if dest == slug and frag else f"/docs/{dest}{frag}"
        elif path.startswith("docs/img/") and path in files:
            images.add(path)
            url = "/docs/img/" + posixpath.basename(path)
        elif path in files:
            url = f"{REPO}/blob/{full}/{path}{frag}"
        elif path.rstrip("/") in dirs:
            url = f"{REPO}/tree/{full}/{path.rstrip('/')}{frag}"
        else:
            raise BuildError(f"docs/{slug}: link to {path}, which is not in the solver repo at {full[:7]}")
        return f'{attr}="{html.escape(url, quote=True)}"'

    return re.sub(r'(href|src)="([^"]*)"', one, body)


# ---------------------------------------------------------------- the page shell
def shell_parts():
    index = (ROOT / "index.html").read_text(encoding="utf-8")
    favicon = re.search(r'<link rel="icon"[^>]*>', index).group(0)
    fonts = re.search(r'<link href="https://fonts\.googleapis\.com[^>]*>', index).group(0)
    doors = re.search(r'<nav class="doors".*?</nav>', index, re.S).group(0)
    doors = doors.replace(' aria-current="page"', "")
    if '<a href="/docs">Docs</a>' not in doors:
        raise BuildError('index.html has no "Docs" link in its nav')
    doors = doors.replace('<a href="/docs">Docs</a>', '<a href="/docs" aria-current="page">Docs</a>')
    return favicon, fonts, doors


def page(slug, title, description, header_html, main_html, toc):
    favicon, fonts, doors = shell_parts()
    url = "https://sankhya-solver.vercel.app/docs" + ("" if slug == "index" else "/" + slug)
    here = "".join('<a href="#%s"%s>%s</a>' % (s, SUB if lvl == 3 else "", html.escape(html.unescape(t)))
                   for lvl, s, t in toc)
    here_nav = f'  <hr class="rail-rule">\n  <nav class="here" aria-label="On this page">{here}</nav>\n' if toc else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<title>{html.escape(title)} · SANKHYA</title>
<meta name="description" content="{html.escape(description, quote=True)}">
<meta property="og:title" content="{html.escape(title)} · SANKHYA">
<meta property="og:description" content="{html.escape(description, quote=True)}">
<meta property="og:type" content="website">
<meta property="og:url" content="{url}">
<link rel="canonical" href="{url}">
{favicon}
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
{fonts}
<link rel="stylesheet" href="/styles.css">
<script src="/site.js" defer></script>
</head>
<body class="doc">
<a class="skip" href="#content">Skip to content</a>
<div class="shell">
<aside class="rail">
  <a class="brand" href="/"><span class="brand-mark" aria-hidden="true"></span>SANKHYA<small>SIH26119</small></a>
  {doors}
{here_nav}</aside>
<main class="col" id="content">
{header_html}
{main_html}
<footer>
<!-- fragment:footer -->
<!-- /fragment:footer -->
</footer>
</main>
</div>
</body>
</html>
"""


def doc_header(title, src_link, src_label, full, date):
    short = full[:7]
    return (f'<header class="page" id="top"><div class="wrap">'
            f'<nav class="crumbs" aria-label="Breadcrumb"><a href="/docs">Docs</a><span aria-hidden="true">/</span>{html.escape(title)}</nav>'
            f'<h1>{html.escape(title)}</h1>'
            f'<p class="doc-banner">Generated from <a href="{src_link}"><code>{src_label}</code></a> at commit '
            f'<a href="{REPO}/commit/{full}"><code>{short}</code></a> ({date}). Do not edit this page by hand.</p>'
            f'</div></header>')


def mobile_toc(toc):
    if not toc:
        return ""
    items = "".join('<li%s><a href="#%s">%s</a></li>' % (SUB if lvl == 3 else "", s, html.escape(html.unescape(t)))
                    for lvl, s, t in toc)
    return f'<details class="doc-toc"><summary>Contents</summary><ol>{items}</ol></details>'


# ---------------------------------------------------------------- checks
def table_shape(md_text):
    """Row counts of every pipe table in the markdown, fence-aware, header row excluded."""
    shapes, run = [], []
    lines = md_text.split("\n") + [""]
    for _, line, in_fence in outside_fences(lines):
        is_row = not in_fence and line.lstrip().startswith("|")
        if is_row:
            run.append(line)
            continue
        if len(run) >= 2 and re.match(r"^\s*\|?\s*:?-{3,}", run[1]):
            shapes.append(len(run) - 2)
        run = []
    return shapes


def html_table_shape(body):
    return [len(re.findall(r"<tr>", t.split("</thead>", 1)[1] if "</thead>" in t else t))
            for t in re.findall(r"<table.*?</table>", body, re.S)]


def numbers_not_in_source(article_html, source_text):
    text = html.unescape(re.sub(r"<[^>]+>", " ", article_html))
    have = set(NUMBER.findall(source_text))
    return sorted({n for n in NUMBER.findall(text) if n not in have})


def check_links(pages, full, files, dirs, check_external, site_images=frozenset()):
    ids = {}
    for rel, text in pages.items():
        ids[rel] = set(re.findall(r'\sid="([^"]+)"', text))
    for extra in ROOT.glob("*.html"):
        ids.setdefault(extra.name, set(re.findall(r'\sid="([^"]+)"', extra.read_text(encoding="utf-8"))))
    problems, external = [], set()
    for rel, text in pages.items():
        text = re.sub(r'<link rel="preconnect"[^>]*>', "", text)
        for target in re.findall(r'(?:href|src)="([^"]+)"', text):
            target = html.unescape(target)
            if target.startswith("https://sankhya-solver.vercel.app"):
                target = target[len("https://sankhya-solver.vercel.app"):] or "/"
            path, _, anchor = target.partition("#")
            if target.startswith("#"):
                if anchor not in ids[rel]:
                    problems.append(f"{rel}: #{anchor} has no target")
            elif target.startswith("/"):
                clean = path.rstrip("/") or "/"
                cands = ["index.html"] if clean == "/" else [clean.lstrip("/") + ".html", clean.lstrip("/") + "/index.html",
                                                            clean.lstrip("/")]
                hit = next((c for c in cands if (ROOT / c).is_file() or c in pages or c in site_images), None)
                if not hit:
                    problems.append(f"{rel}: {target} does not exist on the site")
                elif anchor and hit.endswith(".html") and anchor not in ids.get(hit, set()):
                    problems.append(f"{rel}: {target} has no #{anchor}")
            elif target.startswith(REPO + "/blob/") or target.startswith(REPO + "/tree/"):
                rest = target[len(REPO) + 1:]
                kind, ref, *p = rest.split("/", 2)
                p = p[0].split("#")[0] if p else ""
                if ref == "main" and p:
                    problems.append(f"{rel}: {target} points at main, not at the pinned commit")
                elif ref not in (full, "main"):
                    problems.append(f"{rel}: {target} is pinned to {ref}, not {full}")
                elif p and p not in files and p not in dirs:
                    problems.append(f"{rel}: {target} names a path not in the solver repo")
            elif target.startswith(SITE_REPO + "/blob/main/"):
                if not (ROOT / target[len(SITE_REPO + "/blob/main/"):].split("#")[0]).is_file():
                    problems.append(f"{rel}: {target} is not a file in this repo")
            elif re.match(r"^https?://", target):
                external.add(target.split("#")[0])
    if check_external:
        for url in sorted(external):
            try:
                req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "sankhya-docs-linkcheck"})
                urllib.request.urlopen(req, timeout=20)
            except Exception as e:  # noqa: BLE001
                problems.append(f"external {url}: {e}")
    return problems, external


# ---------------------------------------------------------------- main
def build(solver, check_external=False):
    if markdown.__version__ != MD_VERSION:
        raise BuildError(f"markdown {markdown.__version__} installed; the pages are built with {MD_VERSION} "
                         f"(pip install markdown=={MD_VERSION}) so that output stays byte-identical")
    full, date, files, dirs = pin(solver)
    short = full[:7]
    facts = site_facts.load_facts()
    fragments = {p.stem: p.read_text(encoding="utf-8") for p in (ROOT / "fragments").glob("*.html")}
    pages, images, report = {}, set(), []
    for slug, title, src, blurb in DOCS:
        if src is not None and src not in files:
            report.append(f"skipped {slug}: {src} is not in the solver repo at {short}")
            continue
        if src is None:
            md_text, used = assemble_report(solver)
            source_text = (ROOT / REPORT_SOURCE).read_text(encoding="utf-8") + "".join(read(solver, u) for u in used)
            src_link, src_label = f"{SITE_REPO}/blob/main/{REPORT_SOURCE}", REPORT_SOURCE
            shape_expected = table_shape(md_text)
        else:
            raw = read(solver, src)
            md_text = prepare(raw, src)
            source_text = raw
            src_link, src_label = f"{REPO}/blob/{full}/{src}", src
            shape_expected = table_shape(raw)
        body, toc = to_html(md_text)
        body = resolve_links(body, slug, full, files, dirs, images)
        got = html_table_shape(body)
        if got != shape_expected:
            raise BuildError(f"docs/{slug}: tables {got} do not match the source's {shape_expected}")
        extra = numbers_not_in_source(body, source_text)
        if extra:
            raise BuildError(f"docs/{slug}: numbers not in the source: {extra[:20]}")
        header = doc_header(title, src_link, src_label, full, date)
        main_html = mobile_toc(toc) + f'\n<article class="doc-body">\n{body}\n</article>'
        pages[f"docs/{slug}.html"] = page(slug, title, blurb, header, main_html, toc)
        report.append(f"docs/{slug}.html  <- {src_label}: {len(got)} tables, rows {sum(got)}")
    # the hub
    cards = "\n".join(
        f'      <a class="doc-card" href="/docs/{slug}"><span class="label">{html.escape(src or REPORT_SOURCE)}</span>'
        f"<h3>{html.escape(title)}</h3><p>{html.escape(blurb)}</p><span class=\"more\">Read →</span></a>"
        for slug, title, src, blurb in DOCS if f"docs/{slug}.html" in pages)
    hub_header = (f'<header class="page" id="top"><div class="wrap"><div class="label"><span class="n">Docs</span> · generated</div>'
                  f"<h1>Documentation</h1>"
                  f'<p class="lede">The solver\'s own documents, converted as they stand in the repository. Nothing here is retyped.</p>'
                  f'<p class="doc-banner">Generated from SANKHYA at <a href="{REPO}/commit/{full}"><code>{short}</code></a>, {date}.</p>'
                  f"</div></header>")
    hub_main = f'<section id="documents">\n  <div class="wrap">\n    <div class="doc-cards">\n{cards}\n    </div>\n  </div>\n</section>'
    pages["docs/index.html"] = page("index", "Documentation",
                                    "The SANKHYA documents, generated from the solver repository at one pinned commit.",
                                    hub_header, hub_main, [])
    # the footer and any fact spans, exactly as the rest of the site renders them
    problems = []
    for rel in list(pages):
        pages[rel] = site_facts.render(pages[rel], facts, fragments, problems, rel)
    if problems:
        raise BuildError("; ".join(problems))
    site_images = {f"docs/img/{posixpath.basename(i)}" for i in images}
    link_problems, external = check_links(pages, full, files, dirs, check_external, site_images)
    if link_problems:
        raise BuildError("broken links:\n  " + "\n  ".join(link_problems))
    # write, deterministically: stale pages go, images are copied byte for byte
    OUT.mkdir(exist_ok=True)
    wanted = set(pages) | {f"docs/img/{posixpath.basename(i)}" for i in images}
    for old in OUT.rglob("*"):
        if old.is_file() and old.relative_to(ROOT).as_posix() not in wanted:
            old.unlink()
    for rel, text in sorted(pages.items()):
        (ROOT / rel).parent.mkdir(parents=True, exist_ok=True)
        (ROOT / rel).write_text(text, encoding="utf-8", newline="\n")
    for img in sorted(images):
        dest = OUT / "img" / posixpath.basename(img)
        dest.parent.mkdir(exist_ok=True)
        shutil.copyfile(Path(solver) / img, dest)
    (OUT / "manifest.json").write_text(json.dumps({"solver_commit": full, "solver_date": date,
                                                   "markdown": MD_VERSION,
                                                   "pages": sorted(pages)}, indent=2) + "\n",
                                       encoding="utf-8", newline="\n")
    report.append(f"pinned {full} ({date}); {len(pages)} pages, {len(images)} images, "
                  f"{len(external)} external links {'checked' if check_external else 'not fetched'}")
    return report


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--solver", required=True, help="path to a clean SANKHYA checkout")
    ap.add_argument("--check-external", action="store_true", help="also fetch every external link")
    args = ap.parse_args()
    try:
        for line in build(Path(args.solver), args.check_external):
            print(line)
    except BuildError as e:
        print("error:", e, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
