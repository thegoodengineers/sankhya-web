# sankhya-web

The project site for [SANKHYA](https://github.com/thegoodengineers/SANKHYA), the
optimization solver built for Smart India Hackathon 2026, problem statement SIH26119
(Mangalore Refinery and Petrochemicals Ltd).

Static HTML and CSS, no build step. Deployed on Vercel from `main` at https://sankhya-solver.vercel.app.

## Edit

Eight pages (`index.html`, `evaluate.html`, `problem.html`, `solver.html`, `evidence.html`,
`run.html`, `roadmap.html`, `team.html`), one stylesheet (`styles.css`) and `site.js` for
the "On this page" list. Serve the folder with any static server to preview.

**One fact, one value.** Every figure the site states is defined once in `facts.json`,
each with the file or command it came from on SANKHYA's `main`. Pages carry it as
`<span data-fact="key">value</span>`. Blocks that appear on more than one page (the
scoreboard, the pipeline diagram, the footer) live once in `fragments/` and are carried as
`<!-- fragment:name --> ... <!-- /fragment:name -->`. After editing either:

    python tools/facts.py            # write the values into every page
    python tools/facts.py --check    # what CI runs; fails if any page disagrees

A number changes only when the CSV or the command output behind it changes, and the
footer names the SANKHYA commit the site was last checked against.

## Deploy

Vercel serves the folder as-is. `vercel.json` turns on clean URLs and nothing else.
