# Design note: how two readings of an equation are compared (gate 1b)

Status: **draft for discussion**, started 2026-10-18. This is the design note
that plan.md stage 5 (step 3, "A meaning representation") asks for before
gate 1b evaluates anything, and the "note on layers and comparison" that
outputs.md names. Everything below is **proposed, not decided**; the
decisions are the user's, and go into plan.md stage 5 and section 10 (open
decision 9) when made. It changes no data: the adjudication of gate 1 stays
on hold until gate 1b has chosen the comparison
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
  bold, calligraphic, upright and the like differ). Its cases are in
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

The narrow LaTeX keeps its purpose and its two levels; what changes is how it
is computed: from a **parse tree of the layout**, not from a token stream.

- **Parser:** a grammar of layout (groups, scripts, `\frac`, `\sqrt`,
  `\left…\right`, matrix environments, accents, font commands), with no
  decisions about meaning. Candidate: lark (MIT), whose LALR(1) parser is
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
  LaTeX; equal output means equal at layer 1.
- **Where the rules fall:**

  | rule | where |
  |---|---|
  | spacing, sizing (`\,`, `\quad`, `\big`, `\left`/`\right`) | the grammar drops them |
  | `:=` and `\coloneqq` | the grammar: two spellings of one token |
  | order of a subscript and a superscript | free: the tree has one slot for each; the printer has one order |
  | primes (`x'`, `x^\prime`) | a rewrite |
  | environments (`pmatrix` and `\left(\begin{array}`) | a rewrite |
  | `\ldots`/`\cdots`, `\leqq`/`\leq` (gate 1) | candidates: each would be a rewrite, decided by the user one by one |

- **Parse failures** are explicit (lark raises an error); the comparison then
  falls back to today's token comparison and records the failure. The share
  of equations parsed is reported (gate 1b's criterion).
- **compare.py's cases** become the regression tests of layer 1: every pair
  that the token comparison settles must be settled the same way by the tree.
- **Author macros** are expanded before parsing (stage 3 already does so for
  exact sources).

### 3.2 Layer 2, the operator tree

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
| upright or italic d | `\mathrm{d}x`, `dx` | merged at layer 1, reported as *style* (a house convention, plan.md 6.1) |
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
  model takes what both leave open. Gate 1b measures each one's rate of
  false "same" against the ground truth; it does not redefine equivalence
  per layer.

So a comparison does not return yes or no. It returns **every relation
it established**, from a list ordered from the strictest. The order is
partial: "same up to style" and "same meaning" do not imply each other (a
bold vector against a plain letter may differ in meaning; `f'` against
`\frac{df}{dx}` differs in print), so both are reported when both hold.
From "same meaning" down, each relation implies the one after it, as
far as "same structure, with differences"; "different" and "unsure" are
outcomes, not relations.

| relation | established by |
|---|---|
| identical | equal narrow LaTeX at the strict level |
| same up to style | layer 1, style level (bold, calligraphic, upright) |
| same meaning | layer 2, with no alternative left open (section 4) |
| same up to renaming | layer 2, with a one-to-one typed map of symbols |
| same structure, with differences | the edit script that remains after renaming |
| different | none of the above |
| unsure | an alternative left open, or a layer that cannot decide |

Use 1 requires "same meaning" and reports style separately (stage 5's two
levels). Use 2 accepts "same up to renaming" and reports what lies beyond it
as corrections.

**Alternatives.** Where an `alt` node is not decided by the paper's
context, the two trees are compared under every combination of readings that
the context allows:

- equal under **every** combination: the relation holds;
- equal under **some**: *unsure*;
- equal under **none**: the relation does not hold.

So an ambiguity that is not resolved can never produce a false "same", only
an "unsure": in use 1 it goes to adjudication, in use 2 it is reported to the
caller. The cost is combinatorial when several alternatives are open in one
equation; how often that happens is measured at gate 1b.

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

## 5. Open questions for the user

1. **Two layers as above,** or layer 1 only for now (use 1 only), with
   layer 2 deferred to when task 5 is built?
2. **lark for layer 1,** replacing compare.py's token rules (kept as
   regression tests), or extend the token rules?
3. **The rules from gate 1's disagreements:** for each of `\ldots`/`\cdots`,
   `\leqq`/`\leq`, `\cdot`/`.` (1908), `\max`/`max`: merge at layer 1, report
   as *style*, or leave strict?
4. **Where types come from** for layer 2: the paper's definitions, the
   notation map of the entry, a local model, or the caller's declaration
   (for use 2)?
5. **The table of operators by type:** which commute, which associate, which
   relations have a reverse (`<` and `>`).
6. **Is the operator tree part of the entry,** or a comparison key only
   (plan.md stage 5 asks this)? The record stays the printed-form LaTeX of
   section 1a unless the user decides otherwise.
7. **The local equivalence model** (stage 5, step 3.2) for what neither
   layer settles: kept as planned, with its rate of false "equivalent"
   measured.
8. **The relations of section 3.4:** is the ordered list right, and does
   use 1 require "same meaning" only, or "same up to style" for symbols in a
   cited result (plan.md stage 5 adjudicates a style difference there)?

## 6. What remains for gate 1b

From plan.md 6.3 and the gate 1 report ("What gate 1b does with it"):

1. **This note,** refined with the user, and the decisions of section 5 (eight questions).
2. **Build the chosen comparison** and measure it on the gate 1 judgements
   (669 merged equations) and on look-alike swaps (from the pilots and
   planted): its coverage (the share parsed into trees, per layer), and for
   each layer and the model its rate of false "same" (soundness, section
   3.4) and its share of "unsure".
3. **The user chooses the comparison** from those numbers.
4. **Adjudication** of the gate 1 disagreements that the chosen comparison
   does not settle: one Opus call each with the whole page image
   (`merge.py <key> --adjudicate`); only a high-confidence verdict settles
   one. This is a billed run, approved before it starts.
5. **The user settles the rest and accepts the merged lists:** gate 1b
   closes, and the ground truth is complete for gates 2 and 3.

Also waiting on gate 1b, and decided with the user: the pairing of
unnumbered equations (about 9 shifted pairs in Student, 3 in
Hestenes–Stiefel), which would pair by similarity under the chosen
comparison instead of by order on the page; and the brace of Smith et al.
that groups several lines under one number (about 11), a question of what
counts as one equation, not of comparison.
