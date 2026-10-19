# Transcription conventions

Status: **specification**, 2026-10-19, taken from judge prompt version 8 and
layer 1 of the comparison (branches `feature/judge-prompt-v4` and
`feature/layer1`, not yet merged). Every rule here was decided with the
user on 2026-10-18 or 19; the evidence is in `planning/comparison.md`,
sections 5 and 8 (PR #38, not yet merged).

One specification for everyone who writes or reads a transcription of a
page's mathematics:

- the **judges** that build the ground truth (gate 1);
- the **local transcribers** and the PDF converters that are scored against
  it (gates 2, 3 and 6), and the second transcription of stage 5;
- the **adjudicator** that settles a disagreement;
- the **comparison** (layer 1), which decides when two transcriptions are
  the same.

The judge prompt, the transcriber prompts and the adjudicator's question
should quote this document, not restate it in their own words. Until they
do, the judge prompt (version 8) is the text the judges see, and a
difference between the two is a defect in one of them.

## 1. What is transcribed

- **Display mathematics of the running text:** mathematics set on its own
  line or lines, numbered or not.
- **Formulas in captions and tables:** in the caption of a table or a
  figure, and in a table's heading, cells or notes, whether on its own line
  or within the caption's text.
- **Not transcribed:** inline mathematics within a sentence of the running
  text; plain numbers, also with a sign, brackets or a relation ("(≈ 5)");
  a lone footnote marker (†, *); labels inside a figure.

Each line records **where** it is: `text`, `caption` or `table`.

## 2. The unit: one printed line

- **One entry per printed line.** A display set over several lines gives one
  entry for each line, with no `aligned` environment and no `\\`.
- **A matrix, an array or a cases construction is one entry,** with all its
  rows: its rows are not lines of the display.
- **Grouping is recorded apart from the lines:**
  - `continues`: the line continues the equation of the line before it (one
    equation set over several lines); false for the first line after text;
  - `braced`: a brace or bracket printed beside the lines joins the line to
    the line before it.
- **Numbers:** `number` is the equation number printed beside the line,
  exactly as printed with its brackets; a number centred beside several
  lines goes on the last of them. The number is not part of the LaTeX.

## 3. The LaTeX target

A transcription is LaTeX that, set by **LaTeX with these packages and
nothing else**, prints what the page shows: the same symbols, in the same
places, in the same fonts.

| package | for |
|---|---|
| amsmath | environments, `\boldsymbol`, `\operatorname`, `\text`, `\overset`, extensible arrows |
| amssymb | `\mathbb`, `\mathfrak`, relations such as `\leqq` and `\lesssim` |
| mathrsfs | `\mathscr`, script letters (distinct from `\mathcal`) |
| upgreek | upright lowercase Greek (`\upmu`, `\uppi`) |
| dsfont | `\mathds{1}`, the double-struck one |
| stmaryrd, `\llbracket` and `\rrbracket` only | double brackets |

Only commands that LaTeX and these packages define; no macros. **As
printed:** misprints included; nothing is normalized, simplified or
corrected.

## 4. How to write what is printed

- **Slant.** A letter printed upright is written with `\mathrm`; a plain
  letter is italic, because LaTeX sets it so. Neither is a default: write
  the slant the page prints, capitals as well as lowercase, and one paper may
  set the same letter both ways. An operator name printed upright is written
  with its command (`\sin`, `\max`).
- **Hand lettering.** In a typewritten document whose symbols are drawn by
  hand, a drawn lowercase Greek letter is written plainly (`\alpha`, not
  `\upalpha`): a drawn letter has no typographic slant.
- **Bold.** `\mathbf` for upright bold, `\boldsymbol` for bold italic and for
  bold Greek. A math alphabet such as `\mathbf` changes only Latin letters,
  digits and Greek capitals, so a bold lowercase Greek letter is
  `\boldsymbol{\alpha}`.
- **Other alphabets.** Calligraphic `\mathcal`, script `\mathscr`, Fraktur
  `\mathfrak`, blackboard `\mathbb`, the double-struck one `\mathds{1}`,
  upright lowercase Greek with upgreek.
- **Dots.** As they sit: `\ldots` on the baseline, `\cdots` centred; never
  `\dots`, whose height LaTeX chooses. In a matrix: a lone printed dot is
  `\cdot`; a run of dots across a row is `\ldots` or `\cdots` as it sits,
  down a column `\vdots`, diagonally `\ddots`; a cell is empty only where
  nothing is printed in it.
- **Scripts.** A superscript set after a subscript, rather than above it, is
  written `x_1{}^2`. Primes and stars where they sit (`u^*` against `u_*`).
- **Accents.** `\hat`, `\tilde`, `\dot` as printed; a bar accent over one
  symbol (`\bar{R}`) is not a rule over what is under it (`\overline{R}`),
  whose length follows its content.
- **Words.** Words set as part of the formula ("if", "or", "other terms")
  are kept, with `\text`; words of the surrounding text ("Now", "whence",
  "Theoretical Equation:") and a footnote mark set by the formula are left
  out.
- **Punctuation.** All of it as printed, also at the end of a line.
- **Matrices.** `bmatrix`, or the environment of the brackets printed.

## 5. Uncertainty

Some glyphs are often confused. A reader decides each one from the page, and
records it in `uncertain` whenever the page does not settle it:

- `\leqq` (≦) against `\leq` (≤), and `\geqq` against `\geq`;
- a double bar `\|` (‖) against two single bars;
- the slant of a letter;
- `\bar` against `\overline`;
- dots on the baseline against centred;
- a prime against none;
- 1 against i against l;
- a comma against a full stop.

`uncertain` names the part ("subscript of the second sigma"); it is empty if
nothing is uncertain. A line marked uncertain is adjudicated (section 7).

## 6. When two transcriptions are the same

Layer 1 of the comparison (`src/math_aware_source_digest/layout.py` on
`feature/layer1`): two transcriptions are the same when LaTeX with the
packages of section 3 prints them the same, apart from spacing and sizing.
So, for example:

- the same: `x_i^2` and `x^2_i`; `x'` and `x^{\prime}`; `\frac`, `\dfrac`
  and `\tfrac`; `\le` and `\leq`; `\mid` and `|`; `\max` and
  `\operatorname{max}`; `pmatrix` and `\left(` with an `array`; `\dots` and
  the dots amsmath sets for it;
- different: `\mathrm{d}` and `d`; `\mathbf{x}` and `\boldsymbol{x}`;
  `\ldots` and `\cdots`; `\leqq` and `\leq`; `\bar` and `\overline`; a line
  break and none;
- not compared: punctuation at the end of a line.

There is no style level: a difference of font is a difference like any
other.

## 7. How disagreements are settled

- **Pooling:** all readings of a paper under the final prompt version are
  pooled, line by line.
- **Unanimity, not votes:** a line is settled only when every reading has
  it, all readings are the same (section 6), and no reader marked it
  uncertain.
- **Adjudication:** every other line goes to an adjudicator that sees the
  page as four overlapping 300 dpi tiles and a question naming where the
  readings differ; only a confident verdict settles a line, and the user
  settles the rest.

## 8. Open

- **Positions.** A transcription gives a line's page and order, not its
  place on the page. Gate 2 transcribes crops of single lines, so the
  ground truth needs a way to locate each line (a layout detector, the
  converter's boxes, or the judges asked for boxes); not yet designed.
- **Single source.** The judge prompt restates sections 1-5 in its own
  words. The prompts should be generated from one source (for example a
  module of the package that this document is rendered from), so that the
  judges, the transcribers and the adjudicator cannot drift apart.

## 9. History

The judge prompt that these conventions come from, by version
(`tests/judging/judge.py`; each version's judgements are under
`ground_truth/<key>/prompt-<version>/`):

| version | added | because |
|---|---|---|
| 1 | the first prompt (gate 1) | |
| 2 | the LaTeX target and its packages; never `\dots` | the judges' LaTeX had no stated target; dot heights alone gave 29 disagreements on Hestenes–Stiefel |
| 3 | one entry per printed line; `continues`, `braced` | readers grouped lines differently: 22 spurious disagreements |
| 4 | all punctuation; the confusable glyphs; matrix dots; 2000 px grey pages | run-to-run variation; a misreading two readers shared (an upright A) |
| 5 | slant as printed, no default; `\bar` against `\overline` | version 4 read like a preference for upright |
| 6 | captions and table notes, `where`; matrix dots as they sit | the judges disagreed on what to include; version 5 contradicted itself |
| 7 | no surrounding words, no footnote marks | caption formulas brought words with them |
| 8 | formulas in table cells; no plain numbers or lone markers; hand-lettered Greek | the judges disagreed on scope; hand lettering has no slant |

Version 8 is frozen: it changes again only if a run shows a new kind of
spurious disagreement.
