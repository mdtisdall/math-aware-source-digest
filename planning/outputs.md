# Design note: what the skill outputs

Status: **draft for discussion**, started 2026-10-18. It comes before the
note on layers and comparison (`planning/comparison.md`, not yet
committed): what each layer must achieve follows from what the outputs
promise. Items marked **open** are to be settled with the user; the answers
then go into the plan (sections 1 and 1a).

## 1. Why the outputs change

The plan's entry promises that every *cited* span is exact or marked
unverified, and assumes that drafting decides what to cite. But what a
project will cite is not known when the entry is made, and the reader that
could decide it, Claude in a project, may not read the paper: local first,
no text of a source leaves the machine (plan, section 1). So the digest must
stand in for reading: complete enough on the machine that later questions can
be answered from it, while what goes to Claude stays a summary and short
quotations chosen for a purpose.

## 2. Two commands, one machinery

- **`masd digest <paper>`** (no focus given). Reads the whole paper locally,
  builds the **local digest** (section 3), and writes the **overview entry**
  (section 4).
- **`masd cite <paper> <target>`** (a focus given). The target is an equation
  number, a result label, or a description ("the convergence bound"). Reuses
  the digest, verifies the target against the page, and returns a **cited
  excerpt** (section 5), recorded in the entry. Runs `digest` first if there
  is none.

Both use the same layers and cache (comparison.md, section 3); `cite` is the
plan's stage 5 (verify the cited spans), triggered by a citation instead of
by guessing during drafting.

### How the work is ordered: discovery, then focus

- **Discovery (pass 1), focused on pages.** With no index yet, the first pass
  sweeps the pages in order and finds every display equation, number,
  section, numbered result and definition, with the sentences around them
  (layers 2–3, feed-forward). The index is the output of this pass. The
  gate 1 judges did exactly this.
- **Focus on elements (later passes).** Each element (equation, symbol,
  result) has a priority and the reason for it: a user's target, uncertainty,
  or a link to a focused element. Work goes to the highest priority first,
  and the context given to a model is assembled from the element's
  neighbourhood (the definitions of its symbols, the sentences around it,
  the equations it refers to), not the whole paper.
  - A user's focus (`cite`) puts the target first and spreads along its
    links: the symbols it uses, their definitions, the equations it refers
    to, the assumptions of its result.
  - A sweep of focus over the paper (document order, or most uncertain
    first) lets what is settled for one element improve the others; sweeps
    repeat until a pass changes nothing, or a reported limit.
- **Salience** (for the key results of an overview, with no user focus) comes
  from the paper's own signals: the abstract, the introduction's list of
  contributions, labelled theorems, "our main result", the conclusion, and
  how often an equation or result is referred to.

## 3. The local digest

Complete, on the machine only (in the cache, like the PDF). Every item has a
**status**: *transcribed* (read once), *agreed* (two local readers agree),
*verified* (checked against the page and, where needed, adjudicated), or
*uncertain* (with the candidate readings).

| component | contents | layer |
|---|---|---|
| **Document map** | pages, printed page numbers, sections, the version | 1–3 |
| **Equation index** | every display equation: id, location (page, printed page, position), number, LaTeX as printed, candidates for uncertain parts, the symbols it uses, the equations and results that refer to it, status | 2–3 |
| **Results index** | every numbered result and definition: kind, label, location, statement (as printed), stated assumptions, what it refers to, status | 3 |
| **Notation index** | every symbol: its printed form, meaning (as meant, not as misprinted), kind (variable, function, operator, set, constant), where it is defined, where it is used, the source of the meaning (a definition, usage, convention), status | 4 |
| **Suspected errata** | location, what is printed, what is probably meant, the evidence, confidence | 4–5 |
| **Published errata and retractions** | found from the records (Crossref, the publisher) | 0 |
| **Verification record** | for each item: how it was read and checked, by which tool and model version, and what remains unchecked | all |

**Open:**

- **a.** Inline mathematics (within sentences): indexed too, or only display
  equations?
- **b.** Meaning trees (layer 5, for example OpenMath) for each equation: part
  of the digest, later, or not at all?
- **c.** Dependencies between results (which theorem uses which lemma):
  recorded where the paper states them, or also inferred?

## 4. The overview entry

What Claude in a project reads: the plan's "summary with short quotations",
now built from the digest. JSON with a rendered Markdown file (plan, 1a).

| component | contents |
|---|---|
| **Citation** | each field with its provenance, checked against the first page (unchanged) |
| **Version** | which version the entry describes; numbering between versions |
| **Abstract and key results** | what the paper does; its key results paraphrased, each with its location and stated assumptions |
| **Notation index** | each symbol (short LaTeX) with its meaning and where it is defined |
| **Equation list** | each display equation: number, location, a one-line description (not its LaTeX), status |
| **Results list** | each numbered result and definition: label, location, a one-line paraphrase, status |
| **Suspected errata** | as in the digest |
| **Published errata and retractions** | as in the digest |
| **Cited excerpts** | each excerpt returned so far by `cite` (section 5) |
| **Coverage** | what the digest does not cover (for example inline mathematics, figures, tables), and counts by status |
| **Verification summary** | counts, tools and model versions |

