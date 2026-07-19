# arthurberg.com

Source for <https://arthurberg.com>, built with [Quarto](https://quarto.org)
and deployed to GitHub Pages.

## Local preview

```bash
quarto preview
```

## Update publications

```bash
python3 scripts/gen_research.py       # → _research-body.qmd  (the Research page)
python3 scripts/gen_publications.py   # → publications.qmd, _publications-body.qmd
quarto render
```

Each generated file has exactly one owner — run both scripts, in either order.
`scripts/tag_publications.py` holds the research-area tagging rules that both
scripts share; run it without `--write` to preview the tag distribution.

PDFs live in `papers/<bibkey>.pdf` (colons in bibkeys replaced with
underscores). See `papers/README.md` for details.

`publications.bib` is kept in sync by hand with `~/cv/Berg3.bib` (the LaTeX
CV) — apply bibliography fixes to both. Annotations are LaTeX source, so
markup like ``` ``quoted'' ``` is correct there and is translated to HTML when
the site is generated.

## Deploy

Pushing to `main` triggers `.github/workflows/publish.yml`, which renders
the site and publishes `_site/` to GitHub Pages.

The workflow pins the Quarto version. Quarto bundles its own search/JS/CSS, so
an unpinned build can change the live site without any commit — bump the
`version:` in the workflow deliberately, and check the rendered output when you
do. Local Quarto may differ from the pinned one; CI output is what ships.
