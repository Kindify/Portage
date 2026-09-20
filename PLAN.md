# Plan

## Where things stand

**Phase 0 and Phase 1 are complete and released** - `v0.1.0` and `v0.2.0`.
**Phase 2 is in progress: step 1 of 4 is done.**

Start here, then read `CLAUDE.md`. Where this file and CLAUDE.md differ,
**CLAUDE.md governs**, with four amendments Matt adopted on 2026-09-20, recorded
in `docs/decisions.md` and summarised under Phase 2 below.

### What exists

| | |
|---|---|
| `portage.sqlite` | built by `python -m portage.build` in about a minute |
| Phase 0 | 49,032 provision records, ITA and ITR, both languages, consolidation 2026-06-18 |
| Phase 1 | 229 tax expenditure measures per language, 774 references, 6,440 cost cells |
| tests | 105, `pytest` |
| catalogues | 18, each diffed against a committed fixture in `tests/fixtures/` |
| hand checks | 40 provision spot checks + 60 reference checks, all recorded |

### The documents, and what each is for

| file | what it carries |
|---|---|
| `CLAUDE.md` | the brief and the non-negotiables. Governs. |
| `PLAN.md` | where the work stands and what is next. This file. |
| `docs/decisions.md` | every decision, dated, with the reasoning. 40+ entries. |
| `docs/source-notes.md` | what the real source data looks like, checked not assumed |
| `docs/citation-path-rule.md` | how a provision becomes a citation path |
| `docs/reference-rule.md` | how a reference resolves - Part 1 tagged, Part 2 the report |
| `docs/indicator-definitions.md` | **Phase 2 step 1 output**: every view, its meaning, its null rules |
| `tests/spot_checks/` | the hand-verification samples and their results |

### Three rules that have been earned the hard way

1. **Position is never a join key.** Six times the shortcut looked right and was
   wrong. Each bilingual edition is ordered alphabetically in its own language.
2. **A test that shares code with the thing it tests proves nothing.** The first
   round-trip passed while the database was missing text, because parser and
   check had the same blind spot.
3. **Hand checks find what tests cannot.** Both times a sample was checked by a
   person it found something. Every automated test reads the same grammar that
   produced the data.

## Phase 0 - the Act and Regulations - COMPLETE, released v0.1.0

`portage.sqlite`, built by `python -m portage.build` on a laptop in about
25 seconds.

| | |
|---|---|
| Income Tax Act | 37,136 rows |
| Income Tax Regulations | 11,896 rows |
| total | 49,032 rows, 41,817 addressable |
| sections | 763 (Act) + 499 (Regulations) |
| consolidation date | 2026-06-18, from `lims:pit-date` |
| citation path collisions | 0 |
| round trip, all four files | exact, **zero normalisation** |
| FTS5 | English and French, both instruments |

**Five catalogues**, written on every build and diffed line-by-line against
committed fixtures in `tests/fixtures/`: `label_anomalies.csv`,
`definition_key_fallbacks.csv`, `definition_join_suspects.csv`,
`bilingual_gaps.csv`, `alignment_unverified.csv`.

**Four spot-check files** for hand verification - `tests/spot_checks_ita_en.md`,
`_ita_fr.md`, `_itr_en.md`, `_itr_fr.md` - twenty citations each, seeded so they
stay stable between builds.

---

### Released

`v0.1.0` at <https://github.com/Kindify/Portage/releases/tag/v0.1.0>, with the
database, the catalogues, the README and the hand-verification results. The tag
was held until the eighty spot checks were done: a tag means checked, not built.

---

## Phase 1 - tax expenditures linked to the Act - COMPLETE, released v0.2.0

Rules, table definitions and acceptance tests are in `CLAUDE.md`. This is the
sequencing and the things to settle first.

### Step 1 - tagged cross-references - **DONE**

`cross_references` and `definition_ref_candidates` are built, every row
`method = 'tagged'`. 74 tests pass. The rule is in `docs/reference-rule.md`,
written before it was implemented.

