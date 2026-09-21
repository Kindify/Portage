# Plan

## Where things stand

**Phases 0, 1 and 2 are complete and released** - `v0.1.0`, `v0.2.0`, `v0.3.0`.
**Next: the findings review, then the Excise Tax Act.**

Start here, then read `CLAUDE.md`. Where this file and CLAUDE.md differ,
**CLAUDE.md governs**, with four amendments Matt adopted on 2026-09-20, recorded
in `docs/decisions.md` and summarised under Phase 2 below.

### What exists

| | |
|---|---|
| `portage.sqlite` | built by `python -m portage.build` in about a minute |
| Phase 0 | 49,032 provision records, ITA and ITR, both languages, consolidation 2026-06-18 |
| Phase 1 | 229 tax expenditure measures per language, 774 references, 6,440 cost cells |
| Phase 2 | 13 views, 61 indicator columns, 6 extraction tables, 1,086 temporal bounds |
| tests | 146, `pytest`, none skipped |
| catalogues | 25, each diffed against a committed fixture in `tests/fixtures/` |
| hand checks | 40 provision + 60 reference + 110 temporal, all recorded with results |

### The documents, and what each is for

| file | what it carries |
|---|---|
| `CLAUDE.md` | the brief and the non-negotiables. Governs. |
| `PLAN.md` | where the work stands and what is next. This file. |
| `docs/decisions.md` | every decision, dated, with the reasoning. 40+ entries. |
| `docs/source-notes.md` | what the real source data looks like, checked not assumed |
| `docs/citation-path-rule.md` | how a provision becomes a citation path |
| `docs/reference-rule.md` | how a reference resolves - Part 1 tagged, Part 2 the report |
| `docs/indicator-definitions.md` | **generated** by the build: every view, its SQL, and every indicator column's meaning and null rule. Edit `portage/indicators.py`, not this file. |
| `views/*.sql` | the same view SQL as one file per view, for reading without opening the database |
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

### Step 2 - the SQL - **DONE**

`portage/indicators.py`. 13 views in `portage.sqlite`, exported to `views/`,
documented in a generated `docs/indicator-definitions.md`, 22 tests.

| view | rows |
|---|---|
| `indicators` | 247, one per measure, 60 columns |
| `measure_resolved_provisions` | 332 |
| `measure_provision_overlap` | 230 |
| `v_not_costed` / `v_withheld` | 10 / 9 |
| `v_no_beneficiary_count` | 172 |
| `v_last_change_by_year` | 247 |
| `v_objective_internal` | 70 |
| `v_overlapping_programs` | 208 |
| `v_shared_provisions` | 34 |
| `v_not_in_consolidation` | 13 |
| `v_provision_footprint` | 332 |
| `v_end_bound_by_year` | 0 until step 3 |

Six **extraction tables** feed them, each with a `method` column and a fixture:
`objective_category_groups`, `measure_objective_categories`,
`measure_objective_source`, `section_amending_acts`, `measure_figure_basis`,
and `provision_temporal_scope` (created empty for step 3).

**Both open questions answered.** The top-level section is cut out of a
citation path at the first `(`, `"` or `~` - the quote matters, because
`54"principal residence"` would otherwise yield a section that does not exist.
`v_provision_footprint` returns one row per (provision, measure) pair.

**Six findings from writing the SQL**, all in `docs/decisions.md`:

1. **Five measures publish several `Total` rows**, not the one the definitions
   doc expected, because they publish more than one cost table and
   `measure_costs` has no table index. For the three donation measures the
   second table totals *a group of related measures*; for farm savings accounts
   the third Total is the measure's own; for non-capital loss carry-overs there
   are five subtotals and no grand Total. No rule gets all five right, so all
   five get null cost figures and `cost_figure_basis = 'multiple_total_rows'`.
2. **Finance's measure cells do not always use Finance's own Part 3
   vocabulary** - 18 cells, including two French cells with entirely different
   wording from the French list. Nine measures get a null
   `objective_category_internal` rather than a guessed one.
3. **Six measures resolve differently in the two editions.** Indicators read
   one edition per measure (English where it exists), recorded in
   `measure_figure_basis`; the disagreements are catalogued, not reconciled.
4. **All 75 parsed beneficiary counts are English.** The pattern reads English
   prose only, so a French-only measure can never carry one.
5. **`amending_acts_count` excludes the first entry in a history note**, which
   is the enactment that put the section there rather than an amendment. Both
   numbers are stored.
6. **The internal / other grouping is read from each edition's own markup** -
   English marks the headings with `<strong>`, French with `<h5>` - rather than
   reading the French groups off the English order.

**Three places CLAUDE.md was corrected to match what was built** (`8fbd2fc`),
each for a reason recorded in `docs/decisions.md`. The brief and the build now
agree; this list is here so the change is not invisible:

- Acceptance test 3 asked for `cost_status = 'not_costed'` on the
  reorganization deferral. It is **`no_cost_table`** - Finance published no cost
  table for it at all, which is what the fifth value exists to say. The other
  two assertions in that test passed as written.
- `cost_per_beneficiary` is **dollars**, not millions of dollars, per
  beneficiary.
