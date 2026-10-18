# math-aware-source-digest

A Claude Code skill and Python package (`math_aware_source_digest`, command
`masd`) that turns research papers and books into verified, machine-readable
**source entries** for agentic review of prior work: a citation with the
provenance of each field, the version described, a summary, a notation map,
the results with their locations and stated assumptions, every cited equation
exact or marked "unverified", and a list of what the entry leaves out.

The problem it solves is **mathematics**. PDF converters and models silently
swap look-alike symbols (γ and y, φ̃ and φ̂, 𝒲 and 𝒱), drop terms and change
relations. The skill takes equations from an exact form (arXiv LaTeX, PMC
XML) when one exists, and otherwise checks every cited span against the page.

**Local first:** every stage runs on local models; no text of a source leaves
the machine. Status: in development, following [the plan](planning/plan.md)
gate by gate.

## Example and test papers

All test data is in the public domain or under CC0, CC BY or CC BY-SA, so
anyone may fetch it, send it to a cloud model for judging, and reproduce the
results. Two public-domain scans serve as the running examples of tests,
judging and documentation; both are good test sources for anyone evaluating
a PDF-to-LaTeX pipeline.

### Student (1908): the example paper; a degraded scan

> Student [W. S. Gosset] (1908). The probable error of a mean.
> *Biometrika* 6(1):1–25. DOI [10.2307/2331554](https://doi.org/10.2307/2331554).

- **Copy:** [Zenodo record 1449458](https://zenodo.org/records/1449458),
  `article.pdf` (1.6 MB, MD5 `181bb5eb51fe36714c79dc8b8ef35ce5`), released
  under **CC0 1.0**.
- **What it tests:** recognizing characters on a century-old scan. The PDF
  is JSTOR's cover sheet plus 25 pages of page images with an OCR text layer
  that JSTOR added (which the tool ignores). Its display equations have
  stacked fractions, Greek letters (μ₂, σ, φ, ψ), subscripts on subscripts
  and superscripts on exponents, and a Latin y beside the Greek letters;
  sections VII–IX are numeric tables. Printed page 1 is PDF page 2.
- **What it does not test:** modern notation. It has no bold, calligraphic or
  blackboard letters, no accents such as tildes and hats, and no operators,
  norms or matrices.

### Hestenes and Stiefel (1952): notation-heavy

> Hestenes, M. R., and Stiefel, E. (1952). Methods of conjugate gradients
> for solving linear systems. *Journal of Research of the National Bureau of
> Standards* 49(6):409–436. DOI
> [10.6028/jres.049.044](https://doi.org/10.6028/jres.049.044).

- **Copy:** the PDF that the DOI resolves to,
  [`jresv49n6p409_A1b.pdf`](https://nvlpubs.nist.gov/nistpubs/jres/049/jresv49n6p409_A1b.pdf)
  on NIST's server (30.0 MB, MD5 `f7a162ff6f4048dd0ace9d0abf492073`). NIST
  states that the papers of its Journal of Research are U.S. Government
  publications in the public domain.
- **What it tests:** the notation on which converters and models fail, on a
  scan: adjoints (`A*r`), primes (`R'_{i+1}`), norms in fractions, inner
  products (`(p_i, Ap_j)`), compound indices (`i+1`, `m-1`), ellipses, Greek
  letters, a two-column layout, and equation numbers in its own style
  (`(4:1a)`, `(3:8)`). 28 pages of page images with an invisible OCR layer.
  Printed page 409 is PDF page 1.

Both are part of the judged set of the ground truth (plan section 6.1), with
three born-digital CC BY journal articles (to be chosen). A typewritten report with hand-lettered
symbols is still to be chosen. Other test sets vary the publisher, the math
typeface (Times-like, Computer Modern, Cambria Math, ...) and the era, because
look-alike swaps depend on glyph shapes and house styles.

## Development

See [CLAUDE.md](CLAUDE.md) for the rules of this repository and the branch
and PR workflow. All checks run with

```bash
nix develop --command scripts/check
```

## Licence

MIT; see [LICENSE](LICENSE).
