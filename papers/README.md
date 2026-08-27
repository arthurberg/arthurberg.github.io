# Paper PDFs

Drop PDFs here using the naming convention `<bibkey>.pdf`, with any colons in
the bibkey replaced by underscores. The publications script auto-links them.

Examples:

| Bib key         | Filename         |
|-----------------|------------------|
| `Berg:2025aa`   | `Berg_2025aa.pdf`|
| `Berg:21c`      | `Berg_21c.pdf`   |
| `Hawila:21`     | `Hawila_21.pdf`  |
| `Yee:2025aa`    | `Yee_2025aa.pdf` |

After adding PDFs, regenerate the publications page:

```bash
python3 scripts/gen_publications.py
quarto render
```

## Copyright notice

Only self-host versions you have the right to distribute — typically the
accepted-manuscript (post-print) or preprint, not the publisher's typeset PDF,
unless the journal's open-access license allows it.