- `beneficiaries_raw` is **two columns**, `_en` and `_fr`. One column would drop
  the published French sentence wherever an English one exists.

The cost basis column is also named as built - `cost_figure_basis`, five values
- rather than `cost_total_or_component`, which was never written.

### Step 3 - temporal scope - **DONE**

1,086 date-bounded conditions over 814 provisions, one prompt hash, one
reject, none dropped by the build's independent re-check. Model
`claude-opus-5`, effort `high`, Batch API, ~$25 across seven batches.

| kind | rows | |
|---|---|---|
| `start` | 323 | opens a period |
| `step_down` | 304 | a dated component of a rate schedule |
| `end` | 266 | closes a period |
| `at` | 193 | holds on, as of, or including a named date |

**Six hand-check samples, all read, all with recorded results**: precision and
recall for three rounds, plus a supplementary sample drawn from `at` alone.
Every one found something, and what each found is in its RESULTS file.

The sequence is worth reading before the next extraction is designed. Round 1
found conditions that are not boundaries labelled as boundaries, and the fix
was a fourth kind. Round 2 found the same class again plus version references
over-extracted by that new kind. Three rounds of widening a *filter* fixed
less each time, and the last proved why - the filter selected exactly the
right provisions and the answers did not change, because the cause was missing
context, not missing selection. Putting the parent and children in the request
closed both classes at once. Then the `at` sample found that the same change
had **opened** a third class.

### Pending: the designated-period rerun

**Prompt version 4 is written and has not been run.** Rule 3b: a designated
reference period, specified month or qualifying period is a label, not a
bound. Hash `dc8fe9d65aeb75ab5724bec4efdb68a2079fefee494851b8be8e4f648c8d6d11`.

94 of the 193 `at` rows are in this class, across 69 provisions in ITA 122.5
and 125.7, which also hold 42 `end` and 39 `start` rows a rerun would revisit.

**Scheduled for the next consolidation**, not now, because `at` contributes no
value to any indicator - `earliest_end_date` and `latest_end_date` read
`bound_kind = 'end'`, `has_step_down` reads `'step_down'`, and the only effect
is that two measures whose sole temporal rows are `at` report
`has_step_down = 0` rather than null. Rerunning the whole scope at v4 is
~$10 and the corpus will be rebuilt against the new consolidation anyway.

To run it: `python -m scripts.extract_temporal_scope` with write mode
REPLACE, then `--samples 4` once round 4 seeds are wired.

#### How it was run

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

## What is next

### 1. The findings review

Phase 2 produced findings that are not yet anyone's decision. They are
scattered across `docs/decisions.md`, six RESULTS files and
`data/extraction_notes.csv`, and the useful next step is a person reading them
together and deciding which are dataset questions and which are Phase 3:

- **Six taxonomy edges** in `extraction_notes.csv`, none of them errors: where
  a rate schedule's edges stop being part of the schedule (twice), whether an
  enumeration of named years is a fifth shape, whether a deemed date belongs
  in the taxonomy, a borderline step-down, and the period-definition class.
- **Limit A**: 84 provisions carry point-in-time or exception-year conditions,
  of which 10 produce nothing. Exception-year still has no kind.
- **Limit B**: mostly closed by context, but 12 provisions had a condition
  spanning a parent and a child before the rebuild; nobody has recounted.
- **The designated-period rerun** above.
- **Beneficiary counts**: 75 of 458 parsed, all English. Still the weakest
  thing in the dataset, and unlike a reference a wrong count does not announce
  itself.

### 2. The Excise Tax Act

Deferred since Phase 1 and now the largest single gain available: **53
references name it and none can resolve**, because the instrument is not held.
Adding it is the same shape of work as Phase 0 - fetch the XML, parse to
citation paths, join bilingually - and it converts 53 unresolved references
into resolved ones without changing any rule.

Also still open, carried from earlier phases: Schedules are not captured in
either instrument; table structure is not modelled; ranges are endpoints only;
and the commercial-redistribution question needs a real opinion, not a
guess.

---

### Step 4 - acceptance tests - **MOSTLY DONE**

Written in `tests/test_indicators.py`. The mechanical ones pass: every column
has a definitions entry and the doc is regenerated and diffed; the
reorganization deferral resolves to 55, 85, 87 and 88 with no cost table; no
indicator is non-null where an input is null; no view carries a top-level
`ORDER BY`; every derived top-level section is a real section; Finance's
grouping is 12 and 10 in both languages. **View row counts** are recorded in
`tests/fixtures/view_row_counts.csv`.

**Waiting on Matt - one thing.** `tests/fixtures/cost_change_by_hand.csv` has a
header and no rows. CLAUDE.md asks for three measures whose `cost_change` Matt
computes in a spreadsheet from the published pages; the test reads the fixture
and asserts equality, and skips while the fixture is empty. Any three measures
with `cost_status = 'costed'` will do - `SELECT name_en, cost_first_estimate,
cost_latest_estimate, cost_change_abs FROM indicators WHERE cost_status =
'costed'` lists the candidates, and the point is to check them against the
report pages rather than against that query.

The temporal-scope tests - verbatim phrases, and model, prompt hash and run
date in `meta` - are written and vacuous until step 3 fills the table.

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