| kind | rows | unique | ambiguous | unresolved |
|---|---|---|---|---|
| `XRefExternal` | 2,837 | 0 | 0 | 2,837 |
| `DefinitionRef` | 2,526 | 950 (37.6%) | 1,207 (47.8%) | 369 (14.6%) |
| `XRefInternal` | 1 | 0 | 0 | 1 |
| **total** | **5,364** | **950** | **1,207** | **3,207** |

`definition_ref_candidates`: 10,459 rows - 3,888 same-instrument definition
records, 4,187 same-instrument inline sites, 2,384 other-instrument. 400
distinct terms are defined more than once; "person" is defined in 15 places.

**Three findings that shape the rest of Phase 1:**

1. **The source tags no provision-to-provision references.** One `XRefInternal`
   in the whole corpus. The reference graph does not exist in the source and
   must be built by pattern extraction.
2. **That one `XRefInternal` is now a grammar fixture.** Its text is `51`, in
   the Act, in an element called "internal", and section 51 of the Act exists -
   every markup signal says resolve it. Only the prose says it means section 51
   of a different Act. **A bare section number with no instrument qualifier
   never resolves.**
3. **Ambiguity is the normal case.** 1,207 references name a term defined in
   several places. The report's measure references will behave the same way:
   record the candidates, never choose.

### Step 2 - inspect the report - **DONE**

Written up in `docs/source-notes.md` section 7. Retrieved 2026-09-19. No parser
written.

**Format: clean HTML.** Each measure is one `<table>`, one row per field. Not a
PDF extraction job.

**229 measures in each language**, cross-checked two ways (counting tables, and
counting the Part 3 index links).

**Seven findings that change how step 4 must be written:**

1. **The editions paginate differently.** Part 4 holds 49 measures in English
   and **99** in French; Part 5 holds 70 and 28. Measures are alphabetical
   within each language. The part number is provenance, never a join key.
2. **`caption[id]` does not identify a measure.** The Part 7 appendix table has
   no caption id in English but does in French, with 17 body rows - it passes
   every shape test. **A measure is a table the Part 3 index links to.**
3. **17 fields on every measure in both languages**, no exceptions. But the
   **French labels vary**: 25 distinct labels for 17 fields on Part 4 alone -
   non-breaking spaces, different wording (`Thème`/`Objet`,
   `régime`/`système fiscal`), and two measures labelling the *Tax* field
   `Direction de la politique de l'impôt`, which is not a field name.
   **Every variant sits at a fixed row position**, so key on position, map the
   labels, and never key on label text.
4. **A measure has zero, one or two cost tables.** Three measures on Part 6 have
   two. Measures with none are the "no estimate" cases - including the CLAUDE.md
   fixture *Deferral for asset transfers to a corporation*, which confirms it.
5. **Finance publishes the symbol legend**, in the metadata CSV on
   open.canada.ca: `n.a.`/`n.d.` = no data, `–` = not in effect, `X` = withheld
   for confidentiality, `S`/`F` = under $500,000. `cost_tokens.csv` starts from
   that, not from our inference. `X`, a bare hyphen and empty cells all occur
   and none was anticipated in CLAUDE.md.
6. **`(P)` in the column header marks a projection** - it is published, not
   inferred from the year.
7. **The open data CSV is a check, not a source.** It is under the OGL and is
   worth having, but it is a *summary of cost information*: it carries no
   description, no objective, and **no legal reference**. The field Phase 1
   exists to use is only in the HTML. Use the CSV to validate the cost figures
   against Finance's own numbers.

**Also worth knowing:** `curl` cannot fetch the canada.ca pages at all (HTTP/2
`INTERNAL_ERROR`; HTTP/1.1 hangs), the CSVs are Windows-1252 with CRLF, and the
same number appears three ways - `1,770` in English HTML, `5 515` with a
non-breaking space in French HTML, `5,515` in the French CSV.

### Step 3 - parse, resolve, catalogue, test - **DONE**

Grammar written first in `docs/reference-rule.md` Part 2, then implemented.
90 tests pass.

| table | rows |
|---|---|
| `measures` | 247 (211 paired + 18 English-only + 18 French-only) |
| `measure_references` | 790 |
| `measure_costs` | 6,440 |
| `measure_history` | 681 |
| `measure_beneficiary_counts` | 458 |

**Reference resolution, by status:**

