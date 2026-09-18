# Plan

## Where things stand

**Phase 0, session 1 (2026-09-18): inspection and setup. Complete.**
No parser has been written. There is no `portage.sqlite` yet.

---

## Done this session

**Project set up.** Git repository on `main`. Layout: `portage/` package,
`tests/`, `docs/`, `data/`. `.gitignore` excludes source downloads (`data/`,
`*.parquet`, `*.xml`), the built database (`portage.sqlite`), and `.venv/`.
MIT `LICENSE`. `README.md` written honestly - it says no data is built yet.

**Python environment.** The machine had only the Apple-supplied Python 3.9.6,
below the 3.11+ floor and past end-of-life. Installed `uv`, which manages its
own standalone Python 3.12 without touching the system one. Everything lives in
a project-local `.venv/`. Exact reproduction commands are in the README's Setup
section. Installed: pandas 3.0.6, pyarrow 25.0.1, lxml 6.1.3, pytest 9.1.1.
Confirmed the bundled SQLite (3.53.1) has FTS5 compiled in, which Phase 0 needs.

**Both candidate sources downloaded and inspected**, findings written up in
`docs/source-notes.md` with raw records, element counts, verbatim licence text
and file hashes.

- A2AJ `a2aj/canadian-laws`: 185 MB for the two federal files. Located the
  Income Tax Act (row 504) and Income Tax Regulations (row 539).
- Justice Laws XML: 38.6 MB for all four files (both instruments, both
  languages). Consolidation date `lims:pit-date = 2026-06-18`.

**Reproduction terms found and quoted** from the Department of Justice Canada
Terms and Conditions, recorded verbatim in `docs/source-notes.md`.

**Decisions logged** in `docs/decisions.md`.

---

## Recommendation (step 4)

**Parse from the Justice Laws XML, not from A2AJ.**

A2AJ's deepest unit of structure is the section: `unofficial_sections_en` maps
section numbers to strings, and zero of its 767 keys contain a subsection,
paragraph or clause reference. The whole of section 87 - every subsection, every
paragraph - is one flat Markdown string, so recovering `87(4)` would mean
splitting prose on `\n\n(4) `, recovering headings from `**bold**`, and
reconstructing nesting from number patterns. That is precisely the technique
CLAUDE.md bans and that caused three attribution bugs during scoping. It is not
a matter of extra effort: the structure has been discarded, along with the
history notes, so no amount of careful parsing recovers it. The Justice Laws XML
has every level Phase 0 needs as a real element - `Section`, `Subsection`,
`Paragraph`, `Subparagraph`, `Clause`, `Subclause` - with headings in
`MarginalNote`, amending-statute notes in `HistoricalNote`, and the
consolidation date stamped on the root element, and its English and French files
match element-for-element at section and subsection level. It is also the
smaller download (38.6 MB against 185 MB), and it is the *upstream* source:
A2AJ's own `source_url_en` field points at `laws-lois.justice.gc.ca/eng/XML/I-3.3.xml`,
so choosing the XML means reading the original rather than a lossy derivative.

`meta` will record Justice Laws as the source, with the per-file URLs and
`pit-date = 2026-06-18`.

---

## Session 2

Write the parser - but only after the open questions below are answered, since
two of them change its output.

1. **Map the XML vocabulary completely** before writing anything. Enumerate
   every element that can hold text, not just the seven levels we expect. The
   unknowns that matter: `ContinuedParagraph`, `ContinuedSectionSubsection`
   (1,277 of them combined - text that belongs to a parent but sits after a
   child), the `Formula*` family (754 formulas), `Definition` /
   `DefinedTermEn`, and `Repealed` (548). Write the findings into
   `docs/source-notes.md` before coding.
2. **Build the citation-path rule** from `<Label>` nesting only, and write it
   down as a documented rule with worked examples in both languages.
3. **Write `portage/parse.py`**: XML in, records out, no database yet. Keep it
   a pure function so it is testable without a build step.
4. **Write `portage/build.py`**: records to `portage.sqlite`, with the
   `sections` and `meta` tables and the FTS5 indexes. Defer `cross_references`
   until open question 1 is settled.
5. **Write the acceptance tests** from CLAUDE.md: round-trip, structure,
   the eight known-citation fixtures, and `tests/spot_checks.md` regeneration.
   Expect the round-trip test to be the hard one, and to drive the decision
   about how `Continued*` elements are ordered.

