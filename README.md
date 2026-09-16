# sankhya-web

The project site for [SANKHYA](https://github.com/thegoodengineers/SANKHYA), the
optimization solver built for Smart India Hackathon 2026, problem statement SIH26119
(Mangalore Refinery and Petrochemicals Ltd).

Static HTML and CSS, no build step. Deployed on Vercel from `main` at https://sankhya-solver.vercel.app.

## Edit

`index.html` is the whole site; `styles.css` is the whole stylesheet. Open `index.html`
in a browser to preview. Every number on the page comes from a CSV in the solver
repository's `bench/results/`, and the file is named beside the number; change the
number only when the CSV changes.

## Deploy

Vercel serves the folder as-is. `vercel.json` turns on clean URLs and nothing else.
