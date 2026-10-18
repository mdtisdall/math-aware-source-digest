# Gate 1: ground truth

The ground truth of the judged set (plan, section 6.1): for each of 7 test
papers, every display equation (LaTeX of what is printed, with its location
and number) and every numbered result, definition and section. Converters and
local transcribers are scored against it at gates 2 and 3.

**Status: closed 2026-10-18.** The transcriptions are complete, and the
judges' accuracy on Zach et al. is measured. Adjudication of the
disagreements moved to gate 1b, which chooses how two readings are compared
(plan, open decision 9), because the number of disagreements depends on the
comparison. The user's acceptance of the merged lists follows adjudication
there.

| criterion (plan, 6.3) | state |
|---|---|
| both judges' transcriptions exist for every paper | yes |
| merged lists exist (before adjudication) | yes (`merge.py <key>`) |
| judges' error rate on Zach et al. reported | yes: no error in 17 transcribable equations, per judge (below) |
| disagreements resolved; the user accepts the lists | moved to gate 1b |

## Method

Two independent judges per paper, each one request to Claude Opus 5.5
(`claude-opus-5-5`, effort `high`, structured output, prompt version 1)
through the API, with every page as a 150-dpi image and no text layer. The
judges transcribe; they do not grade a converter. They are told to write
what is printed, misprints included, and to note what they cannot read with
certainty. Each request record (`judge-N.request.json`) holds the prompt,
the settings and the SHA-256 of each page image; each raw answer is in
`judge-N.response.json`, and the parsed judgement in `judge-N.json`. Tools:
[judge.py](../tests/judging/judge.py), [merge.py](../tests/judging/merge.py),
[source_accuracy.py](../tests/judging/source_accuracy.py).

The merge pairs numbered equations by page and number, unnumbered ones in
order on their page, and compares each pair with the narrow-LaTeX comparator
([compare.py](../src/math_aware_source_digest/compare.py)). Numbered results
and sections pair by kind and number.

## The papers

| paper | form | pages | typefaces | equations (judge 1 / 2) | numbered | items | uncertain notes (1 / 2) |
|---|---|---|---|---|---|---|---|
| student-1908 | scan | 26 | Monotype hot metal, 1908 | 77 / 77 | 0 | 13 | 4 / 4 |
| hestenes-stiefel-1952 | scan | 28 | letterpress, two columns | 331 / 330 | 193 | 57 | 13 / 12 |
| smith-schmidt-mcgee-1962 | scan | 30 | government letterpress | 105 / 105 | 81 | 6 | 3 / 2 |
| blucker-1968 | scan | 18 | typewriter, hand-drawn symbols | 56 / 56 | 12 | 0 | 3 / 5 |
| zach-knoll-pock-2023 | born-digital | 16 | Times, Computer Modern maths | 18 / 18 | 18 | 27 / 28 | 1 / 1 |
| blumenthal-2026 | born-digital | 10 | STIX Two | 13 / 13 | 13 | 12 | 0 / 0 |
| harris-kleefeld-2019 | born-digital | 19 | Times, Computer Modern and Euclid | 64 / 64 | 8 | 13 | 0 / 0 |

Licences, sources and hashes: [testdata/papers.toml](../testdata/papers.toml).
The notes are in each paper's `uncertain.md`.

## Agreement between the judges

| paper | merged equations | agreed | strict | style | only one judge | items agreed |
|---|---|---|---|---|---|---|
| student-1908 | 82 | 54 | 18 | 0 | 10 | 13 / 13 |
| hestenes-stiefel-1952 | 331 | 298 | 32 | 0 | 1 | 57 / 57 |
| smith-schmidt-mcgee-1962 | 105 | 90 | 13 | 2 | 0 | 6 / 6 |
| blucker-1968 | 56 | 55 | 0 | 1 | 0 | none |
| zach-knoll-pock-2023 | 18 | 17 | 1 | 0 | 0 | 27 / 28 |
| blumenthal-2026 | 13 | 13 | 0 | 0 | 0 | 12 / 12 |
| harris-kleefeld-2019 | 64 | 64 | 0 | 0 | 0 | 13 / 13 |
| **total** | **669** | **591 (88%)** | 64 | 3 | 11 | 128 / 129 |