| status | all references | ITA/ITR only |
|---|---|---|
| `resolved` | 600 (77.5%) | **600 (91.3%)** |
| `schedule_or_class` | 79 | 31 |
| `instrument_not_held` | 53 | - |
| `not_in_consolidation` | 19 | 19 |
| `no_provision` | 12 | 2 |
| `no_instrument` | 6 | - |
| `term_not_joined` | 5 | 5 |
| **total** | **774** | **657** |

A 100% rate would be evidence of a bug: the Excise Tax Act references and the
Schedule references cannot resolve by construction.

**Validated against Finance's own numbers:** 559 cost cells have a counterpart
in the open data CSV and all 559 match.

**Both CLAUDE.md fixtures pass.** The reorganization deferral resolves to
sections 55, 85, 87 and 88 with no cost estimate in any year; the measure citing
paragraph 20(1)(ss) resolves to `20(1)(ss)`.

**Measures join in two passes.** 201 pair on references and cost values
(`join_method='content'`); a second pass on Finance's categorical fields -
CCOFOG codes, tax, objective category, subject - pairs a further 10
(`'content_categorical'`). **211 of 229 joined; 18 stay single per language.**
The Part 3 category lists supply the vocabulary, but are alphabetical in their
own language, so the French-to-English lookup is learned from the first-pass
pairs and vocabulary-checked. All 16 categorical pairs are correct read as
names, which the signature never saw.

**Fourteen catalogues**, each diffed against a committed fixture.

**Precision sample round 1: 28 of 30 pass.** The two failures were a real bug -
French paragraph labels written without an opening bracket, read as section
numbers - and it had produced 6 false resolutions corpus-wide, not only the 2 in
the sample. Fixed by rebuilding the normaliser on bracket matching rather than
keyword matching, with three tests added, one of which caught a second variant
the first fix had missed. Full account in
`tests/spot_checks/references-RESULTS.md`.

Resolution after both rounds: 600 resolved of 774. Measures joined: 201 `content` plus
10 `content_categorical` = 211 of 229.

**Waiting on Matt:** `tests/spot_checks/references-2.md` - a fresh seeded sample
of 30 drawn from the post-fix build. The first sample is never regenerated;
regenerating it would orphan the results it is evidence for.

---

## Phase 2 - indicators

**CLAUDE.md's "Phase 2: Indicators" section governs.** Read it before working
here. Matt adopted four amendments to it on 2026-09-20:

1. Indicators are **SQL views inside `portage.sqlite`**, not a stored table.
2. `docs/indicator-definitions.md` is **generated** from each view's SQL plus a
   prose paragraph, and tested current.
3. **Cross-edition comparison is out of scope** until a second edition exists.
4. **The Excise Tax Act comes after Phase 2**, not before.

### Step 1 - definitions before SQL - **DONE**

`docs/indicator-definitions.md`. Every view, what it means, and what null means
in it, written before any SQL. Four design questions were raised and answered:

- Parameterized views do not exist in SQLite, so the year is **a column** and
  the reader supplies the threshold. No per-threshold views.
- `indicators` is **one row per measure** (247), `_en` / `_fr` on copied labels,
  with `join_method` carried through so the 36 unjoined singles stay visible.
- `cost_status` has **five** values; `no_cost_table` was added because 46
  measures have no cost table at all, which is a different statement from a
  table showing no estimate.
- Temporal scope is extracted over the **cited provisions only**, ~400 of them.

Three facts checked against the data first, because they decided the rules: only
52 of 183 measures publish a `Total` cost row (130 publish exactly one
component, 1 publishes several with no Total); Finance's Part 3 groups objective
categories into 12 internal and 10 other; 1,240 sections carry a history note,
semicolon-separated after a `[NOTE: ...]` prefix.

### Step 2 - the SQL - **NEXT**

In this order:

1. **`indicators` first**, because everything else reads from it. Build it
   column group by column group in the order the doc lists them - cost,
   beneficiaries, history, objective source, classification, legal footprint -
   and leave the temporal-scope columns null until step 3 supplies the table.
2. **Then the ten canned views**, each a filter over `indicators` or the base
   tables. None carries an `ORDER BY` that implies importance.