**Open:**

- **d.** The equation list: one-line descriptions only (a description needs a
  local model to understand the equation), or also the LaTeX of short
  equations?
- **e.** How many key results, and paraphrased or quoted?
- **f.** A record of what has been retrieved by `cite` for each paper, with a
  total, so that many retrievals do not quietly add up to much of the paper?

## 5. The cited excerpt

What `cite` returns, and what the entry records under "cited spans".

- the target and how it was resolved (for a description: which elements it
  was matched to, for the user to confirm);
- the exact LaTeX or statement **as printed**, verified against the page
  first, or marked unverified with the reason;
- the symbols it uses, from the notation index;
- the assumptions of the result it belongs to;
- probable misprints in it, with the reading as meant;
- its location and verification record.

**The promise** (replaces the plan's): every excerpt that `cite` returns is
verified against the page, or marked unverified with the reason. The digest
promises completeness of discovery and a status for each item, not that every
item is verified.

## 6. Running on this laptop

The target machine is an M1 Max with 64 GB of unified memory. Measured on it
(plan, section 2): Qwen3-VL 32B writes about 7.6 tokens a second and reads one
equation crop in about 17 s; Marker converts a paper in 5–8 minutes. The
plan's budget is 15 minutes for a typical 20-page paper (plan, section 5a).
Memory holds one 32B model (about 20 GB at 4 bits) at a time, with small
models beside it.

Estimates for a 20-page paper with about 60 display equations (only the
measured figures above are firm):

| component | what runs | estimate | within budget? |
|---|---|---|---|
| discovery (layers 2–3) | Marker; a 0.9B OCR model for a second reading of each equation | 5–8 min; 1–3 min (unmeasured) | yes |
| `cite`: verify one target | a 32B vision model on one crop | 20–60 s | yes |
| notation index (layer 4) | a text model over the paper | 32B: 5–10 min; 7–14B: 2–4 min | probably; quality unknown |
| one-line descriptions | a text model | about 4 min (32B) | probably |
| focus sweeps with feedback, whole paper | about 30 s per equation with a 32B model | about 30 min per sweep | no |
| meaning trees (layer 5), whole paper | the strongest model | hours for 300 equations | no |

Two principles follow (decided 2026-10-18):

- **Anytime.** Work goes in priority order (section 2) until the budget runs
  out; whatever is not reached keeps its status (transcribed, uncertain) and
  is counted in the coverage. `digest` runs discovery, the notation index and
  the descriptions, then as many sweeps as the budget allows, and reports
  how far it got; the user can give a longer budget (for example overnight
  for a reading list). Layer 5 and repeated sweeps run where a focus puts
  them (`cite`), not over whole papers.
- **Narrow tasks for small models.** Each output component is built from
  narrow tasks, each with a bounded input and a constrained output, so that
  small local models can do them:
  - **choice over generation:** "which of these candidate readings matches
    the crop", "does this sentence define `E`, and as what", "given that `k`
    is the index everywhere else and `K` occurs only here, is this a
    misprint: yes, no, unsure";
  - **deterministic code for bookkeeping:** where each symbol is used,
    candidate definitions found by pattern ("let", "denote", "where"),
    cross-references; code is tested and makes no reading errors;
  - **short context from focus:** an element and its neighbourhood, about
    1–2k tokens, not the whole paper;
  - **a cascade:** a small model first; low confidence or disagreement goes
    to a larger one (plan, section 5a);
  - **the smallest model that passes, per task,** measured at the gates.
    Small models' confidence is poorly calibrated, so it is measured on the
    planted-error set for each task, not trusted.
  - Tasks that need the whole paper (the abstract, choosing key results) are
    built from the items' one-line descriptions, or are one call to a
    mid-size model.

**Open:**

- **g.** The biggest uncertainty is quality, not speed: whether small local
  models can build a correct notation index or spot misprints. Measuring it
  needs a layer-4 ground truth for the judged set (the notation of each
  paper), made by judges as in gate 1: test data, a few US$, with the user's
  approval.

## 7. Out of scope

Unchanged from the plan: judging whether a result applies to a project, and
writing to the user's Zotero library.

## 8. What follows for the layers and gates

- Discovery must find every display equation and numbered item (layers 2–3,
  the whole paper): gate 1's ground truth measures it.
- `cite` must verify one item well (layer 2 against the page): gates 2 and 4.
- The notation index needs layer 4 for the whole paper; suspected errata
  need layers 4–5. Measuring them needs a layer-4 ground truth (open g).
- Each narrow task gets its own measure and its smallest passing model
  (gates 2 and 6); the anytime budget is measured at gate 6a.
- The comparison note serves these outputs: equivalence at layer 2 for
  verification and scoring; at layers 4–5 for the notation index and errata.
