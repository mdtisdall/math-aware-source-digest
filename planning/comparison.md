# Design note: how two readings of an equation are compared (gate 1b)

Status: **decided in part**, 2026-10-18. This is the design note that
plan.md stage 5 (step 3, "A meaning representation") asks for before gate 1b
evaluates anything, and the "note on layers and comparison" that outputs.md
names. The user's decisions of 2026-10-18 are in section 5 and in plan.md
stage 5; what is not listed there is **proposed, not decided**. It changes
no data: the adjudication of gate 1 stays on hold until gate 1b has built
and measured the comparison
([gate 1 report](../ground_truth/README.md)).

Sources: [compare.py](../src/math_aware_source_digest/compare.py) and the
gate 1 report; the evaluation of existing formula search engines in
`planning/evaluation-existing-work.md` (PR #37, not yet merged; "the
evaluation" below) and the discussion with the user of 2026-10-18.

## 1. What the comparison is for

Two uses, with one comparison:

1. **Two readings of one printed equation** (plan.md stage 5, step 3): a
   converter against a transcriber, or one judge against another (gate 1's
   merge). The question: do they mean the same to a mathematical reader?
   Here a difference in print is an error of one reading, so the comparison
   must not merge two notations that print differently.
2. **A caller's equation against a paper's equation** (outputs.md task 5):
   written from memory, in the caller's notation. The question: is it the
   same up to a consistent renaming of symbols, and what differs beyond it?
   Here different notations for one thing (`f'` and `\frac{df}{dx}`) should
   match, with the difference noted.

The two uses need different strictness, so the proposal has two layers.

## 2. What exists

- **A narrow LaTeX, by tokens:**
  [compare.py](../src/math_aware_source_digest/compare.py) normalizes both
  readings (spacing, sizing, display environments, delimiters of matrices,
  primes, `:=`, the order of a subscript and a superscript) and compares the
  tokens, at two levels: *strict* (the symbols differ) and *style* (only
  bold, calligraphic, upright and the like differ; the style level is
  dropped as a decision, section 5). Its cases are in
  [test_compare.py](../tests/test_compare.py). Gate 1's merge uses it.
- **Gate 1's disagreements under it:** 78 pairs of the 669 merged equations,
  in four kinds (gate 1 report): notation that means the same (`\ldots` and
  `\cdots`, `\leqq` and `\leq`, the 1908 multiplication point as `\cdot` or
  `.`, `\lambda_{\max}` and `\lambda_{max}`), layout (a brace grouping
  several lines, kept or left out), pairing (unnumbered equations shifted on
  a page), and different readings (`f(x_i)` against `f(x_1)`).
- **What the formula search engines show** (the evaluation, section 3):
  operator trees give commutativity and both sides of `=`; layout trees are
  more robust to parse; the two together do better than either alone
  (Tangent-S); operator-tree parsing fails on real LaTeX, sometimes silently
  (ARQMath). No published parse rate covers display equations of research
  papers.

## 3. The proposal: two layers

### 3.1 Layer 1, the narrow LaTeX as a layout tree

The narrow LaTeX keeps its purpose; what changes is how it is computed:
from a **parse tree of the layout**, not from a token stream (decided: lark,
section 5).

- **Parser:** a grammar of layout (groups, scripts, `\frac`, `\sqrt`,
  `\left…\right`, matrix environments, accents, font commands), with no
  decisions about meaning. Chosen: lark (MIT), whose LALR(1) parser is
  "incredibly fast and requires very little memory", and whose Earley parser
  can return "the set of all possible parse-trees (using
  ambiguity='explicit')" ([lark docs](https://lark-parser.readthedocs.io/en/stable/parsers.html)).
  Approach0's MIT grammar is a reference for the coverage of research LaTeX
  (the evaluation, section 3).
- **Rules:** one rewrite of the tree per rule of the narrow LaTeX, each a
  small function (or an entry of a table of patterns, to be decided), each
  with plan.md's two tests: one that the two forms merge, one that a
  look-alike does not.
- **Printer:** writes each tree in exactly one way. Its output is the narrow
  LaTeX; equal output means equal at layer 1. There are two outcomes, the
  same or different. A difference of font (bold, calligraphic, blackboard,
  upright against italic) is a difference like any other: there is no
  *style* level and no separate label.