3. **Then the generator and its test**: the prose lives in a dict in code, the
   SQL is read back from `sqlite_master`, the doc is written from both, and a
   test asserts the file on disk matches what the generator produces.

Two small things the doc leaves open, to decide while writing the SQL: whether
`sections_touched` takes the top-level section from the path string or from the
`sections` row, and whether `v_provision_footprint` returns one row per
(path, measure) pair or one per path with a count.

### Step 3 - temporal scope - **AFTER STEP 2**

The one extraction in Phase 2 that needs a model, and the only part of this
project that calls an API. CLAUDE.md's rules are strict and are not negotiable:

- the extracted phrase must be a **verbatim substring** of `text_en`, asserted
  by a test for every row;
- the model never infers a date the text does not state;
- prompt, model name and run date recorded in `meta`;
- **the API is called from a batch script, never from the build**, and its
  output is committed as data with a fixture;
- a precision sample of 30 rows checked by hand, same protocol as Phase 1.

Scope is the cited provisions only. Expect this to be the slowest step and the
one most likely to produce a finding about the Act rather than about the code.

### Step 4 - acceptance tests

Listed in CLAUDE.md. Two need Matt before they can be written:

- **Hand recomputation fixtures**: three measures' `cost_change` computed by
  Matt in a spreadsheet from the published pages, asserted equal. He supplies
  the three.
- **View row counts** recorded in a fixture for this edition.

The others are mechanical: every column has a definitions entry; the
reorganization deferral is `not_costed` with `provisions_resolved = 4`; no
indicator is non-null where an input is null; temporal phrases are verbatim.

---

## Not in Phase 2

From CLAUDE.md's "Explicitly out of Phase 2":

- **Any qualitative flag** - "objective no longer applies", "beneficiary field
  disagrees with cost table". Phase 3 candidates at best, and they need a human
  decision on whether they belong in a dataset at all.
- **Evaluations linkage.** Finance's list of published evaluations is not keyed
  to measures, and linking by title would be judgment. Catalogue the list as
  published; do not link it.
- **Any front end.** Views are SQL. Presentation comes after Phase 3 test users
  have asked their own questions.
- **Any text that says what a reader should do with an indicator.**

Also still out, carried from earlier phases: embeddings, an MCP server, and
cross-edition comparison until a second edition exists.

---

## Carried forward, unresolved

Known gaps, none of them blocking Phase 2. Each is documented where it matters
and most are catalogued with a fixture.

**Coverage**

- **The Excise Tax Act is cited 53 times and is not held.** The single largest
  available gain in reference coverage. Deferred to after Phase 2.
- 174 of 774 references do not resolve: 79 Schedule or Part forms, 53 naming
  instruments we do not hold, 19 provisions absent from the consolidation, 12
  with no provision recognised, 6 with no instrument named, 5 `term_not_joined`.
- **Schedules are not captured** in either instrument. "Listed Corporations" is
  part of the Act and its omission is a gap, not a principle.
- **Table structure is not modelled** - the Regulations' five tables survive as
  text, without cell geometry.

**Precision**

- **18 measures per language do not join.** Nothing language-independent to
  join on: no resolvable reference, no numeric cost, a shared categorical
  signature.
- **Beneficiary counts: 75 of 458 rows parsed.** The field is prose, and this is
  the weakest thing in the dataset - unlike a reference, a wrong count does not
  announce itself.
- **Ranges are endpoints only**, so a measure citing a range is not linked to
  the provisions between them.
- **Fragments join by ordinal across languages.** `2(3)~c1` pairs with `2(3)~c1`
  by position. Flagged where counts differ, paired on trust where they match -
  the one place position is still doing work.
- `history_note` is section-level only, because that is where the source
  attaches it.

**Open questions for a person, not for code**

- **Commercial redistribution.** Justice Canada's standing permission to
  reproduce enactments is not conditioned on non-commercial use, while a
  separate clause restricts commercial redistribution of site materials. Both
  are quoted verbatim in `docs/source-notes.md`. The project is non-commercial;
  what a downstream commercial user may do needs a real opinion.
- **13 malformed labels in the published XML**, catalogued. Three are in the
  English Act and were handled; the rest were left as published.