Deliverable at the end of session 2: `python -m portage.build` produces a
database of the Act and Regulations with `sections` and `meta` populated and the
acceptance tests passing, or a clear written account of which test fails and why.

---

## Open questions for Matt

**1. Internal cross-references are not tagged in the XML. How should we handle them?**

This is the one that needs an answer before session 2 finishes. The XML marks up
references to *other Acts* (`XRefExternal`, 1,112 of them) and to defined terms
(`DefinitionRef`, 1,158), but there are **zero** `XRefInternal` elements. A
reference from one provision to another inside the same Act is plain text:

> `<Text>Notwithstanding subsections 152(4) to (5), the Minister may ...</Text>`

Phase 0's `cross_references` table is mostly about exactly these. So there is a
genuine tension with the CLAUDE.md rule against text heuristics. My reading is
that the rule bans inferring *document structure* from text patterns - which
caused the attribution bugs - and that finding a citation inside a sentence is a
different kind of operation, since a wrong match creates a bad edge in a
reference table rather than misfiling the text of a provision. But that is my
reading of your rule, not a decision I should make. Options:

- **(a)** Extract internal references by pattern, mark every row with
  `extraction_method = 'text_pattern'` so they are never confused with
  structural facts, and report a precision sample in the test output.
- **(b)** Ship Phase 0 with `cross_references` covering only what is tagged
  (`XRefExternal`, `DefinitionRef`), and defer internal references to a later
  phase with its own validation.
- **(c)** Something narrower - e.g. only match the unambiguous, fully-qualified
  forms like `subsection 152(4)` and skip relative ones like `subsection (1)`,
  which need context to resolve.

I lean to **(b) for Phase 0, then (a) as its own phase**, because it keeps the
"mechanical, never judgment" promise clean in the first published artifact. But
it makes `cross_references` much thinner than CLAUDE.md envisions, so it is your
call.

**2. Paragraph counts differ between English and French. Which is authoritative?**

Section and subsection counts match exactly (785 / 785 and 5,351 / 5,351). Below
that they diverge: 13,215 English paragraphs against 12,933 French; 8,468
subparagraphs against 8,219. Most likely this is ordinary bilingual drafting -
French sometimes expresses in one paragraph what English splits in two - but I
have not verified that and I am not going to guess. It matters because
"every record has English and French text, linked by the same citation path"
may not hold at paragraph level for a few hundred provisions. Do you want:
records to exist wherever *either* language has one, with the other side null
and a report listing them; or only where both exist; or should we investigate
the divergence first and decide after seeing real examples? I would suggest
investigating first - it is maybe an hour of work and it tells us whether this
is 280 real mismatches or a counting artifact.

**3. Commercial redistribution - do you want an opinion here, or a lawyer's?**

Justice Canada's terms contain both a standing permission to reproduce
enactments and consolidations "without charge or request for permission"
(not conditioned on non-commercial use), and a separate clause prohibiting
"reproduction of multiple copies of materials on this site ... for the purposes
of commercial redistribution" without written permission. The first clause is
specific to enactments and reads as the governing one for our two instruments.
I have recorded both verbatim in `docs/source-notes.md` and drawn no conclusion.
If the dataset is going to be published under terms that let others use it
commercially, this is worth a real opinion rather than mine.

**4. Snapshot date - confirm `pit-date`.**

I plan to record `snapshot_date = 2026-06-18` (`lims:pit-date`, the point-in-time
date of the consolidation) rather than the date we downloaded the file. That
means the date describes the law, not our fetch. I will additionally store the
retrieval timestamp and `Last-Modified` in `meta` so both are recoverable. Say
if you would rather `snapshot_date` mean the download date.

**5. Should the Regulations be a second `act` value, or a separate build?**

CLAUDE.md puts both instruments in one `sections` table with an `act` column.
Confirming that means `citation_path` is only unique *within* an `act`, not
globally - Regulations section 200 and Act section 200 both exist. I will make
the uniqueness constraint `(act, citation_path)` unless you say otherwise.

---

## Not in Phase 0

Named here so they do not creep in: embeddings, a web front end, an MCP server,
the Finance Canada tax expenditure linkage, and any indicator publishing. All
later phases.
