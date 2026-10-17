# Plan: a skill that turns research papers into verified, machine-readable source entries

Status: plan, version 4, 2026-10-17. Version 1 was reviewed by an Opus agent (24 findings, 6 high) and checked against a survey of existing tools; version 2 adopted both. Version 3 makes the design local first: every step runs on local models, so no source text leaves the machine, and cloud models are only a fallback if local mode fails a gate (decided 2026-10-17). It also adds ways to make local mode cheaper (section 5a) and the parts of an existing plugin worth reusing (section 11). Version 4 settles the open decisions that blocked the start (section 10: 1, 2, 3, 6) and defines the entry format (section 1a). The remaining open questions are in section 10. Name of the skill: **math-aware-source-digest**, in the public repository `mdtisdall/math-aware-source-digest` (Python package `math_aware_source_digest`, command `masd`). It is a general tool. It was planned in the repository `linear-recon-design-reference` ("the reference" below), which is its first user.

## 1. What the skill does

Given a list of papers or books (DOIs, arXiv IDs, ISBNs, titles, Zotero items, or PDF paths), the skill produces, for each, a **source entry** that an agent can load on its own and trust:

- **citation**: each field with its provenance (Crossref, DataCite, ISBN record), and checked against the first page of the acquired document; never taken from a model's memory;
- **versions**: which version the entry describes (version of record, preprint), and errata or retractions found;
- **content summary**: what the source does, and its main results with their locations (section, theorem, equation, page) in the version that the entry names;
- **notation map**: each symbol that the cited results use, its meaning, and where it is defined;
- **results**: each main result, with the assumptions that the source states for it, quoted or closely paraphrased;
- **cited spans**: every equation, inline formula, result sentence or table cell that the entry relies on, each with an ID, its provenance (which route produced it) and its verification status;
- **coverage**: the source's numbered results, definitions and equations that the entry does not include, listed, so that an omission is visible;
- **a verification record**: what was checked, how, by which tool and model version, and what remains unchecked.

It also produces an **index**: an annotated bibliography with one line for each entry.

**The promise of an entry:** every span that the entry cites is exact or marked as unverified. The skill does not promise that the whole source was transcribed without error; the entry lists what it does not cover.

**Where the text goes: local first.**

- **Local mode is the design.** Every step runs on the machine, including drafting, adjudicating and checking, with local models. No text of the source leaves the machine. Only the finished entry (a summary with short quotations) is later read by Claude, when a project cites it. The gates optimize local mode until it "just works": correct, complete, and within the time budget of section 5a.
- **Cloud mode is a fallback,** built only if local mode fails a gate for some kind of source, and used only for those sources, with the user's approval for each. In cloud mode, drafting, adjudicating and checking run as Claude Code subagents, which receive the converted text.

Each source records its licence (from Unpaywall or the user). **Claude's role during development** is to judge local-mode output, and only on material that may be sent: the three pilot papers (already sent) and openly licensed papers (section 6.1).

**Not in scope:**

- judging whether a result applies to a project (that is the work of the user or of a project agent);
- writing to the user's Zotero library (read-only).

The entry format is configurable, so that a project can match its own template (section 1a).

## 1a. Entry format

Decided 2026-10-17.

