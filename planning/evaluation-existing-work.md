# Design note: existing work to reuse before building

**Status, 2026-10-19: a record, superseded in part.** The conclusions held:
the comparison was built, not reused (layer 1 on lark), and neither
PaperQA2 nor Approach0's code was adopted. Superseded: the advice for gate
1b (section 3, answer 6: both trees, the operator tree first). The user
decided that gate 1b builds the layout tree only, and the operator tree is
deferred to task 5 (`planning/comparison.md`, decision 1). Of the step-2
tests (section 5), lark was adopted for layer 1 rather than for the
matcher, and the PaperQA2 baseline was not run.

Written 2026-10-18 as step 1 of the evaluation that
[outputs.md](outputs.md) section 8 asks for (PR #36, now merged): a desk
review, by reading only. Nothing was cloned, installed or downloaded; web pages and the papers'
PDFs were read through a web fetch. Step 2, a hands-on test, needs the user's
approval for each download (section 5).

Every factual claim links to its source, read on 2026-10-18. **Unverified**
marks what could not be confirmed from the project's own pages. Inferences
drawn from reading source code are marked as such; they are what step 2
would confirm.

## 1. Summary

| project | licence | fits | recommendation |
|---|---|---|---|
| PaperQA2 (`paper-qa` 2026.8.12) | Apache-2.0; its PyMuPDF reader is AGPL-3.0 | a dense passage index at page-range resolution; no equations, no sections, no labels | **build** our own small index; borrow a model-free sparse baseline, and MMR only if candidates repeat; no dependency |
| Approach0 (`search-engine`, `pya0`) | MIT (`pya0`: only a PyPI classifier) | an operator-tree LaTeX parser; ranking, not a symbol correspondence | **build** the matcher; read Approach0's MIT grammar as a reference; optional parse-rate comparison in step 2 |
| Tangent-3 / Tangent-S | CC BY-NC 3.0 | consistent unification, SLT and OPT together | **ideas only** (the licence excludes the code) |
| Tangent-CFT, Tangent-L | AGPL-3.0; not found | embedding or BM25 ranking only | not used |
| MathWebSearch | GPL-3.0 | returns qvar bindings, exact unification only | not a component; at most an exact-match oracle in a test (not proposed for step 2) |

Neither project replaces a task of outputs.md section 4. Each changes how a
task is specified (section 4 of this note).

## 2. PaperQA2

### What it is

A library and agent for question answering over a folder of documents: it
parses and chunks the documents, embeds the chunks, retrieves passages, has a
language model summarize and score each passage, and writes a cited answer
([README](https://github.com/Future-House/paper-qa)). Version read: tag
`v2026.08.12` (commit `57e89f7`), which is also the newest PyPI release
([tags](https://github.com/Future-House/paper-qa/tags),
[PyPI](https://pypi.org/pypi/paper-qa/2026.8.12/json)).

### Answers to the questions

**1. Licence.** `paper-qa` is Apache-2.0
([pyproject.toml](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/pyproject.toml)).
The readers are separate packages in the same repository
([packages/](https://github.com/Future-House/paper-qa/tree/v2026.08.12/packages)):

- `paper-qa-pypdf`: Apache-2.0, on pypdf (BSD-3-Clause); its `media` extra
  adds pypdfium2
  ([pyproject](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/packages/paper-qa-pypdf/pyproject.toml),
  [pypdf](https://pypi.org/pypi/pypdf/json));
- `paper-qa-pymupdf`: **AGPL-3.0**, on PyMuPDF
  ([pyproject](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/packages/paper-qa-pymupdf/pyproject.toml));
- `paper-qa-docling` and `paper-qa-nemotron`: Apache-2.0
  ([docling](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/packages/paper-qa-docling/pyproject.toml),
  [nemotron](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/packages/paper-qa-nemotron/pyproject.toml)).

Its main dependencies are permissive: `fhlmi` and `fhaviary` Apache-2.0
([fhlmi](https://pypi.org/pypi/fhlmi/json),
[fhaviary](https://pypi.org/pypi/fhaviary/json)), `litellm` MIT
([PyPI](https://pypi.org/pypi/litellm/1.84.1/json)), `tantivy` MIT
([PyPI](https://pypi.org/pypi/tantivy/json)).

**2. Fully local.** Possible, but every default points to the cloud and has
to be overridden.

- The settings are `llm`, `summary_llm`, `agent.agent_llm`,
  `parsing.enrichment_llm` (each with a `*_config`) and `embedding`
  ([settings.py](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/src/paperqa/settings.py)).
  The language models default to GPT-4o and the embedding to OpenAI's
  `text-embedding-3-small` (same file).
- The README documents Ollama through LiteLLM (`ollama/llama3.2` with
  `api_base` `http://localhost:11434`, embedding `ollama/mxbai-embed-large`),
  llama.cpp as an OpenAI-compatible server, and local sentence-transformers
  embeddings with the prefix `st-` after `pip install paper-qa[local]`
  ([README](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/README.md)).
  The README's Ollama example sets `llm` and `summary_llm` but not
  `agent_llm` or `enrichment_llm`, which would stay GPT-4o (inference from
  the README and settings.py).
- **Images go to the cloud by default:** `parsing.multimodal` defaults to
  `ON_WITH_ENRICHMENT`, which sends images and tables to the enrichment model
  for captions (settings.py).
- **Metadata lookups by default:** `parsing.use_doc_details` defaults to
  `True` and queries Crossref and Semantic Scholar
  ([clients/\_\_init\_\_.py](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/src/paperqa/clients/__init__.py),
  settings.py). `Docs.aadd` also asks the language model for a citation from
  the first pages when no `citation` is passed
  ([docs.py](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/src/paperqa/docs.py)).
- LiteLLM fetches its model cost map from GitHub unless
  `LITELLM_LOCAL_MODEL_COST_MAP=True`
  ([LiteLLM docs](https://docs.litellm.ai/docs/proxy/custom_model_cost_map));
  it documents a telemetry switch, `litellm.telemetry`
  ([docs](https://docs.litellm.ai/docs/observability/telemetry)).
  **Unverified:** whether telemetry is on by default in the pinned version,
  and whether `fhlmi` makes other network calls.

**3. Retrieval without an answer.** Yes.
`Docs.retrieve_texts(query, k, settings, embedding_model, partitioning_fn)`
embeds the query and runs a maximal-marginal-relevance (MMR) search over
the chunks; it calls no language model and returns `list[Text]` **without
scores** ([docs.py](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/src/paperqa/docs.py)).
MMR picks results one at a time, each by its similarity to the query
minus a penalty for its similarity to the results already picked, weighted
by λ, so that the top results are not near-copies of each other
([Carbonell and Goldstein, SIGIR 1998](https://doi.org/10.1145/290941.291025)).
With `texts_index_mmr_lambda` at its default of 1.0 the penalty is zero and
this is plain similarity search (settings.py). `Docs.aadd_texts(texts, doc, ...)` takes chunks
already made, so our own discovery could supply the units (docs.py). The
agent's full-text index (tantivy) matches whole documents, not passages
([agents/search.py](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/src/paperqa/agents/search.py)).
`get_evidence` uses the summary model; whether `answer.evidence_skip_summary`
removes every model call is **unverified**.

**4. Locations.** Pages only, and only inside a string. `Text` has the
fields `text`, `name`, `media` and `doc`; no page, section, offset or box
([types.py](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/src/paperqa/types.py)).
For a PDF, `name` is `"{docname} pages {lower}-{upper}"`
([readers.py](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/src/paperqa/readers.py)).
No reader records headings; the docling reader does not use docling's
section headers
([docling reader](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/packages/paper-qa-docling/src/paperqa_docling/reader.py)).
Chunks are 5000 characters with 250 of overlap and cross page boundaries
(settings.py, readers.py): one to two pages, much larger than a theorem.

**5. PDF parser. Flag:** `get_default_pdf_parser()` imports
`paperqa_pymupdf` (AGPL) **first** and falls back to `paperqa_pypdf` only if
that import fails (settings.py). The required dependency is
`paper-qa-pypdf` (pyproject.toml), so PyMuPDF is the default only when it is
installed, but then silently. A user would set
`parsing.parse_pdf` to the pypdf reader explicitly. The pypdf reader takes
the text layer with `page.extract_text()`; pypdfium2 renders images only
([pypdf reader](https://raw.githubusercontent.com/Future-House/paper-qa/v2026.08.12/packages/paper-qa-pypdf/src/paperqa_pypdf/reader.py)).
Alternatives: docling and nemotron-parse
([README](https://github.com/Future-House/paper-qa)); nemotron-parse runs
only through NVIDIA's hosted API or AWS SageMaker
([package](https://github.com/Future-House/paper-qa/tree/v2026.08.12/packages/paper-qa-nemotron)),
so it is excluded here.

**6. Mathematics.** The text layer only. The pypdf reader has no OCR and no
formula handling (pypdf reader). The docling reader keeps a formula's text
and an image of it, not LaTeX (docling reader); whether docling's formula
enrichment can be switched on through `custom_pipeline_options` is
**unverified**. "Math equations" in the README's list of modalities means
images with optional captions from a model (README, settings.py). As
expected: prose and labels, never equations.

**7. Maintenance and weight.** CalVer releases; seven tags in 2026, the last
2026-08-12 ([tags](https://github.com/Future-House/paper-qa/tags)). Since
2026-03-20 the commits are two by people and the rest by a dependency bot
([commits](https://github.com/Future-House/paper-qa/commits/main)). 133 open
issues, 22 open pull requests
([repository](https://github.com/Future-House/paper-qa)). That FutureHouse
founded Edison Scientific as a company in November 2025 is reported by the
press
([AIwire](https://dev.aiwire.net/2025/11/07/futurehouse-spins-out-edison-scientific-launches-kosmos-ai-for-research/))
but **unverified** on FutureHouse's own pages (its
[announcements](https://www.futurehouse.org/research-announcements) do not
mention it); the repository is still under Future-House, and its README does
not name Edison. Python ≥ 3.11.
Runtime dependencies include `fhlmi`, which pins
`litellm>=1.83.9,<=1.84.1` and brings `openai`, `coredis` and
`limits[async-redis]` ([fhlmi](https://pypi.org/pypi/fhlmi/json),
[paper-qa](https://pypi.org/pypi/paper-qa/2026.8.12/json)). That pin is
below the fix for advisory
[GHSA-3cv6-jpf6-8222](https://github.com/advisories/GHSA-3cv6-jpf6-8222)
(LiteLLM's proxy server; we would not run the proxy). The wheels of
`litellm` (16.7 MB) and `tantivy` (8.2 MB) alone are 50 times the size of
`paper-qa` itself (0.5 MB) (PyPI pages above).

**8. Which of our tasks.**

- *Discovery's text index:* no. Discovery must list display equations,
  numbered results, definitions and sections with their locations; PaperQA2
  keeps no sections or labels and reads no equations. Its chunks could index
  prose, at page-range resolution.
- *Alignment:* the embedding step only, and only if we give it our own units
  through `aadd_texts`. The label-and-number step comes first in
  outputs.md and is deterministic; PaperQA2 does not do it. Its retrieval
  returns no scores, which an "unsure" answer (open question c) needs.
- *Not at all:* equations, verification against the page, comparison,
  corrections, the cap and the budget.

What would remain after removing its language-model parts is an embedding
store with MMR over chunks: about as much code to configure safely as to
write, and with a heavier dependency tree than our own.

### Risks

1. Silent cloud calls: five defaults (three models, the enrichment of
   images, the metadata clients) each send text or images out unless
   overridden; one forgotten setting breaks the rule "no text of a source
   leaves the machine".
2. AGPL by accident: installing `paper-qa-pymupdf` (directly or through an
   extra) makes PyMuPDF the parser.
3. A pinned LiteLLM below a security fix, and maintenance that has slowed.
4. Coarse locations, without sections and without scores.

### Recommendation: build

Write the alignment index ourselves: one unit per item of discovery (a
numbered result, a definition, a section's paragraphs), each with its page,
section and label; embeddings from a small local model through
sentence-transformers (a dependency we would need anyway); cosine similarity
with scores. Borrow two ideas: MMR, and a model-free sparse
embedding as a baseline (`lmi`'s `SparseEmbeddingModel`, hashed tokens
([embeddings.py](https://raw.githubusercontent.com/Future-House/ldp/main/packages/lmi/src/lmi/embeddings.py)))
— in our case BM25 over the same units. Apache-2.0 allows copying a function
with its notice if one is worth copying.

MMR is a small gain for us. PaperQA2 needs it more, because its chunks
overlap and the top hits can be one passage twice. Our units are the items
of discovery (a theorem, a definition, a section), which barely overlap. MMR
would matter only if alignment returns several candidate locations (open
question c), to keep them distinct (a theorem and its restatement in a later
section, rather than two pieces of one paragraph). It is a few lines; add it
only if the alignment test of step 2 shows repeated candidates.

Step 2 is only worth it as a baseline: does PaperQA2, configured fully
local, find the right page more often than our units? It is optional
(section 5).

## 3. Approach0 and its relatives

### Approach0

**What it is:** formula search on operator trees (OPT) by leaf-to-root
paths, with a structure score and a symbol score
([Zhong and Zanibbi, ECIR 2019](https://www.cs.rit.edu/~dprl/assets/files/Approach0_ECIR2019.pdf)).

**1. Licence, language, build, maintenance.** `search-engine`: MIT
([LICENSE](https://raw.githubusercontent.com/approach0/search-engine/master/LICENSE)),
C with a Bison grammar and a Flex lexer
([tex-parser/](https://github.com/approach0/search-engine/tree/master/tex-parser)).
Its README says the master branch is inactive and that the newest code is
closed source ([README](https://github.com/approach0/search-engine)); last
commit on master 2020-12-12
([commits](https://github.com/approach0/search-engine/commits/master)).
`pya0`, the Python binding: last commit 2023-11-04
([commits](https://github.com/approach0/pya0/commits/master)); no LICENSE
file in the repository ([tree](https://github.com/approach0/pya0/tree/master));
PyPI gives no licence field but the classifier "MIT License", and its only
wheel is `manylinux_2_24_x86_64`, 19.7 MB, version 0.3.7 of 2023-04-17
([PyPI](https://pypi.org/pypi/pya0/json)). **No macOS wheel**; it builds in a
manylinux Docker image with flex, bison, OpenMPI, libxml2 and Indri
([README](https://raw.githubusercontent.com/approach0/pya0/master/README.md)).

**2. Input.** LaTeX, through its own grammar of "roughly 100 grammar rules
and 50 token types" (ECIR 2019, footnote 2). From reading the grammar and
lexer
([grammar.y](https://raw.githubusercontent.com/approach0/search-engine/master/tex-parser/grammar.y),
[lexer](https://raw.githubusercontent.com/approach0/search-engine/master/tex-parser/lexer.template.l)):
fractions, roots, scripts, a matrix environment, `\left`/`\right` and
`\operatorname`; `\text`, `\mbox`, `\label` and `\tag` are skipped and
unknown commands dropped. `pya0` exposes the parser alone:
`do_parsing(latex)` returns a status and the tree, each node with its token,
symbol and character span
([parser.py.c](https://raw.githubusercontent.com/approach0/pya0/master/parser.py.c)).
The index is on disk (`index_open(path, ...)`), and a small index in a
temporary directory works in its tests
([indexer.py.c](https://raw.githubusercontent.com/approach0/pya0/master/indexer.py.c),
[test-index.py](https://raw.githubusercontent.com/approach0/pya0/master/tests/test-index.py));
how well it ranks on tens of equations is **unverified**.

**3. Symbol correspondence.** Ranking only. Leaves are tokenized to their
type (variables to `VAR`) "to allow results from unification/substitution",
and the symbol score comes from the Mark-and-Cross algorithm, which "scores
exact symbol matches higher than unified symbol matches" (ECIR 2019, §3.2).
In
[mnc-score.c](https://raw.githubusercontent.com/approach0/search-engine/master/search/mnc-score.c)
(inference from the code, master of 2020): query symbols are paired with
document symbols one group of identical query symbols at a time, greedily by
score; a document symbol is not reserved for one query symbol, so the
mapping need not be one-to-one; `mnc_score()` returns only a number, and the
pairing is printed only in a debug build. The search returns a score, a
document and an expression ID
([math-expr-search.c](https://raw.githubusercontent.com/approach0/search-engine/master/search/math-expr-search.c)).
Wildcards exist (`\qvar{x}` in grammar.y).

**4. Hard cases** (from grammar.y and the lexer, inference): `+`, implicit
multiplication and the relations are all marked commutative; the lexer tags
`=`, `<`, `>` and `\le` with `WC_COMMUT_OPERATOR`, even under its own
comment "non-commutative gt/lt/eq". So `a=b` matches `b=a` and `a+b`
matches `b+a`, but also `Ax` matches `xA` (wrong for matrices) and `a<b`
matches `b<a` (wrong; `a<b` and `b>a` do not match, since `<` and `>` stay
different symbols). `a-b` is
`a + (-b)`. Moving terms across `=` and matrix against index notation: not
handled; the paper lists equivalences such as `x^{-1}` and `1/x` as future
work (ECIR 2019). Its authors write that a parse failure "would end up zero
recall" and that their OPT parser is "less robust … than SLT parser"
([CLEF 2021 notes](https://par.nsf.gov/servlets/purl/10339390)), and in 2022
they rewrote 20 queries by hand so that the parser could read them
([CLEF 2022 notes, §4](https://ceur-ws.org/Vol-3180/paper-09.pdf)).

### Tangent-3 and Tangent-S

- **Licence:** Tangent-S is **CC BY-NC 3.0**, last activity 2024-02-18
  ([GitLab API](https://gitlab.com/api/v4/projects/dprl%2Ftangent-s?license=true)).
  Its code cannot go into an MIT package; its ideas can be reused.
- **Build:** Python 3.6 and a C++ index, LaTeXML for input, "tested on
  linux" ([README](https://gitlab.com/dprl/tangent-s/-/raw/matts_cleanup/README.md)).
- **Input:** symbol layout trees (SLT) from Presentation MathML and operator
  trees from Content MathML, both from LaTeX by LaTeXML (README).
- **Consistent renaming:** Tangent-3 requires it: "It is important that the
  substitutions are consistent", found by a greedy unification; wildcards
  with the same name bind the same subtree
  ([NTCIR-12 paper, §3.2.4](https://research.nii.ac.jp/ntcir/workshop/OnlineProceedings12/pdf/ntcir/MathIR/06-NTCIR12-MathIR-DavilaK.pdf)).
  Tangent-S unifies only nodes of similar type (single-character identifiers
  with each other) and aligns a subtree of the candidate to the query
  ([SIGIR 2017, §3.1, §3.3](https://www.cs.rit.edu/~dprl/files/SIGIR_2017_revised.pdf)).
  Whether it outputs the mapping is **unverified**.
- **Hard cases:** in the OPT "we ignore the order of children for
  commutative operators", which "allows us to match x + y= 0 and 0= y + x
  perfectly" (SIGIR 2017, §3.3).
- **SLT and OPT together** score better than either: Bpref 0.5530 combined,
  0.5240 SLT, 0.5127 OPT on NTCIR-12 (SIGIR 2017, §4). The same paper notes
  that in the NTCIR-12 Content MathML "f(x) is almost always converted to
  the tree corresponding to f×x".

### Tangent-CFT and Tangent-L

Tangent-CFT embeds SLT and OPT tuples with fastText and returns one score
per formula; **AGPL-3.0** on GitLab
([API](https://gitlab.com/api/v4/projects/dprl%2FTangentCFT?license=true));
a copy on GitHub shows no licence
([repository](https://github.com/BehroozMansouri/TangentCFT)).
Tangent-L ranks bags of SLT tokens with BM25+ in Lucene
([Waterloo page](https://www.scg.uwaterloo.ca/brushsearch/tangent-l));
its source and licence were not found (**unverified**). Neither gives a
correspondence; neither fits.

### MathWebSearch

- **Licence and build:** GPL-3.0, C++ with CMake, LevelDB and libxml2; a
  Docker image; last commit 2020-12-10 ([repository](https://github.com/KWARC/mws),
  [commits](https://github.com/KWARC/mws/commits/master)).
- **Input:** Content MathML only, in "harvest" files
  ([wiki](https://github.com/KWARC/mws/wiki/MWS-Harvests)).
- **Correspondence:** the only engine reviewed that returns one. Query
  variables (`mws:qvar`) with the same name match the same expression
  ([query wiki](https://github.com/KWARC/mws/wiki/MWSQuery)), and each answer
  lists its bindings, for example `<mws:substpair qvar="x" xpath="1/3/2"/>`
  ([answer-set wiki](https://github.com/KWARC/mws/wiki/MWSAnswerSet)).
- **Limits:** matching is exact unification
  ([NTCIR-11 paper](https://research.nii.ac.jp/ntcir/workshop/OnlineProceedings11/pdf/NTCIR/Math-2/05-NTCIR11-MATH-HambasanR.pdf)),
  so there are no partial matches and no differences to report. Whether two
  query variables may bind the same symbol (injectivity), and any handling
  of commutativity, are **unverified**.

### The shared tasks

- NTCIR-12: "All of the automated systems employ unification"; unification
  of candidates with few matching symbols "appears to hurt precision"
  ([overview, §4](https://www.cs.rit.edu/~rlaz/files/ntcir12-mathir.pdf)).
- ARQMath (formulas from Math StackExchange, converted by LaTeXML 0.8.5):
  in ARQMath-1, 8% of SLTs and 10% of OPTs failed; in ARQMath-2, 0.14%
  ([ARQMath-2 overview, §3](https://ceur-ws.org/Vol-2936/paper-01.pdf)). In
  ARQMath-3 the organizers "found and corrected 65,681 formulae with incorrect
  SLT and OPT representations"
  ([overview, §2](https://www.cs.rit.edu/~rlaz/files/ARQMath_2022_Overview_WorkingNotes.pdf)):
  a conversion that does not fail can still be wrong.
- Approach0 had the best nDCG′ of ARQMath-2's formula task, 13% above the
  Tangent-S baseline (ARQMath-2 overview, §5).
- No published rate of OPT parsing for display equations of research papers
  was found (**unverified gap**). Math StackExchange formulas are short and
  typed by their authors; ours are longer and transcribed or recalled.

### Answers 5 and 6

**5. Best fit.** None fits our task as it is: one query against tens to
about 150 equations, with a consistent and one-to-one renaming, the
correspondence returned, and the differences beyond it. The ideas that fit:

- Tangent-3's consistent unification and Tangent-S's typed unification
  (single-character identifiers with each other);
- Approach0's and Tangent-S's normalization of commutative operators on
  operator trees, restricted by type (not for products of matrices, not for
  `<`);
- MathWebSearch's form of the answer: a binding per query symbol;
- Tangent-S's fallback to the layout tree when the operator tree fails.

The collection is small enough to compare the query with every equation of
the paper, but not to try every map: an equation with 15 symbols has too
many one-to-one maps to enumerate. So, for each candidate equation: propose
maps from aligned leaves (Tangent-3's greedy unification, which gives one
consistent map), refine them by a beam search that keeps the map one-to-one
and typed, score each map by tree edit distance after renaming, and report
the best map and the remaining edit script. Three points the design must
settle, which none of the engines settles for us:

- **What a symbol is.** `x_i` against `x_1` (outputs.md's own example) is
  an index renamed to a constant, not one symbol renamed to another; and
  decorated symbols (`\hat{x}`, `x^{(k)}`, `\mathbf{A}`) are units whose
  decoration carries meaning (plan.md section 1a). The map is over base
  symbols and indices separately, and an index that becomes a constant is a
  difference, not a renaming.
- **Part of an equation.** The caller may remember one side, or one term,
  of a printed equation, or an equation that the paper splits in two.
  Tangent-S aligns a subtree of the candidate with the query; the matcher
  needs the same, and the result says "matches part of eq. (12)".
- **The cap.** The edit script is what leaves the machine; its size is the
  natural measure for the cap (outputs.md open question d), and an edit that
  inserts a whole subtree of the paper's equation is the case the cap
  withholds.

Candidate
building blocks, all permissive: `lark` (MIT, a parser library) for our own
grammar, porting rules from Approach0's MIT `grammar.y`; `apted` (MIT, tree
edit distance on ordered trees) for the score; since edit distance on
unordered trees is NP-complete in general
([Zhang, Statman and Shasha 1992](https://cs.nyu.edu/~shasha/papers/ipl8.pdf)),
the children of a commutative
operator are put in a canonical order first (after renaming, so the order
does not depend on the names), and APTED compares the ordered result
(design inference, to be measured in step 2); SymPy (BSD) only as a checker for
rearrangements ([lark](https://pypi.org/pypi/lark/json),
[apted](https://pypi.org/pypi/apted/json),
[sympy](https://pypi.org/pypi/sympy/json)). SymPy's `parse_latex` is
documented as experimental; its ANTLR backend can silently parse part of an
expression and its Lark backend has no matrices
([docs](https://docs.sympy.org/latest/modules/parsing.html)), so it is not
the parser. LaTeXML is in the public domain
([notices](https://math.nist.gov/~BMiller/LaTeXML/notices.html)) and could
be a second source of operator trees to cross-check, not a trusted one.

**6. Gate 1b.** The evidence argues for **both trees, not a choice**: the
operator tree gives commutativity and both sides of `=` (Approach0,
Tangent-S); the layout tree is the more robust (Approach0's authors, the
ARQMath failure rates); and the two together outperform either alone
(Tangent-S). For gate 1b this means:

- a normalized layout tree (the narrow LaTeX of plan.md stage 5, as a tree)
  always exists, and is the fallback;
- an operator tree is added where the parse succeeds and is used first;
- the parse rate is measured on our own data, the 591 equations on which
  gate 1's judges agreed (the rest wait for the adjudication of gate 1b),
  because no published figure covers research papers;
- an operator tree needs the meaning of symbols (`f(x)`: application or
  product; `Ax`: commutative or not), which plan.md stage 5 already notes;
  the paper's definitions and the notation map are where it comes from.

Matrix against index notation and moving terms across `=` are done by no
engine reviewed; they stay with the model stage, with "unsure" as an
answer, as outputs.md section 7 says.

### Risks

1. Licences: Tangent-S (CC BY-NC) and Tangent-CFT (AGPL) exclude their code;
   MathWebSearch is GPL; `pya0`'s licence rests on a PyPI classifier only.
2. Platform and maintenance: every engine is Linux C or C++, inactive since
   2020–2024; `pya0` has no macOS wheel.
3. Operator-tree parsing fails on real LaTeX, sometimes silently (ARQMath-3).
4. Commutativity applied too widely is a false "matches": exactly the error
   our comparison must not make.

### Recommendation: build, from these ideas

Build the matcher of outputs.md task 5 ourselves, in Python, with the ideas
and permissive components above. Read Approach0's grammar as a reference for
the coverage of research LaTeX. Use no engine's code.

## 4. What changes in outputs.md

Proposed for the outputs.md branch (or the next change to it), not made
here:

- **Section 8, PaperQA2:** "retrieval with locations" becomes "retrieval
  with page ranges in the chunk's name; no sections, labels or scores"; the
  candidate role shrinks to an optional baseline for alignment.
- **Section 4, task 3 (alignment):** the units of the embedding step are the
  items of discovery (results, definitions, sections), not fixed-size
  chunks; the step returns a similarity score, so that open question c
  ("unsure alignment") has something to decide on; a sparse baseline (BM25)
  beside the embedding.
- **Section 4, task 5 (comparison):** "matching up to a consistent renaming"
  is specified as a **one-to-one** map of symbols, typed (a symbol maps to a
  symbol of the same kind; a matrix to a matrix), over base symbols and
  indices separately, found by search; a match may be to part of an
  equation; the minimal corrections are the edit script that remains after
  renaming, and its size is the measure for the cap; commutativity is
  applied by operator and by type.
- **Section 7:** Approach0 and Tangent-S are no longer "to study"; what they
  give is listed in section 3 of this note. The requirement on gate 1b
  becomes both trees, operator tree first, with a measured parse rate.
- **Section 5 (time):** the matcher is deterministic code; a beam search
  over symbol maps against ~150 equations is expected to take seconds
  (**unmeasured**; step 2 measures it).

## 5. Step 2: hands-on tests (each download needs approval)

All tests use only the pinned test papers (testdata/papers.toml) and the
committed gate 1 lists; no copyrighted PDF. Nothing is adjudicated: the
tests measure parse rates and retrieval, not the ground truth (gate 1b
decides the comparison first).

### 5a. Formula parsing and matching (recommended first)

1. A prototype matcher on `lark` and `apted`: parse the 591 equations on
   which both judges agreed
   ([gate 1 report](../ground_truth/README.md)), and count the parses by
   paper (scans and born-digital apart). Then take equations of Hestenes and
   Stiefel (1952, public domain; 298 agreed equations, many of them alike,
   the hard case for telling equations apart) and of Harris and Kleefeld
   (2019, CC BY; 64), apply planted changes (a consistent renaming, an
   inconsistent renaming, an index made a constant, reordered sides, a
   dropped term, one side only), and match each against the whole paper.
   Measures: parse rate; the planted source equation ranked first; the map
   recovered; false "matches up to renaming" (also against the other
   papers' equations); the time per query.
2. Optional comparison: Approach0's parser on the same 591 equations,
   through `pya0` in a Linux x86_64 container (emulated on the M1), for its
   parse rate only.
3. Optional: LaTeXML's Content MathML on the same equations, for its parse
   rate and a sample of its trees checked by hand.

| download | source | version | size | for |
|---|---|---|---|---|
| lark | PyPI | 1.3.1 | 113 KB ([PyPI](https://pypi.org/pypi/lark/json)) | 1 |
| apted | PyPI | 1.0.3 | 41 KB ([PyPI](https://pypi.org/pypi/apted/json)) | 1 |
| sympy (checker for rearrangements) | PyPI | 1.14.0 | 6.3 MB ([PyPI](https://pypi.org/pypi/sympy/json)) | 1, optional |
| pya0 | PyPI | 0.3.7 | 19.7 MB wheel ([PyPI](https://pypi.org/pypi/pya0/json)) | 2 |
| a manylinux x86_64 Python base image, and Docker or a Linux VM if not installed | Docker Hub | to pin | **unknown** | 2 |
| LaTeXML and its Perl dependencies | nixpkgs (pinned) or CPAN | 0.8.8 | 14.6 MB source ([MetaCPAN](https://metacpan.org/dist/LaTeXML)); closure **unknown** | 3 |

`lark` and `apted` are small enough that they could become dependencies of
the package; adding them goes through its own PR.

### 5b. PaperQA2 as an alignment baseline (optional)

Index the three born-digital papers of the judged set (Zach et al. 2023,
Blumenthal et al. 2026, Harris and Kleefeld 2019; all CC BY, with a text
layer, which PaperQA2's pypdf reader needs) with `paper-qa[local]` fully
local: the pypdf reader set explicitly; `multimodal` off;
`use_doc_details` off; `citation` and `docname` passed; embedding
`st-BAAI/bge-small-en-v1.5`, downloaded once with approval and then loaded
with `HF_HUB_OFFLINE=1`; `LITELLM_LOCAL_MODEL_COST_MAP=True`. The run is
without network (a container with networking off, or a sandbox; the method
to be chosen), which also tests that nothing tries to leave the machine.
Query with the gate 1 numbered results (53 items with their locations),
written as a caller would write them; measure how often the right page
comes first, and how often the top candidates repeat one passage (the test
for MMR), against a baseline of our own: the same embedding model on
one unit per page from pypdfium2's text (already a dependency; discovery's
units do not exist yet), and BM25, a few lines of our own code, on the same
units.

| download | source | version | size |
|---|---|---|---|
| paper-qa (with the `local` extra; not `pymupdf`, not `zotero`) | PyPI | 2026.8.12 | 0.5 MB ([PyPI](https://pypi.org/pypi/paper-qa/2026.8.12/json)) |
| paper-qa-pypdf | PyPI | 2026.8.12 | 16 KB ([PyPI](https://pypi.org/pypi/paper-qa-pypdf/json)) |
| litellm (pinned by fhlmi) | PyPI | 1.84.1 | 16.7 MB ([PyPI](https://pypi.org/pypi/litellm/1.84.1/json)) |
| tantivy | PyPI | 0.26.2 | 8.2 MB ([PyPI](https://pypi.org/pypi/tantivy/0.26.2/json)) |
| fhlmi, fhaviary | PyPI | 1.0.7, 0.37.0 | 61 KB, 62 KB ([fhlmi](https://pypi.org/pypi/fhlmi/1.0.7/json), [fhaviary](https://pypi.org/pypi/fhaviary/json)) |
| sentence-transformers | PyPI | 6.1.0 | 0.7 MB ([PyPI](https://pypi.org/pypi/sentence-transformers/6.1.0/json)) |
| torch (macOS arm64) | PyPI | 2.14.1 | 127 MB ([PyPI](https://pypi.org/pypi/torch/2.14.1/json)) |
| transformers, openai, tiktoken and the rest of the tree | PyPI | from the lock | **unknown**; the resolver gives the list before asking |
| BAAI/bge-small-en-v1.5 (MIT) | Hugging Face | to pin by commit | 133 MB ([files](https://huggingface.co/BAAI/bge-small-en-v1.5/tree/main)) |

Known total: about 290 MB, most of it torch and the embedding model, which
our own alignment would need anyway; what PaperQA2 adds is about 26 MB plus
the unknown rest of its tree. Everything runs through `uvx` or a separate
environment, outside the default devShell.

## 6. Not verified

- LiteLLM's telemetry default at 1.84.1, and other network calls of `fhlmi`.
- Whether `evidence_skip_summary` removes every model call from
  `get_evidence`; whether docling's formula enrichment can be enabled.
- Approach0's newer `pya0` code: whether it differs from master's scoring or
  returns the pairing.
- Tangent-S's output of the alignment; MathWebSearch's injectivity and
  commutativity.
- Tangent-L's source and licence.
- Any published operator-tree parse rate for research-paper display
  equations.
- The sizes marked unknown in section 5.
