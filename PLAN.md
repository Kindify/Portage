# Plan

## Where things stand

**Phase 0 is complete.** The Income Tax Act and the Income Tax Regulations are
built in both languages, from the official Justice Laws XML, with 41 tests
passing and all four round trips exact.

What remains for Phase 1: the `cross_references` table, and then the Finance
Canada tax expenditure linkage.

---

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

## Phase 1

1. **`cross_references`, tagged only.** `XRefExternal` and `DefinitionRef`,
   every row `method = 'tagged'`, unresolved targets reported rather than
   dropped. This is the last item in CLAUDE.md's Phase 0 list; it is being
   carried into Phase 1 because the source has no markup for internal
   references, which is where most of the value would be.
2. **Internal references**, as a separate table with
   `method = 'extracted'`, its own validation and its own precision report.
3. **Finance Canada tax expenditure linkage.**

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

## Not in Phase 0

Embeddings, a web front end, an MCP server, indicator publishing. Later phases.