- **Two forms of each entry.** The canonical entry is a JSON file, validated against a schema that is part of the package (versioned). The checks (stage 6), the index (stage 7) and any merge read the JSON. A Markdown file, `sources/<key>.md` by default, is rendered from the JSON by a template. To correct an entry, edit the JSON (or run the stage again) and render again; the Markdown is never the source.
- **Fields:** the fields of section 1. The Markdown contains all of them, including the cited spans (ID, exact LaTeX or text, location, route, verification status), so that an agent that loads one file has everything that it needs. The detailed verification log (models, crops, comparison scores, adjudication answers) stays in the cache; the entry gives a summary of it.
- **Notation map:** the source's own symbols only, each with its meaning and where it is defined. The skill does not map them to a project's notation.
- **Project fields are not included.** Fields that judge a source for a project (what the project uses from it, the status of a result in the project, the chapters that use it; section 5 of the reference's plan) are the project's work (section 1, "not in scope"). The skill does not write them, and does not leave slots for them. A project that needs them keeps them in its own files, which link to the entry.
- **Configuration** (a file in the project, with defaults): the output directory (default `sources/`); the key scheme (default: the surname of the first author, or of both authors when there are two, then the year, lower case and ASCII, with a suffix `a`, `b`, … on a collision; for example `kaipio-somersalo-2007`, `seeger-2010`); the Markdown template (default: a template that follows the reference's `sources/<key>.md` without its project fields); the order and headings of the sections; the name of the index (default `sources/README.md`).
- **Where the JSON goes:** next to the Markdown (default `sources/<key>.json`), so that a project can check it and so that later runs can compare against it.

## 2. Evidence so far

Measured on 2026-10-17 with three born-digital journal papers: Seeger et al. 2010 (MRM, 11 pages), Unser 2000 (Proc. IEEE, 19 pages), Adcock et al. 2013 (Inverse Problems, 28 pages). One Opus judge for each output compared it with the page images; the judges' lists are incomplete (section 6.1).

| finding | evidence |
|---|---|
| A PDF's text layer loses mathematics. | Nine extractions from text layers were discarded. |
| Models read page images well, with occasional formula slips and misses. | Haiku: 1–3 harmful errors per paper and the most misses. Sonnet and Opus: 0–1 harmful errors each. Cost: 84k–162k tokens per paper. |
| arXiv LaTeX and PMC XML were exact in the cases tested. | One arXiv source and one PMC article. Pandoc failures on other sources, and PMC articles with mathematics as images, are not yet measured. |
| Some of the candidate papers have an exact form. | Of 26 candidate papers (books excluded): 11 found on arXiv, 2 in PMC, 13 found in neither. These are preprints, not the versions of record. |
| Marker 2.0 (default settings) fails on mathematics. | Harmful display-equation errors: 6/14, 17/71, 56/138. One paper lost all inline mathematics. |
| Marker 2.0 at 288 dpi with full OCR is better, but not enough alone. | Harmful display errors: 4/14, 10/71, 11/136. Seeger and Unser: look-alike swaps (γ/y, φ̃/φ̂). Adcock: dropped terms, changed relations, and 𝒲/𝒱. Inline errors remain: Seeger 27 harmful. |
| A second, local transcription of each display equation flagged Seeger's 4 harmful display errors. | Qwen3-VL 32B instruct (Ollama), 300-dpi crops: 3 flagged by disagreement, 1 because its answer was cut off and could not be parsed. Its readings of the 3 complete answers were correct. One paper only. |
| A vocabulary check and a role check added little. | Every "undefined symbol" flag was ordinary notation. |
| Local models need guards. | A "thinking" model spent its whole budget reasoning. Ollama's default context (262k) took 91 GB on a 64 GB machine. Marker waits forever if its `llama-server` dies. |
| Timing. | One crop: about 30 s. The loop with a per-symbol report: 177 s per equation. Marker at 288 dpi: 5–8 minutes per paper. |

## 3. Architecture

**Division of work.** A Python command-line tool (uv package) does all deterministic and local work: resolving, downloading, converting, cropping, local transcription, comparison, checks. Every model task that needs judgment (drafting, adjudicating, checking) is written as a **request file** (the task, the inputs, the output format, the tier). The **local backend** answers each request: the tool sends it to a local model and writes the answer. The whole pipeline runs without Claude Code, as an unattended job of the command-line tool, and the skill only starts it, monitors it, and reads the results.

The request-file format keeps the door open for the fallback: a **cloud backend** (the skill starts a Claude Code subagent for a request, at its tier, and the tool reads the answer back) can answer the same requests with the same prompts, if a gate shows it is needed. It is not built until then. If it is built, its subagents run with no shell and no network, and may write only their answer file (section 7).

Runs are reproducible from the request and answer files and the manifest; cost is reported as wall time and peak memory.

**Cache.** One content-addressed directory for each source, under a cache root outside any repository: downloads, conversions, crops, transcriptions, requests, answers, and a manifest of tool and model versions and settings. Each stage is skipped if its inputs and settings are unchanged. Before writing this logic, check whether a small runner (for example a make-style or Snakemake-style tool) does it already (section 9, step 3).

**Local servers.** Only one local model server runs at a time (Marker's `llama-server`, or Ollama), started and stopped by the tool. Ollama always runs with `num_ctx` capped, `num_predict` capped, `think: false`, instruct models only, and a JSON schema in `format`. The tool checks that each server started and stays up.

## 4. Stages

### Stage 1: Resolve

- **Primary record:** Crossref for DOIs, DataCite for arXiv DOIs, an ISBN record (Open Library or the Library of Congress) for books, with the edition stated.
- **Open copies and versions:** Unpaywall (only if the user sets a contact email, which it requires) and OpenAlex (a free key raises the daily budget) for open copies with their version (submitted, accepted, published) and licence; Semantic Scholar (batch of up to 500 IDs) and Europe PMC for arXiv and PMC IDs; Europe PMC for open-access full texts. For an arXiv paper, the journal DOI that Semantic Scholar gives is recorded as the version of record (`published_doi`).
- **The user's library:** the Zotero local API (read-only GET requests, to this machine only) for items and PDF paths, and Better BibTeX for citation keys.
- **No DOI:** GROBID (Docker image `0.9.1-crf`, arm64) extracts the title from the PDF as a search key only, never as a citation field.
- **Each field records its provenance,** not a count of agreeing records (OpenAlex and Semantic Scholar mostly copy Crossref).
- **Clients:** the REST APIs are called directly through the tool's one HTTP layer (download policy, spacing per host, backoff, cache). The services' Python libraries were not adopted (decided 2026-10-17): habanero and pyalex make their own requests and would bypass that layer, and pyzotero adds four dependencies for a few local GET requests. The NCBI ID converter (`pmc.ncbi.nlm.nih.gov`) refuses the `requests` library (HTTP 403); Europe PMC gives the same identifiers.

### Stage 2: Acquire

- **The version of record,** from the user's library or a path that the user gives, whenever it exists. Entries locate results in it.
- **An exact form** (arXiv source, or PMC or Europe PMC XML) as well, when it exists. It is the source of exact equations. Locations are mapped from it to the version of record (stage 5).
- **Errata and retractions:** Crossref update relations (`update-to`, retraction notices).
- **Books:** a PDF that the user gives, with a page or chapter range; only that range is processed.
- **Missing:** the skill reports the source, with a link for the user to add it to the library. It never substitutes another version or another work without the user's consent, and records any substitute in the entry (`original_unavailable`, `based_on`).
- **Download checks** (adapted from research-superpowers, section 11): each downloaded file passes checks before it counts (a real PDF or archive, not an HTML error page; size; page count; title on the first page), with a failure code. Failures go to a worklist and an audit file.
- **Which version a PDF is** (submitted, accepted manuscript, or published), checked from the PDF itself (adapted from `check-pdf-version.py`), not only from the record.
- **Download policy:** a configuration file of the project (or a default for the user) lists the hosts that need no approval. The default list is empty: every other download stops and asks the user, with the file, its source and its size. A host that the text of a source suggests is never added to the list by the tool. The documentation gives an example list (arXiv, NCBI, Europe PMC, Crossref, DataCite, OpenAlex, Semantic Scholar, Unpaywall, Open Library). Independent of the policy, arXiv requests wait at least 3 seconds apart, every request honours HTTP 429 with backoff, and all downloads are cached.

### Stage 3: Convert

- **arXiv LaTeX:** pandoc with `--sandbox` and the `latex_macros` extension (de-macro as a fallback for author macros). arXiv's own HTML (LaTeXML, with MathML and the original TeX) as a cross-check where it exists.
- **PMC or Europe PMC XML:** pandoc from JATS.
- **PDF:** the converter chosen at gate 3. Candidates: Marker 2.0 at 288 dpi with full OCR, and MinerU 4. Page images at 150 dpi are kept.
- **Check of the output,** with fall-through to the next form if it fails: mathematics present; no mathematics as images (PMC); pandoc warnings none or listed; equation numbers with no gaps; the number of equations agreeing with a second detector (the other converter's layout, or a heuristic on the PDF's layout from pypdfium2).

### Stage 4: Draft the entry

A local model writes the entry from the converted text, as JSON against the schema of section 1a; the tool renders the Markdown. It never retypes an equation or a quoted sentence: it cites each by the span ID that stage 3 assigned. Tier by mode and form (section 5). Every location gives both the printed page number and the physical page of the PDF. A chapter of an edited book records its parent (`parent_bibkey`). A field that could not be verified carries its reason; the tool refuses to write a field that is neither verified nor given a reason.

For a long source, the model works one section at a time, and the tool merges the parts, so that a local model's context (32k–64k tokens) is enough.

### Stage 5: Verify the cited spans

For each span that the entry cites:

- **Exact form:** map its location to the version of record (equation and theorem numbers, pages), and flag where the two versions differ.
- **PDF route:**
  1. Crop the span from the PDF at 300 dpi (pypdfium2; `pdftoppm` as a cross-check), whether it is a display equation, a line with inline mathematics, a result sentence or a table cell.
  2. Transcribe the crop a second time with the local transcriber chosen at gate 2. Candidates: GLM-OCR (0.9B), PaddleOCR-VL (0.9B), and Qwen3-VL 32B instruct.
  3. Compare the two transcriptions with CDM (it renders both and matches characters), at two levels: **strict** (the rendered symbols differ) and **style** (bold, calligraphic or upright differs). A strict difference is always adjudicated; a style difference is adjudicated when the symbol occurs in a cited result.
  4. Adjudication: a model reads the crop and both transcriptions, and returns the correct LaTeX, its confidence, and whether it chose neither. A local vision model of a different family from both transcribers (for example Qwen3-VL 32B instruct, if the two transcribers are GLM-OCR and PaddleOCR-VL); low confidence leaves the span "unverified".
  5. **Propagation:** when a span had a symbol swap (for example γ read as y), search the nearby spans of the source for the same swap, and verify them too.
- A span that cannot be verified keeps the status "unverified", with the reason.

### Stage 6: Check the entry

- **Automatic checks:** the JSON is valid against the schema, and the Markdown is rendered from it; each citation field matches its record and the first page of the document; each cited span has an ID and a status; each location exists in the version that the entry names; every printed page number lies in the source's printed page range.
- **Coverage check:** the tool lists the source's numbered results, definitions and equations from the converted text; the entry either includes each or lists it under "coverage" as not included.
- **Model check:** a second model compares the summary and the results with the converted text. A local model of a different family from the one that drafted the entry.

### Stage 7: Index

Write the annotated bibliography: one line for each entry, with its key, citation, version, form, licence, and verification status.

## 5. Model tiers

| work | local mode (the design) | cloud fallback (only if a gate fails) |
|---|---|---|
| draft (stage 4) | a local text model, chosen at gate 6 among a mixture-of-experts model (for example Qwen3 30B-A3B) and dense models of about 30B (Qwen3 32B, Gemma 3 27B, Mistral Small) | Sonnet; Haiku for exact forms if as good |
| second transcription (stage 5, PDF route and books) | a local model, chosen at gate 2 | the same (local) |
| adjudication (stage 5) | a local vision model of another family from both transcribers; low confidence stays "unverified" | Sonnet; Opus for low confidence |
| check (stage 6) | a local text model of another family from the drafter | Sonnet; Opus for failures |

As first designed, local mode was estimated at 30–60 minutes per paper. Section 5a lists the ways to cut that, and gate 6a measures them against the budget.

## 5a. Making local mode cheaper

Local compute is the main bottleneck. Measured so far: Marker at 288 dpi took 5–8 minutes per paper; Qwen3-VL 32B wrote about 7.6 tokens per second and took 17 seconds to read one crop; one page of notation took about 2 minutes. Most of the time goes to generating text with a large model, and to reading whole pages. The strategies below attack those costs. Each is adopted only if gate 6a shows that it keeps quality at the levels of gates 2–6.

| strategy | what it saves | expected effect (to be measured) |
|---|---|---|
| **Route first** | Exact forms (arXiv LaTeX, PMC XML) need no OCR and no transcription. | About half the candidate papers skip stages 3 (PDF) and 5 (transcription) entirely. |
| **Verify only cited spans** | Crops only for the spans an entry cites, not for every equation. | Tens of crops per paper instead of 14–136 display equations plus all inline mathematics. |
| **Convert only the pages needed** | Run the expensive PDF converter at high resolution only on pages with cited spans; a fast pass (text layer, or the converter's fast mode) for the rest. | Fewer pages through the slowest step. |
| **Small specialist models first (cascade)** | Second transcription by a 0.9B model (GLM-OCR or PaddleOCR-VL); the 32B vision model only for disagreements. | The 0.9B models are about 35 times smaller; the large model runs only on the few flagged spans. |
| **Mixture-of-experts text models for drafting** | A model such as Qwen3 30B-A3B has the knowledge of a 30B model but computes with about 3B parameters per token. | Generation several times faster than a dense 32B model; quality to be checked against the dense model. |
| **Short outputs** | Ask only for what is used: the LaTeX, or the entry's fields; no per-symbol reports, no free-text reasoning; a JSON schema; capped length. | Generation time is proportional to output length (the per-symbol report took the loop from about 30 s to 177 s per equation). |
| **Prefix caching** | Draft and check an entry section by section with the paper's text as a shared prefix, so that the server reads it once (llama.cpp and MLX keep the prompt cache). | Prefill of a 20k–40k-token paper paid once, not once per request. |
| **A faster backend** | MLX (`mlx-lm`, `mlx-vlm`) runs natively on Apple Silicon; compare with Ollama and `llama-server`. | Often faster than llama.cpp on Apple Silicon (to be measured on this machine). |
| **Speculative decoding** | A small draft model proposes tokens that the large model checks in one step (llama.cpp and MLX support it). | Typically 1.5–2 times faster generation, with identical output. |
| **Quantization and context** | Q4 against Q5 or Q8 weights; quantized key-value cache; the smallest context that fits each request. | Less memory and faster reading; the quality cost of each choice is measured. |
| **Crop resolution** | The lowest resolution at which the transcriber still reads accents and subscripts correctly. | Fewer image tokens per crop. |
| **Keep models loaded, one at a time** | Stages grouped so that each model loads once per batch of papers, not once per paper. | No repeated loading of 20 GB models. |

**Budget.** The target for local mode on this machine (M1 Max, 64 GB): a typical 20-page paper on the PDF route in at most 15 minutes, and an exact-form paper in at most 5 minutes, unattended, at the quality of gate 6. Gate 6a reports where the time goes if the target is not met.

## 6. Testing

### 6.1 Ground truth

- **Judged set:** the three pilot papers and one **scanned** paper (to be chosen; older statistics papers are likely scanned). For each, a second Opus judge reads the page images; the lists of all judges are merged, and their disagreements are resolved once (by Opus, then by the user for what remains). This merged list is the ground truth. It includes omissions, not only errors.
- **Automatic set:** the arXiv-mathematics tests of olmOCR-Bench, with its KaTeX checker (ground truth ready; published scores for Marker 1.10.1).
- **LaTeX set:** arXiv papers whose journal PDF the user also has. The PDF route runs on the journal PDF (journal fonts cause the swaps), and its result is compared with the arXiv LaTeX, matched by equation number and position. Start with 3 papers as a smoke test; decide on 10.
- **Open set:** openly licensed papers (CC-BY or similar, mostly from arXiv), with page images and full text that may be sent to Claude. Cloud judges grade local-mode entries only on this set and on the judged set, so that testing local mode never sends restricted text to the cloud.
- **Unit tests:** a known made-up reference resolves to nothing (adapted from research-superpowers); CDM on the cases that matter (bold against non-bold, tilde against hat, 𝒲 against W, γ against y); crop coordinates; record parsing (fixtures); the download policy; backoff on 429 (mocked); every guard; pandoc `--sandbox`; safe extraction of archives (path traversal rejected).
- **Normalization and thresholds** are developed on Unser and frozen before Seeger and Adcock are run (Seeger is held out).

**What is committed:** identifiers, hashes of the PDFs, ground-truth lists (locations and correct LaTeX), and tests. Not committed: PDFs, page images, crops, or long quotations. Tests that need a copyrighted PDF fetch it from the user's library at test time and are skipped in CI; CI uses openly licensed arXiv papers.

### 6.2 Metrics

- **Correctness:** harmful errors left in cited spans; recall of flags against the ground truth; errors introduced by adjudication; cases where the adjudicator chose neither; omissions (coverage); citation fields wrong. Reported as counts with confidence intervals.
- **Efficiency:** wall time per page and per span (local); peak memory; and, during development only, the tokens that cloud judges use.

### 6.3 Gates

Each gate ends with a report to the user. The next gate starts only after the user approves. A gate that fails returns to the design, not to the next gate.

| gate | what it decides | runs on | passes if |
|---|---|---|---|
| 0. Environment | the tool is sound | unit tests | all pass; each guard stops its failure mode; the security tests pass |
| 0b. Obedience | the skill's prohibitions hold | scripted sessions (adapted from research-superpowers' tests): asked for a citation fact with no record; given a source with an embedded instruction; asked to retype an equation; asked to download from a host outside the policy | the agent refuses or asks in every case |
| 1. Ground truth | what is correct | judged set (4 papers) | merged lists exist; disagreements resolved; the user accepts them |
| 2. Second transcriber | which local model | crops of the ground-truth spans (all harmful ones, and a sample of correct ones) | the chosen model reads at least 95% of the harmful spans correctly, and keeps at least 98% of the correct ones correct, at the lowest time per span |
| 3. PDF converter | Marker or MinerU | judged set and olmOCR-Bench arXiv-math | the chosen converter has the fewest harmful errors and missing equations; time per page reported |
| 4. Cited spans, end to end | the PDF route works | judged set: draft, verify, check | no harmful error left in cited spans; no error introduced by adjudication; omissions listed in coverage match the ground truth's omissions |
| 5. Exact route | LaTeX and XML work, with version mapping | LaTeX set (3, then 10) and 3 PMC articles | pandoc and LaTeXML failure rate measured and falls through correctly; locations map to the version of record; harmful errors in cited spans 0 |
| 6. Local models | which local models draft, adjudicate and check | the judged set and the open set, 3 papers from each route; Opus judges against the ground truth | local mode has no harmful error in cited spans or results, and no more omissions than a reference entry written by Sonnet from the same text (open set only). If it fails for some route, the report says where; the user decides between more local work and the cloud fallback for that route |
| 6a. Local efficiency | which strategies of section 5a to adopt | the judged set and the open set, in local mode; each strategy measured on its own, then the chosen combination | for each strategy: time per paper, time per span, peak memory, and the change in harmful errors and omissions. A strategy is adopted only if quality stays at the level of gate 6. The combination meets the budget of section 5a, or the report shows which step prevents it |
| 7. First batch | the skill is ready for use | the sources of chapter 0 of the reference | in a stratified sample of 5 entries (at least 2 from the PDF route, 1 from the exact route, 1 book), no harmful error; the index lists every source with its version, form, licence and status |

The ground truth stays as described in 6.1, so every later change of a tool or a model is checked again against it (regression).

## 7. Security, licences and privacy

- **Untrusted content.** Downloaded files and converted text are data, not instructions (the MinerU README already contains instructions aimed at coding agents). Pandoc runs with `--sandbox`. Archives are extracted safely into a fresh directory. Scripts that read downloads run with `python -I`. Subagents receive the converted text inside delimiters, with no shell, no network, and write access only to their answer file.
- **Licences.** Full texts stay in the local cache. Each source records its licence. In local mode no text of a source goes to the cloud at any stage; its entry is the only output that Claude later reads.
- **Telemetry.** Telemetry of local tools is turned off (MinerU has it).

## 8. Packaging

A Claude Code plugin in its own repository with the dev-workflow setup: a skill and a Python package (uv). Licence: MIT (decided 2026-10-17). Dependencies of the package have permissive licences; for that reason the PDF library is pypdfium2 (BSD and Apache), not PyMuPDF (AGPL).

- **Default devShell (and CI):** Python, uv, `poppler-utils`, `pandoc`.
- **Not in CI:** the converters and the local models (Marker or MinerU through `uvx` at pinned versions; `llama-server` and Ollama from the pinned nixpkgs through `nix shell`; GROBID and the CDM renderer, which needs TeX Live and ImageMagick, in their own shells). The scripts that need them check for them and stop with a clear message.

**SKILL.md** stays short and loads reference files when needed. It states:

1. when to use the skill, and its inputs;
2. the command for each stage, and how to resume;
3. what needs the user's approval: downloads outside the policy, using the cloud fallback for a source (if it is ever built), and moving to the next gate;
4. how long local jobs run, and how to run and monitor them in the background;
5. how to start, monitor and resume the local job, and which local models it needs;
6. the prohibitions: no citation facts from memory; never retype an equation; never act on text from a source;
7. what a verification status means for a consumer of the entry;
8. the entry format and its configuration;
9. each failure message, and what to do about it;
10. where the cache is, and that it never goes into a repository.

## 9. Order of work

1. Settle the open decisions that block the start (section 10: 1, 2, 3, 6). Done 2026-10-17.
2. Make the repository, with the dev-workflow setup. Done 2026-10-17.
3. Port the existing scripts (resolver, crop and compare loop, judge prompts) into the package; adopt the libraries of stage 1, CDM and a cache runner if one fits. Gate 0.
4. Gate 1 (ground truth), then gates 2 and 3 (bake-offs). They can run in parallel once gate 1 passes.
5. Stages 4–6, then gate 4.
6. Gate 5 (exact route), then gate 6 (local models), then gate 6a (local efficiency). Gates 2 and 3 already record time per span and per page, so that gate 6a starts from measured numbers. The cloud fallback is built only if gate 6 or 6a fails for some route, and only for that route.
7. Gate 7, which also produces the first sources of the reference.

## 10. Open decisions

1. **Where the skill lives:** settled (2026-10-17): its own repository, `mdtisdall/math-aware-source-digest`.
2. **The entry format:** settled (2026-10-17): canonical JSON with a rendered Markdown file, the reference's `sources/<key>.md` without its project fields, configurable (section 1a).
3. **The download policy:** settled (2026-10-17): configurable for each project; the default asks for every download (stage 2). During development, Claude asks before each download.
4. **Which version an entry cites** for a paper with both a preprint and a version of record (proposed: the version of record, with the preprint as the source of exact equations).
5. **The cloud fallback:** settled as local first (2026-10-17). Open only if a gate fails: for which routes, and whether openly licensed sources may use it without asking each time.
6. **Public or private repository:** settled (2026-10-17): public. Only identifiers, hashes, ground-truth error lists and openly licensed test material are committed (section 6.1).
7. **Books:** does the user have PDFs (often scanned) of the books, and should the skill process page ranges?
8. **A second judge for each paper of the ground truth:** about 120k–230k tokens per paper; needed for gate 1.

## 11. Prior art: research-superpowers

[research-superpowers](https://github.com/leiverkus/research-superpowers) (MIT licence, one maintainer, last change 2026-09-13) is a Claude Code plugin for a whole research workflow around a Markdown wiki, for the humanities. It acquires sources and writes a page for each, but it does not convert PDFs (the model reads the PDF), does not handle mathematics, and does not check quotations or page numbers against the document. Its "verified" citations are rendered from search records, not compared with the document.

**Adopted here** (code copied keeps its MIT copyright notice): the checks of downloaded files with failure codes, the worklist and the audit (stage 2); the check of which version a PDF is (stage 2); the schema fields `based_on`, `original_unavailable` and `parent_bibkey` (stages 2 and 4); printed and physical page numbers, and the check of the printed page range (stages 4 and 6); refusing to write an unverified field without a reason (stage 4); the test that a made-up reference resolves to nothing (section 6.1); tests of obedience to the skill's prohibitions (gate 0b).

**Not adopted:** its SessionStart hook (it runs Python from the current directory at every start, with no prompt); automatic downloads without a policy; syncing the library to cloud storage; rewriting PDFs in place; instructions that rank the skill above the system prompt.

**Out of scope here, possible for a later skill that uses these entries:** literature search, project-specific "focus" blocks, entities and a knowledge graph.
