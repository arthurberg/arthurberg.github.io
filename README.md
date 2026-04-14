# arthurberg.com

Source for <https://arthurberg.com>, built with [Quarto](https://quarto.org)
and deployed to GitHub Pages.

## Local preview

```bash
quarto preview
```

## Update publications

```bash
python3 scripts/gen_publications.py
quarto render
```

PDFs live in `papers/<bibkey>.pdf` (colons in bibkeys replaced with
underscores). See `papers/README.md` for details.

## Deploy

Pushing to `main` triggers `.github/workflows/publish.yml`, which renders
the site and publishes `_site/` to GitHub Pages.
