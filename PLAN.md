# Plan

## Where things stand

**Phase 0 is released as `v0.1.0`.** Both instruments, both languages, 47 tests
passing, all four round trips exact, and forty citations verified by hand against
the official site on 18 and 19 September 2026 with no mismatches.

Next: Phase 1, the tax expenditure report. Scope and rules are in `CLAUDE.md`;
what follows is the working plan for getting there.

## What Phase 0 delivers

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

## Done in session 4

**Divergent addressable rows are split** (option (c)). The English record keeps
the path, the French moves to `<path>~fr`, both are flagged as gaps and point at
each other through `same_path_counterpart`. Fragments stay joined and keep
`alignment_unverified = 1`. **No row under 51(1) carries both languages** - a
test asserts it.

**The Regulations parsed with no changes to the walker.** Both round trips were
exact on the first run.

**The Regulations use CALS table markup** the Act never uses - `TableGroup`,
`table`, `row`, `entry`, `colspec`, `Caption`; 5 tables, 157 rows, 314 cells.
It needed no special handling: the `_is_text_leaf` rule from session 2 is
structural rather than a list of element names, so an unseen vocabulary was
captured rather than dropped. Table text is preserved exactly; table *structure*
is not modelled, which is stated in README.

**One real bug, found by the Regulations.** The Regulations number sections
`3000 to 3002` / `3000 à 3002`; the Act has no section-level ranges, so the
label rule translated range connectors only below section level and the two
languages never joined. Caught by the section-count test - written for a
different purpose - which expected 499 and found 501.

**A correction.** Session 1 said the Act contains zero `XRefInternal` elements.
That count was English-only; the French Act has one. It does not change the
tagged-only decision, but the original statement was too absolute.

**README gained a Methods section** setting out the three independent guards -
round-trip against a separate reconstruction, uniqueness on the shipped key,
symmetric bilingual join - and the three-version history of the definition rule.

---

## Released - v0.1.0

Tagged. Assets assembled in `dist/v0.1.0/` with `SHA256SUMS.txt`, ready to
upload wherever the project is published (there is no git remote yet):
`portage.sqlite`, the six catalogue CSVs, `README.md`, and the spot-check
results with the four verified samples.

---

## Phase 1 - the tax expenditure report

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
| `measures` | 265 (193 paired + 36 English-only + 36 French-only) |
| `measure_references` | 790 |
| `measure_costs` | 6,440 |
| `measure_history` | 681 |
| `measure_beneficiary_counts` | 458 |

**Reference resolution, by status:**

| status | all references | ITA/ITR only |
|---|---|---|
| `resolved` | 613 (77.6%) | **613 (91.1%)** |
| `schedule_or_class` | 68 | 20 |
| `instrument_not_held` | 53 | - |
| `not_in_consolidation` | 33 | 33 |
| `no_provision` | 12 | 2 |
| `no_instrument` | 6 | - |
| `term_not_joined` | 5 | 5 |
| **total** | **790** | **673** |

A 100% rate would be evidence of a bug: the Excise Tax Act references and the
Schedule references cannot resolve by construction.

**Validated against Finance's own numbers:** 559 cost cells have a counterpart
in the open data CSV and all 559 match.

**Both CLAUDE.md fixtures pass.** The reorganization deferral resolves to
sections 55, 85, 87 and 88 with no cost estimate in any year; the measure citing
paragraph 20(1)(ss) resolves to `20(1)(ss)`.

**Six catalogues**, each diffed against a committed fixture:
`field_label_variants.csv` (43 rows - a new label at any position fails the
build), `cost_tokens.csv` (11 symbol rows), `unresolved_references.csv`,
`measure_join_gaps.csv`, `measures_without_references.csv`, and the Phase 0 six.

**Waiting on Matt:** `tests/spot_checks/references.md` - 30 resolved references
to check by hand. Resolution is mechanical, so what it checks is whether the
grammar reads Finance's citation the way a person would, which no automated test
here can tell us because they all read the same grammar.

## Open items

**1. The 30-row precision sample has not been checked.** Nothing else in Phase 1
tells us whether the grammar reads a citation the way a person would.

**2. 36 measures do not join across languages.** Mostly measures with no
resolvable reference and no numeric cost - nothing language-independent to join
on. The open data CSVs were checked as a possible Finance-supplied pairing and
**cannot serve**: only 39.8% of their rows align, because each file is
alphabetical in its own language. A name or order tie-breaker would be judgment.

**3. Beneficiary counts are mostly unparsed** - 75 of 458 rows, and this is
the weakest field in the dataset. The field is prose, and unlike a reference a
wrong count does not announce itself by failing to resolve.

**4. Phase 0 items still open:** fragments join by ordinal across languages;
schedules not captured; table structure not modelled; `history_note` is
section-level only.

**5. Commercial redistribution** remains an open legal question. Not a blocker.

## Not in Phase 1

From `CLAUDE.md`: interacting provisions Finance does not list; any indicator,
ranking or score; temporal scope extraction from the Act's text; any front end.
Also still out: embeddings and an MCP server.