- **Where the rules fall:**

  | rule | where |
  |---|---|
  | spacing, sizing (`\,`, `\quad`, `\big`, `\left`/`\right`) | the grammar drops them |
  | `:=` and `\coloneqq` | the grammar: two spellings of one token |
  | order of a subscript and a superscript | free: the tree has one slot for each; the printer has one order |
  | primes (`x'`, `x^\prime`) | a rewrite |
  | environments (`pmatrix` and `\left(\begin{array}`) | a rewrite |
  | `\ldots`/`\cdots`, `\leqq`/`\leq`, `\cdot`/`.`, an upright label against italic letters (gate 1) | not merged: strict (decided, section 5) |

- **Parse failures** are explicit (lark raises an error); the comparison then
  falls back to today's token comparison and records the failure. The share
  of equations parsed is reported (gate 1b's criterion).
- **compare.py's cases** become the regression tests of layer 1: every pair
  that the token comparison settles must be settled the same way by the tree.
- **Author macros** are expanded before parsing (stage 3 already does so for
  exact sources).

### 3.2 Layer 2, the operator tree

**Deferred to task 5** (decided, section 5): gate 1b builds layer 1 only.
What follows is the design that task 5 starts from.

An operator tree says what applies to what. It is built from layer 1's tree
by a second pass that decides meaning, with the paper's context: its
definitions and the entry's notation map (plan.md stage 5 already notes
that print does not fix meaning: `f(x)`, `x^{(j)}`, `|A|`, `x'`).

