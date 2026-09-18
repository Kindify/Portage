# Plan

## Where things stand

**Phase 0, session 1 (2026-09-18): inspection, setup and decisions. Complete.**
No parser has been written. There is no `portage.sqlite` yet.

All five open questions from the first draft of this plan have been answered by
Matt and logged in `docs/decisions.md`. Session 2 is unblocked.

---

## Done in session 1

**Project set up.** Git repository on `main`, repo-local identity. Layout:
`portage/` package, `tests/`, `docs/`, `data/`. `.gitignore` excludes source
downloads, the built database, and `.venv/`. MIT `LICENSE`.

**Python environment.** `uv` manages a standalone Python 3.12 in a project-local
`.venv/`; the Apple-supplied 3.9 is untouched. pandas 3.0.6, pyarrow 25.0.1,
lxml 6.1.3, pytest 9.1.1. SQLite 3.53.1 with FTS5 confirmed present.

**Both candidate sources inspected**, written up in `docs/source-notes.md` with
raw records, element counts, file hashes and verbatim licence text.
**Source chosen: the Justice Laws XML**, because A2AJ's records stop at the
section and discard the hierarchy, headings and history notes entirely.

**Bilingual divergence investigated and quantified** (`docs/source-notes.md`
section 3). It is real drafting divergence, not a bug: 96.67% of citation paths
exist in both languages, 3.33% in only one.

**README** carries the Justice Canada clause, the OGL terms verbatim, and a
"Known limits" section stating plainly what Phase 0 does not contain.

---

## Settled (see `docs/decisions.md` for the reasoning)

| | Decision |
|---|---|
| Source | Justice Laws XML, both instruments, both languages |
| Cross-references | Phase 0: tagged only (`XRefExternal`, `DefinitionRef`), `method = 'tagged'`. Internal refs deferred to Phase 1, separate table, `method = 'extracted'` |
| Bilingual join | on `citation_path`; single-language paths keep the record with the other side NULL and `bilingual_gap = 1`; never force alignment |
| `citation_path` | English label form in both languages; native labels kept in `label_en` / `label_fr` |
| Uniqueness | `UNIQUE (act, citation_path)` |
| `meta` dates | `consolidation_date` (from `lims:pit-date` = 2026-06-18) and `retrieved_date`, stored separately |
| Licensing | terms recorded verbatim; project non-commercial; commercial redistribution logged as an open legal question, not a blocker |

---

## Session 2 - scope

**One file only: the Income Tax Act, English (`data/ITA-eng.xml`).**
Do not touch French or the Regulations until the round-trip and structure tests
pass on this one file. The point is to get the hard part right once, on the
largest and messiest instrument, before multiplying the surface area.

### Steps

1. **Finish mapping the XML vocabulary.** Before writing the parser, enumerate
   every element that can hold text and record the findings in
   `docs/source-notes.md`. The ones that will decide the round-trip test:
   - `ContinuedParagraph` (649) and `ContinuedSectionSubsection` (628) - text
     belonging to a parent that appears *after* a child element. Their ordering
     is what makes round-tripping non-trivial.
   - the `Formula*` family (754 `Formula`, plus `FormulaGroup`, `FormulaTerm`,
     `FormulaDefinition`, `FormulaParagraph`, `FormulaText`, `FormulaConnector`)
   - `Definition` (2,199), `DefinedTermEn` (3,359)
   - `Repealed` (548)
   - `Heading` (195) and `TitleText` (198) - structural headings above the
     section level, distinct from `MarginalNote`

2. **Write the citation-path rule down** as prose with worked examples before
   implementing it, covering: bare section labels, bracketed lower levels,
   range labels, and the 13 malformed source labels already catalogued in
   `docs/source-notes.md` section 3. The rule reads `<Label>` only.

3. **`portage/parse.py`** - XML in, records out. A pure function, no database,
   no file writing, so it is testable directly. Structure comes from element
   nesting only; nothing is inferred from text.

4. **`portage/build.py`** - records to `portage.sqlite`. In session 2 this
   creates `sections` and `meta` and the English FTS5 index only. No
   `cross_references` table yet; no French columns populated.

5. **Acceptance tests**, on the English Act only:
   - **Round-trip**: concatenating `text_en` in `order_index` order reproduces
     the source, after a whitespace normalisation that is documented and
     minimal. Expect this to be the one that fights back, and expect it to be
     what forces the `Continued*` ordering decision.
   - **Structure**: every record has a parent except top-level sections;
     `(act, citation_path)` is unique; sections appear in source order; the
     section count matches the Justice Laws table of contents.
   - **Known citations**, the English subset of the CLAUDE.md fixtures:
     245(1) "tax benefit"; 125(7) "active business carried on by a
     corporation"; 248(1) "active business"; 95(1) "active business";
     87(4) exists under 87; 55(3)(b) exists under 55(3); 118.02(2) contains
     "before 2025"; 127.44(1) contains "2040".
   - **`tests/spot_checks.md`**: 20 random citation paths with the first
     sentence of each, regenerated on every build, for Matt to check by hand.

### Done when

`python -m portage.build` produces a database of the English Income Tax Act with
`sections` and `meta` populated and the tests above passing - or a clear written
account of which test fails and why, with the failure understood rather than
worked around.

### Explicitly not in session 2

French text. The Regulations. Any `cross_references` table. FTS5 over French.
`bilingual_gap`. These come in session 3, once the parser is proven on one file.

---

## Carried forward

- **The 13 malformed source labels** (`docs/source-notes.md` section 3) need a
  handling decision. Three of them - `12.4` with label `(b`, and `181.7` /
  `190.21` with a quotation mark prefixed to the label - are in the English Act
  and so land in session 2. The rest can wait.
- **Commercial redistribution** remains an open legal question. Not a blocker;
  the project is non-commercial.
- **`history_note` granularity.** There are 762 `HistoricalNote` elements against
  785 sections, so notes attach at section level, not subsection. The column
  should reflect that rather than imply a precision the source does not have.

---

## Not in Phase 0

Named so they do not creep in: embeddings, a web front end, an MCP server, the
Finance Canada tax expenditure linkage, indicator publishing. Later phases.
