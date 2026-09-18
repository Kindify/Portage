# Plan

## Where things stand

**Phase 0, session 2 (2026-09-18): the parser works on the English Income Tax
Act.** `python -m portage.build` produces `portage.sqlite` and 19 tests pass,
including a byte-exact round trip with no normalisation at all.

French, the Regulations and cross-references are still to come.

---

## Done in session 2

**XML vocabulary mapped** before any code was written -
`docs/source-notes.md` section 4. Two invariants checked rather than assumed:
an addressable unit has at most one direct `<Text>`, and that text never follows
a structural child.

**The citation path rule written down first**, as a specification with worked
examples, in `docs/citation-path-rule.md`. Two refinements were needed once it
met the data, both logged with reasons.

**`portage/labels.py`** - label normalisation. **`portage/parse.py`** - XML to
records, a pure function. **`portage/build.py`** - records to SQLite, with
`sections`, `meta`, an English FTS5 index, the anomaly catalogue and the
spot-check file.

**Results on the English Act:**

| | |
|---|---|
| rows in `sections` | 36,277 |
| addressable units | 31,501 |
| sections (Body) | 763 |
| label anomalies | 26, catalogued in `tests/fixtures/label_anomalies.csv` |
| citation path collisions | 0 |
| round trip | **exact, zero normalisation** |
| tests | 19 passing |

### The two bugs worth remembering

**A round-trip test that shared the parser's blind spot passed while wrong.**
Both skipped every `<Label>`, so both lost the formula variable names on
`FormulaDefinition` elements - 93 characters. An independent character
accounting against the raw XML caught it. `source_text()` now uses a different
method from the parser, and a second test accounts for every character by a
third route. Written up in `docs/decisions.md`.

**Treating definitions as transparent would have silently lost 3,412 rows.**
`Definition` carries no label but holds 6,853 addressable descendants, so
`248(1)(a)` collided 86 ways. Definitions now get a `~d<n>` ordinal.

---

## Session 3 - scope

**Add French to the Income Tax Act.** Still not the Regulations.

1. Parse `data/ITA-fra.xml` with the same parser - it is language-agnostic
   already, and the label rule handles French forms.
2. Join English and French on `citation_path`. Populate `text_fr`,
   `heading_fr`, `label_fr`.
3. Write `data/bilingual_gaps.csv` and commit
   `tests/fixtures/bilingual_gaps.csv`. The diff test is already written for
   label anomalies and the same shape applies.
4. Confirm the three converging typos. Session 1 counted 941 single-language
   paths **before** the label rule existed. 12.4, 181.7 and 190.21 should now
   resolve to the same path in both languages and stop being gaps. The
   catalogue will say what is actually left; the 941 is not a target.
5. Add the French FTS5 index.

Then session 4: the Regulations, and the tagged `cross_references` table.

---

## Open questions for Matt

**1. How should definitions be keyed?** Currently `248(1)~d17(a)` - an ordinal
in document order. It works, collides with nothing and needs no text parsing, but
nobody can cite it and it cannot be looked up by hand, so definitions are
excluded from the spot-check file. The alternative is the defined term itself,
`248(1)"active business"(a)`, which is how these are actually cited - but the
term is missing from about 5% of definitions, and the English and French terms
differ, so it would not serve as a bilingual join key without more thought.
`defined_term_en` and `defined_term_fr` are already stored, so switching later
needs no reparse. **This is the one I would most like an answer on**, because
definitions are the most-cited part of the Act.

**2. Three new columns.** `is_addressable`, `label_raw` and `label_anomaly` are
not in the CLAUDE.md column list. The reasoning is in `docs/decisions.md`; the
alternative for continued text was a second table. Confirm or redirect.

**3. The "Listed Corporations" schedule is not captured.** It is part of the Act
but contains no `Section` elements, so nothing in the current model holds it.
Should Phase 0 include schedules at all? The round-trip currently covers the
enacted `<Body>` only, which is stated in the test.

**4. `history_note` is section-level.** 762 `HistoricalNote` elements against
763 sections. Subsections do not carry their own. The column exists on every row
but is only ever populated on sections - confirm that is what you want rather
than a separate table.

---

## Carried forward

- **Commercial redistribution** remains an open legal question. Not a blocker.
- **`tests/spot_checks.md`** needs a pass by hand against the Justice Laws site.
  Twenty rows, seeded so they stay stable between builds.

---

## Not in Phase 0

Embeddings, a web front end, an MCP server, the Finance Canada tax expenditure
linkage, indicator publishing. Later phases.