- **Used first** where both sides parse; **layer 1 is the fallback**
  (Tangent-S's approach).
- **Commutativity by operator and by type:** `+` always; `=` in both
  orientations; a product only of scalars (never `Ax` against `xA`, the
  error found in Approach0); never `<` (the evaluation, section 3).
- **For use 1** (two readings), layer 2 is stricter than meaning in a
  computer algebra system: it never rearranges (`(x+1)^2` is not
  `x^2+2x+1`), so a reading that differs in print still differs.
- **For use 2** (the caller), layer 2 is where different notations meet, and
  where the matcher of outputs.md task 5 works (the evaluation, section 3:
  typed one-to-one maps of symbols, edit distance after renaming).

### 3.3 Worked example: derivatives

The narrow LaTeX has one way to write each *printed notation* of a
derivative, not one notation for all derivatives:

| tier | examples | layer |
|---|---|---|
| spellings of one printed form | `f'`, `f^\prime`, `f^{\prime}`; `\frac`, `\dfrac`, `\tfrac`; spacing inside `\frac{d f}{d x}`; `\partial_x`, `\partial_{x}` | merged at layer 1 |
| upright or italic d | `\mathrm{d}x`, `dx` | different at layer 1 (upright against italic is strict, decided); one node at layer 2 |
| different notations | `f'(x)`, `\frac{df}{dx}`, `\frac{d}{dx}f`, `Df`; `\dot{x}`, `\frac{dx}{dt}`; `\partial_x f`, `\frac{\partial f}{\partial x}`, `f_x` | different at layer 1; one node at layer 2, roughly `diff(f, x)` |

Print often cannot decide: `x'` may be a new variable, `f_x` an index,
`\dot{x}` not a time derivative. Layer 2 then records the alternatives
(section 4) and the comparison answers "unsure" unless the paper's context
decides.

### 3.4 What "the same" means across the layers

With two layers, an operator tree that can hold alternatives, and a local
model behind them, no single test is "the" equivalence. Two things are kept
apart:

- **One target per use.** Use 1 (two readings of one printed equation): the
  same meaning as the printed equation for a mathematical reader, not the
  same characters (plan.md section 1a); the ground truth of gate 1 rests on
  it. Use 2 (the caller's equation): the same up to a consistent renaming of
  symbols (outputs.md). These are the definitions; they do not change from
  layer to layer.
- **Several tests that approximate the target.** Each layer, and the local
  model, answers "same", "different" or "unsure" about the target, with a
  measured error rate. Each must be **sound**: when it says "same", the
  target holds. Layer 1 merges only what is safe, layer 2 merges more, the
  model takes what both leave open. Each one's rate of false "same" is
  measured against the ground truth (layer 1 at gate 1b; the model at gates
  2 and 6; layer 2 with task 5); equivalence is not redefined per layer.

So a comparison does not return yes or no. It returns **the strongest
relation it established**, from a list ordered from the strictest; each
relation implies the one after it (decided as the draft for task 5,
section 5). "Different" and "unsure" are outcomes, not relations.

| relation | established by |
|---|---|
| identical | equal narrow LaTeX |
| same meaning | layer 2, with no alternative left open (section 4) |
| same up to renaming | layer 2, with a one-to-one typed map of symbols |
| same structure, with differences | the edit script that remains after renaming |
| different | none of the above |
| unsure | an alternative left open, or a layer that cannot decide |

At gate 1b, with layer 1 only, use 1 accepts "identical" and sends every
other pair to adjudication; with layer 2 (task 5), use 1 would accept "same
meaning". Use 2 accepts "same up to renaming" and reports what lies beyond
it as corrections.

**Alternatives.** Where an `alt` node is not decided by the paper's
context, the two trees are compared under every combination of readings that
the context allows:

- equal under **every** combination: the relation holds;
- equal under **some**: *unsure*;
- equal under **none**: the relation does not hold.

So an ambiguity that is not resolved can never produce a false "same", only
an "unsure": in use 1 it goes to adjudication, in use 2 it is reported to the
caller. The cost is combinatorial when several alternatives are open in one
equation; how often that happens is measured with task 5, when layer 2
is built.

## 4. The format of the operator tree

**Proposed:** Strict Content MathML (equivalently OpenMath), with one
symbol of our own for alternatives, and a JSON form for storage. Not a new
language.

What the standards already give (MathML 3):

- Strict Content MathML "is designed to be compatible with OpenMath", and
  "OpenMath CDs are the preferred source of external definitions": a symbol
  is named by its content dictionary (`<csymbol cd="arith1">plus</csymbol>`)
  ([MathML 3, §4.1.3, §4.2.3.1](https://www.w3.org/TR/MathML3/chapter4.html)).
- **Types of symbols:** `ci` has a `type` attribute; in Strict Content
  MathML its values are "integer", "rational", "real", "complex",
  "complex-polar", "complex-cartesian", "constant", "function", "vector",
  "list", "set" and "matrix" (§4.2.2.1). Commutativity by type (section 3.2)
  can read it.
- **Links to the layout:** "Parallel Markup via Cross-References":
  "MathML supports cross-references between the branches of a semantics
  element to identify corresponding sub-structures"
  ([MathML 3, §5.4.2](https://www.w3.org/TR/MathML3/chapter5.html)). Ours
  link each node to a span of the LaTeX instead, so that corrections can be
  written in the caller's own notation (outputs.md).

What is missing:

- **Alternative meanings.** `semantics` attaches annotations (other
  encodings) to one expression (§4.2.8, §5.4.2); nothing read in MathML 3
  says "this is either an application or a product". An `apply` makes one
  reading explicit (§4.2.5.1), but only one.
- **Proposal:** a content dictionary of our own with one symbol, `alt`,
  whose arguments are the possible readings, each with what would decide it
  (a definition in the paper, a symbol's type). OpenMath lets anyone define
  a content dictionary: one of its four statuses is "`private`: used by a
  private group of OpenMath users"
  ([OpenMath 2.0, §4.2.1](https://openmath.org/standard/om20-2019-07-01/omstd20.html)),
  so a tree with `alt` is still well formed. How trees with alternatives
  are compared is in section 3.4. The alternatives
  are discrete, not weighted. Representing several parses is not new (lark's
  Earley parser returns all parse trees; parsers call this a parse forest);
  keeping the ambiguity in the meaning layer, labelled with what decides it,
  is the part to design.
- **JSON:** OpenMath's standard encodings are XML and binary; a JSON
  encoding exists only as a proposal (Kohlhase and Wiesing, CICM workshops
  2018, CEUR-WS vol. 2307,
  [record](https://cris.fau.de/publications/213997304)). We would store our
  own JSON form, close to that proposal, and write Strict Content MathML for
  cross-checks with LaTeXML (public domain; its Content MathML is not
  trusted, the evaluation, section 3).

## 5. Decisions (the user, 2026-10-18)

1. **Layer 1 only for gate 1b.** Comparing two readings of one printed
   equation needs the layout tree; layer 2's merges (`f'` with `df/dx`,
   `a+b` with `b+a`) are what use 1 must not make. The operator tree
   (sections 3.2 and 4) is built with task 5, on top of layer 1.
2. **lark for layer 1:** a layout grammar, one rewrite per rule, a printer;
   compare.py's token comparison is the fallback on a parse failure, and its
   cases become regression tests. Downloading lark needs the user's approval.
3. **Gate 1's notation pairs are all strict,** not merged: `\ldots` against
   `\cdots`; `\leqq` against `\leq` (some papers use ≦ for componentwise
   order); `\cdot` against `.` (in 1908 type a point between digits may be a
   decimal); an upright label against italic letters (`\lambda_{\max}`,
   `F_{\mathrm{CSM}}`). Upright against italic is strict everywhere,
   `\mathrm{d}` against `d` included. Adjudication reads the page.
4. **The style level is dropped as a decision.** Two readings are the same
   in the narrow LaTeX or they differ, and every difference is adjudicated,
   in the ground truth and in the pipeline. A difference of font is not
   tracked separately either: compare.py's style level goes. (So gate 1's 3
   pairs that differ in font only are adjudicated like the rest.)
5. **The local equivalence model is not used for the ground truth.** It
   stays in the pipeline's design (plan.md stage 5, step 3.2); its rate of
   false "equivalent" is measured when local models are chosen, at gates 2
   and 6. Gate 1b downloads no model.
6. **The relations of section 3.4** (without "same up to style") are kept as
   the draft for task 5, to be revisited when its matcher is designed.

Decided during the build (2026-10-18 and 19; section 8 has the evidence):

7. **The target is LaTeX with amsmath, followed throughout.** Two readings
   are the same when LaTeX with amsmath prints them the same, apart from
   spacing and sizing: `\dots` is set as amsmath sets it (centred before a
   binary operator or relation, on the baseline otherwise); a math alphabet
   (`\mathbf`, `\mathrm`) changes only Latin letters, digits and Greek
   capitals, so `\mathbf{\alpha}` prints `\alpha`; `\mid` and `|` are one
   glyph; `\not=` is `\neq`.
8. **The packages of the target:** amsmath, amssymb, mathrsfs (`\mathscr`),
   upgreek (upright lowercase Greek), dsfont (`\mathds{1}`), and stmaryrd for
   `\llbracket` and `\rrbracket` only. The judges are told to use these and
   nothing else (judge prompt version 2 and later), and layer 1 reads exactly
   these.
9. **Lines, with grouping apart.** A reading is compared line by line; a line
   break is printed layout, so `a = b \\ c = d` and `a = b \quad c = d`
   differ. Readers give one entry per printed line (matrices and cases stay
   whole), with `continues` (the line continues the equation before it) and
   `braced` (a brace joins it to the line before) as fields of their own
   (judge prompt version 3). The merge pairs lines, numbered lines by
   number and the rest in order, and accepts a line that one reader wrote as
   several only when the several join up to it exactly; line breaks,
   grouping and braces are recorded apart from the symbols.
10. **Punctuation at the end of a line is not compared,** as at the end of a
    display; readers write all punctuation as printed (version 4).
11. **Run-to-run variation: unanimity, not votes.** All readings of a paper
    are pooled; a line goes to adjudication if any reading of it differs or
    any reader marked it uncertain. A majority vote is not used: on
    Hestenes–Stiefel it would have chosen the wrong reading of (11:8).
12. **Judge prompt version 4:** all punctuation as printed; the glyphs that
    readers confuse named (≦/≤, ‖/||, upright/italic, dot height, prime,
    1/i/l, comma/full stop), to be decided from the page and marked uncertain
    when not clear; one form for dots in a matrix; grey page images scaled to
    a 2000 px long edge (the most that a request of more than 20 images
    allows).
13. **Adjudication sees more than the page at 150 dpi:** the page as four
    overlapping 300 dpi tiles, and a question that names the parts that
    differ.

**Deferred to task 5's design:** where the types of symbols come from (the
paper's definitions, the notation map, a local model, or the caller); the
table of operators by type (which commute, which associate, which relations
have a reverse); and whether the operator tree is part of the entry or a
comparison key only (plan.md stage 5 asks this; the record stays the
printed-form LaTeX of section 1a meanwhile).

## 6. What remains for gate 1b

From plan.md 6.3, the gate 1 report ("What gate 1b does with it") and the
decisions above:

1. **A measurement plan** for layer 1: section 7. Done: accepted
   2026-10-18.
2. **Build layer 1 and measure it.** Built (branch `feature/layer1`);
   development and frozen runs done (section 8). The held-out paper is run
   once the rules are final.
3. **Judge prompt version 4:** pilot on Hestenes–Stiefel (running), then all
   seven papers, approved before it starts (about US$5).
4. **The user accepts layer 1** from the numbers.
5. **Adjudication** of every line that the pooled readings do not settle
   (decision 11): one Opus call each, with the page as 300 dpi tiles and a
   focused question (decision 13); only a high-confidence verdict settles
   one. This is a billed run, approved before it starts.
6. **The user settles the rest and accepts the merged lists:** gate 1b
   closes, and the ground truth is complete for gates 2 and 3.

The pairing of unnumbered equations and the brace of Smith et al., which
were waiting on gate 1b, are settled by decision 9: lines pair in order and
by content, and a brace is recorded as grouping.

## 7. Measurement plan for layer 1 (accepted 2026-10-18)

What gate 1b measures before the user accepts layer 1 (section 6, step 3).
Nothing here is adjudicated or sent to a model; it runs offline on committed
data.

### 7.1 Data

- **The gate 1 pairs:** the two judges' readings of the 7 papers of the
  judged set, paired by `merge.py` (669 merged equations: 591 agreed by
  compare.py, 64 strict, 3 style, 11 found by one judge only). All seven
  papers are in the public domain or under CC BY (testdata/papers.toml),
  so pairs derived from them may be committed with their attribution.
- **Planted pairs,** made by program from the agreed readings, with a fixed
  seed and committed as a list (each pair: the paper, the equation, the
  change, the two LaTeX strings), so that anyone can rerun them. A change
  is applied only where the equation has what it changes (a γ to swap, a
  product to reverse); at most 20 pairs per kind of change and per paper,
  sampled with the seed; a pair whose two strings are equal is discarded:
  - **differences**, which layer 1 must call *different*, one change per
    pair:
    - look-alike letters: γ and y, ν and v, φ and ϕ, ε and ϵ, ι and i, ω
      and w, κ and k, 𝒲 and 𝒱 (the swaps the design's pilots found are
      among these; only their kinds are used, since the pilot papers are
      copyrighted);
    - accents: tilde, hat, bar, check, dot, one for another, or dropped;
    - fonts: bold and plain, calligraphic and roman, blackboard and roman,
      upright and italic (decided: each is a difference);
    - indices: `i` and `1`, `k` and `K`, `i` and `j`, a subscript moved to a
      superscript;
    - signs and relations: `+` and `-`, `=` and `\leq`, `\leq` and `<`,
      `\leq` and `\leqq`;
    - gate 1's notation pairs: `\ldots` and `\cdots`, `\cdot` and `.`, an
      upright label and italic letters (decided: strict);
    - structure: a dropped term, a dropped prime, the order of a product
      reversed (`AB`, `BA`), the two sides of `=` exchanged (different at
      layer 1: use 1 compares print);
  - **equivalent rewrites**, which layer 1 must call *the same*, one rule per
    pair: `x'` and `x^\prime`; the order of a subscript and a superscript;
    `(` and `\left(`; spacing commands added; `\frac`, `\dfrac`,
    `\tfrac`; `:=` and `\coloneqq`; `pmatrix` and `\left(\begin{array}`;
    redundant braces (`x^{2}`, `x^2`).
- **compare.py's cases** (`test_compare.py`): every case keeps its expected
  outcome, except that the style level becomes *different* (decided).

### 7.2 Development and freezing

Plan.md section 6.1: the normalization is developed on one paper, frozen,
then run on the others, with one paper held out until the end.
**Proposed:** develop on Smith, Schmidt and McGee (1962: 105 equations,
letterpress matrices); hold out Blumenthal et al. (2026: 13 equations,
born-digital); run the frozen version on the other five, then on the held-out
paper. Planted pairs are made from every paper, but the rules are fixed
before the planted pairs of the five and of the held-out paper are run.

### 7.3 Measures

1. **Soundness:** the number of planted differences that layer 1 calls *the
   same*, per kind of change and per paper.
2. **Rule coverage:** the number of planted equivalent rewrites that layer 1
   calls *different*.
3. **Agreement with compare.py** on the 669 gate 1 pairs: each pair whose
   outcome changes, and why. Expected changes: the 3 style pairs become
   *different*; any other change is read by hand and is either a bug or a
   proposed rule, decided by the user.
4. **Parse rate:** the share of readings (both judges, all papers) that the
   grammar parses, per paper and per form (scan, born-digital); each failure
   with the construct that caused it. A failure falls back to compare.py's
   tokens.
5. **Left for adjudication:** the number of gate 1 disagreements after
   layer 1, per paper and per kind (the four kinds of the gate 1 report).
6. **Time** per comparison.

### 7.4 What passes (proposed)

- **Soundness: no planted difference called the same.** A single one is a
  defect to fix, not a rate to accept: layer 1 must be sound (section 3.4).
  Each one is read by hand first, since a change can happen to be
  equivalent (reversing a product of two equal factors).
- **Rule coverage: every planted equivalent rewrite called the same,** since
  each is a rule with its own test.
- **Agreement with compare.py:** every change explained, and accepted by the
  user.
- **Parse rate:** reported, with no threshold, since a failure falls back to
  the tokens; a construct that fails 5 or more readings is fixed before the
  freeze.

### 7.5 What it does not measure

- A misreading that both judges share: their readings agree, so no
  comparison sees it (gate 1 report, "Agreement is not correctness").
- Meaning beyond layout (layer 2, task 5) and the local model (gates 2 and
  6).
- Errors of the planted kinds that the list leaves out; the list grows as
  gates 2 and 3 find new kinds.

### 7.6 Where it goes

- A script, `tests/judging/layer1_measure.py` (name to be fixed in the
  build), with the seed and the lark version pinned in `uv.lock`.
- The planted pairs and the results under `ground_truth/gate1b/`, and a
  section "Gate 1b" in the gate 1 report.
- `merge.py` loses its "style" status with the style level.

## 8. What the build and the pilots found (2026-10-18 and 19)

**Layer 1** (measured with `tests/judging/layer1_measure.py` on branch
`feature/layer1`; results under `ground_truth/gate1b/`):

- Every reading of the six papers run so far parses (1,301 readings); no
  planted pair of those papers is judged wrongly (planted differences called
  the same: 0; planted rewrites called different: 0).
- Against the token comparison it replaces, the changes are all ones the
  rules intend: `\dots` set as amsmath sets it (in Hestenes–Stiefel 19 pairs
  that the old alias merged now differ, as dot heights the page shows, and
  15 pairs now agree); `\lambda_{\max}` against `\lambda_{\mathrm{max}}`
  (both upright: the same); a comma inside a cases row and a superscript set
  after a subscript (`K_{10}{}^{2}`), which the old comparison hid.
- The rules changed after the freeze, each time by a decision or a defect
  found: the amsmath `\dots` rule and the amsmath rules generally
  (decisions 7 and 8), an empty group as a barrier to scripts, line breaks
  and braces (decision 9), and punctuation at the end of a line (decision
  10). The five frozen papers are therefore no longer a blind test of these
  rules; the held-out paper still is.
- Pairing by line: in Smith et al. the disagreements left for adjudication
  fall from 14 to 3, the rest being braces and grouping, recorded apart.

**Judge prompts, piloted on Hestenes–Stiefel** (two judges per version;
branch `feature/judge-prompt-v4`):

| between the two judges | v1 | v2 | v3 |
|---|---|---|---|
| dot disagreements | 29 | 0 | 1 |
| other symbol disagreements | 6 | 9 | 8 |
| font disagreements | 0 | 3 | 1 |
| lines found by one judge only | 4 | 0 | 0 |
| grouping differences | – | 4 | 0 |

- **Run-to-run variation.** Over the four readings of versions 2 and 3, 18
  of 424 lines differ: hard glyphs (≦/≤, ‖/||, upright/italic, dot height)
  10, readings (a prime, `x_i`/`x_1`, `p_i`/`p_j`, `c`/`d`) 4, dots in sparse
  matrices 3, a line missing 1. Only 7 of the 18 were marked uncertain.
- **A shared misreading.** In (11:8a, b, d) the page prints an upright A;
  five of six readings write it italic (checked against the page image).
  Two agreeing readings are not enough on hard glyphs; this is why decision
  11 pools all readings with unanimity, and why decision 13 gives the
  adjudicator more resolution.

