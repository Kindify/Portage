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

### Step 2 - inspect the report before parsing it

`docs/source-notes.md` first, as in Phase 0. The questions to answer against the
real pages, not from assumption:

- Are Parts 3 to 7 clean HTML, or tables inside a PDF? This decides the shape of
  the whole phase.
- Does the same data exist on open.canada.ca under the OGL? If so, prefer those
  terms and quote both.
- Confirm the actual field set per measure against `CLAUDE.md`'s expected list.
  Fields absent for a measure are null, never empty string or zero.
- What does the French edition's URL structure look like, from the language
  toggle?
- What distinct tokens appear in cost cells? `S`, `n.a.`, and the
  no-estimate wording are known; the fixture in `data/cost_tokens.csv` has to
  start from what is actually there.

### Step 3 - write the reference grammar down before implementing it

`docs/reference-rule.md`, the same discipline as `docs/citation-path-rule.md`.
Pattern extraction is permitted here because failure is visible - a reference
either resolves to an existing `citation_path` or it does not - but the grammar
still gets written first: section, subsection, paragraph, subparagraph, clause;
ranges with "to"; lists with "and"; "of the Act" against "of the Regulations";
Part and Schedule references. Anything the grammar does not cover is stored
unresolved with its raw text. Never dropped, never guessed.

### Step 4 - parse, resolve, catalogue, test

Five tables (`measures`, `measure_references`, `measure_costs`,
`measure_history`, `measure_beneficiary_counts`) and eight acceptance tests, all
specified in `CLAUDE.md`.

The bilingual join is the part Phase 0 has already taught us about: measures are
alphabetical in each language, so **position means nothing across editions** -
the same trap as definitions. Join on the language-independent content, the
reference set plus the cost values. Anything that does not join uniquely is
catalogued and both singles survive.

**Resolution rate is reported, not asserted.** A build that resolves 100% is
suspicious, not good.

---

## Open items

**1. Fragments join by ordinal across languages.** `2(3)~c1` in English pairs
with `2(3)~c1` in French purely by position within the provision. Where the
counts differ the rows are flagged; where they match they are paired on trust.
It is the same species of assumption that ordinals failed at for definitions,
though the consequences are smaller - fragments are not citable and each
language round-trips in its own order.

**2. Schedules are not captured.** Three in the Act, ten in the Regulations.
"AMENDMENTS NOT IN FORCE" is rightly excluded, but "Listed Corporations" and the
Regulations' schedules are part of the instruments.

**3. Table structure is not modelled.** Text is preserved, cell geometry is not.

**4. `history_note` is section-level only.** 762 notes against 763 sections in
the Act; the source does not attach them to subsections.

**5. The spot-check files have not been checked by hand.** Eighty citations
across four files, waiting on Matt. Nothing else substitutes for this - every
other guard compares the build against the same XML.

**6. Commercial redistribution** remains an open legal question. Not a blocker;
the project is non-commercial.

---

## Not in Phase 1

From `CLAUDE.md`: interacting provisions Finance does not list; any indicator,
ranking or score; temporal scope extraction from the Act's text; any front end.
Also still out: embeddings and an MCP server.
