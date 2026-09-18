# Plan

## Where things stand

**Phase 0 is built and tested; it is not yet released.** Both instruments, both
languages, 46 tests passing, all four round trips exact.

The one thing standing between here and v0.1.0 is the eighty hand spot checks.
Every automated guard in this project reads the same four XML files the build
reads, so none of them can catch a file being misread the same way twice. The
spot checks are the only evidence from outside that loop, and the tag should
mean "checked", not "built".

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

## Release - v0.1.0

**Not tagged yet.** It is waiting on the eighty hand spot checks, which is the
right order: the tag should mean "checked", not "built". When
`tests/spot_checks/RESULTS.md` is filled in and the README's Methods section
records the date and outcome, the tag can go on.

Release assets, when it does:

- `portage.sqlite` - the built database
- the six catalogue CSVs from `data/`
- `README.md`
- `tests/spot_checks/RESULTS.md`, so the verification travels with the data

---

## Phase 1 - the tax expenditure report

Link each provision to what it costs. This is the point of the project: Phase 0
made the Act navigable, Phase 1 attaches the money.

**Source:** the 2026 *Report on Federal Tax Expenditures*, Department of Finance
Canada, **Parts 3 to 7**, English and French.

### Scope

1. **Parse Parts 3 to 7 into structured records**, both languages. One record per
   tax expenditure, carrying at minimum: its identifier, its title in both
   languages, its description, the cost estimates with their years, and whatever
   the report states about the legal authority for it.
2. **Resolve every legal reference to a `citation_path`.** This is where Phase 0
   pays off - a reference to "paragraph 110(1)(d)" has to land on the row whose
   `citation_path` is `110(1)(d)`, and either it resolves or it does not.
3. **Report which references fail to resolve.** Catalogued, not dropped, with a
   fixture, exactly as in Phase 0. An unresolved reference is a finding about
   either the report or our data, and both are worth knowing.

### What to settle before writing any code

- **What format is the report published in?** PDF, HTML, spreadsheet? A PDF of
  tables is a different project from an HTML document. Inspect the real source
  and write it up in `docs/source-notes.md` before assuming anything - the same
  rule that kept Phase 0 out of trouble.
- **What licence does Finance Canada publish it under?** Quote it verbatim.
- **How are legal references written in the report?** They will be prose
  ("paragraph 110(1)(d) of the Act"), which means extraction by pattern - the
  technique Phase 0 deliberately avoided. It is defensible here because a
  reference that fails to resolve is *visible*, where a mis-parsed structure is
  not. But it needs the same treatment as internal cross-references: a `method`
  column, a catalogue, and a precision sample.
- **Does a tax expenditure map to one provision or several?** If a mapping needs
  a tax opinion, CLAUDE.md says it does not go in the data.

### Still outstanding from Phase 0

`cross_references`, tagged only - `XRefExternal` and `DefinitionRef`, every row
`method = 'tagged'`. Carried forward because the source has no markup for
internal references, which is where most of the value would be. Phase 1 should
probably do this first, since resolving references is the same machinery.

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