The three born-digital papers agree almost entirely; all disagreements but
one are in the scans.

**What the 78 disagreements are,** from reading the pairs (not adjudicated;
counts approximate):

- **Notation that means the same:** an ellipsis on the baseline or centred
  (`\ldots`, `\cdots`; about 24 in Hestenes–Stiefel), `\leqq` against `\leq`,
  the 1908 multiplication point as `\cdot` or `.` (about 9 in Student),
  `F_{\mathrm{CSM}}` against `F_{CSM}`, `\lambda_{\max}` against
  `\lambda_{max}`. A comparison by meaning would settle these.
- **Layout:** a brace that groups several lines under one number, kept by one
  judge and left out by the other (about 11 in Smith et al.).
- **Pairing:** where one judge splits or leaves out an unnumbered equation,
  the pairs after it on the page shift (about 9 in Student, 3 in
  Hestenes–Stiefel).
- **Different readings:** `f(x_i)` against `f(x_1)`, the number of dots in a
  sparse matrix, a comma, `\hat{x}_{K-1}` (as printed) against `_{k-1}`, and
  equations that only one judge listed (about 10 in Student, 1 in
  Hestenes–Stiefel).

## The judges' accuracy on Zach et al.

Zach, Knoll and Pock (2023) has its authors' LaTeX under CC BY
(`testdata/sources/zach-knoll-pock-2023/`). Its 18 numbered equations, with
the paper's macros expanded, were compared with each judge's reading of the
same number ([source-accuracy.json](zach-knoll-pock-2023/source-accuracy.json)):

| judge | same meaning | different | drawn symbol |
|---|---|---|---|
| 1 | 17 | 0 | 1 |
| 2 | 17 | 0 | 1 |

Equation (16) ends in a crop icon that the paper draws with TikZ; no LaTeX can
match it, and both judges said so in their notes. Every other equation
matches: no judge error found.

Limits: 17 equations of one born-digital paper; the source is the arXiv
version and the page images are the version of record. This measures the
judges on clean type only. The scans, where the disagreements are, have no
exact source.

## Cost

| run | judges | cost (US$) |
|---|---|---|
| Blumenthal judge 1 (single request, 2026-10-18) | 1 | 0.24 |
| batch `msgbatch_018hZTt878Z1Dap146WQEZCD` (half price) | 13 | 4.15 |
| batch `msgbatch_0163rsNAcYz2pREcmx5mJWRj`, Hestenes–Stiefel judge 1 rerun | 1 | 0.64 |
| **total** | | **5.03** |

US$0.80 of it was Hestenes–Stiefel's first judge 1, cut off at 64,000
output tokens and invalid; the rerun allowed 128,000 and used 63,136. Its
judge 2 (60,940 tokens) was not squeezed: the two agree on the equation count
of every page but the last.

## Notes for later gates

- **Agreement is not correctness.** The two judges are the same model with the
  same prompt, so their errors may be correlated: where both misread the same
  glyph, the merge accepts it. Zach et al. checks this only on clean type.
- **Transcription limits:** a 300-equation paper needs about 61,000 output
  tokens; long papers need 128,000.
- **Printed, not intended:** one judge corrected a misprint (`K` to `k`)
  against its instructions; the plan now says so explicitly (section 1a).

## What gate 1b does with it

1. The comparison (narrow LaTeX, a meaning representation, a local
   equivalence model), refined with the user first.
2. Adjudication of the remaining disagreements with it (`merge.py <key>
   --adjudicate`, one Opus call per disagreement, seeing the whole page).
3. The user's review of what adjudication cannot settle, and acceptance of
   the merged lists.
