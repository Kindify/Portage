# Design decisions

One entry per decision, newest last. Every entry says what was decided, when,
and why - so that a future session (or a future person) does not have to
re-argue it.

---

## 2026-09-18 - Repository layout and ignored files

**Decided:** `portage/` package, `tests/`, `docs/`, with source downloads in a
gitignored `data/` directory and `portage.sqlite` gitignored as a build
artifact.

**Why:** the build must be reproducible from documented source URLs rather
than from files checked into the repository. Committing the source data would
also mean redistributing Justice Canada's material from a mirror, which we do
not want to do implicitly. The database is output, not input.

---

## 2026-09-18 - Python 3.12, managed by uv

**Decided:** pin Python 3.12 and manage both the interpreter and the
dependencies with `uv`. The interpreter and every library live in a project-local
`.venv/`, which is gitignored.

**Why:** the machine only had the Apple-supplied Python 3.9.6, which is below the
3.11+ floor in CLAUDE.md and is past end-of-life (no more security fixes). The
Apple Python is a system component and must not be modified or installed into.
uv installs its own standalone Python build, so nothing outside this project
changes, and it records exact versions so a stranger can reproduce the
environment from the commands in the README. 3.12 rather than 3.13+ because it
is the version with the longest track record of working wheels for pandas,
pyarrow and lxml.

**Verified at the time:** Python 3.12.14, pandas 3.0.6, pyarrow 25.0.1,
lxml 6.1.3, pytest 9.1.1, bundled SQLite 3.53.1 with FTS5 compiled in (checked -
Phase 0 needs FTS5 and not every SQLite build has it).

---

## 2026-09-18 - Source: Justice Laws XML, not A2AJ

**Decided:** parse Phase 0 from the official Justice Laws XML
(`laws-lois.justice.gc.ca`), for both instruments in both languages. A2AJ's
`canadian-laws` dataset was inspected and rejected for this purpose.

**Why:** A2AJ's records stop at the section. Its `unofficial_sections_en` field
maps section numbers to Markdown strings, and none of its 767 keys reference a
subsection, paragraph or clause - the whole of section 87 is one flat string.
Recovering `87(4)` would require splitting prose on number patterns and reading
headings out of `**bold**`, which CLAUDE.md bans and which caused three
attribution bugs during scoping. History notes are stripped entirely. The
structure is not hidden, it is gone. The Justice Laws XML has every level as a
real element, plus `MarginalNote` headings, `HistoricalNote` amending notes, and
`lims:pit-date` on the root. It is also the upstream source A2AJ itself scraped,
and a smaller download (38.6 MB vs 185 MB).

**Not a criticism of A2AJ:** their dataset is built for full-text and
language-model use, where flat Markdown is the right shape. It is simply the
wrong shape for a citation-addressable dataset.

**Evidence:** `docs/source-notes.md`, written the same day, with raw records,
element counts and file hashes.

---

## 2026-09-18 - Snapshot date will be the consolidation date, not the download date

**Decided (pending Matt's confirmation, open question 4 in PLAN.md):**
`snapshot_date` = `lims:pit-date` from the XML root = `2026-06-18`. The
retrieval timestamp and HTTP `Last-Modified` go into `meta` as separate fields.

**Why:** the point of the column is to tell a reader which version of the law
they are looking at. The download date only tells them when we happened to run
a script. Both are worth keeping, but only one belongs in `snapshot_date`.

---

## 2026-09-18 - Cross-references: Phase 0 ships tagged references only

**Decided (Matt):** Phase 0's `cross_references` table contains only references
that are **tagged as elements in the source XML** - `XRefExternal` (1,112 in the
Act, references to other statutes, carrying a `link` attribute) and
`DefinitionRef` (1,158, references to defined terms). Every row carries
`method = 'tagged'`.

Internal references - one provision citing another inside the same instrument,
such as "Notwithstanding subsections 152(4) to (5)" - are **deferred to Phase 1**
as a **separate table** with `method = 'extracted'`.

**Why:** the Justice Laws XML contains zero `XRefInternal` elements, so internal
references exist only as untagged prose. Extracting them means pattern-matching
text, and Phase 0's promise is that everything in it is mechanical and
structural. Keeping the two in separate tables with an explicit `method` column
means a consumer can never mistake a pattern-matched edge for a structural fact,
and Phase 1 can be validated on its own terms without weakening Phase 0.

**Consequence to be honest about:** Phase 0's `cross_references` is much thinner
than CLAUDE.md's Phase 0 scope envisions. That is a deliberate narrowing, agreed
with Matt, and the README must say so rather than let a reader assume the table
is complete.

---

## 2026-09-18 - Bilingual alignment: join on citation_path, never force

**Decided (Matt):** English and French records are joined on `citation_path`. A
path present in only one language keeps its record, with the other language's
text `NULL` and a `bilingual_gap = 1` flag. Alignment is never forced - records
are never paired by position, order, or similarity.

**Why:** investigated and evidenced in `docs/source-notes.md` section 3. The two
language versions genuinely structure some provisions differently: English
51(1) has eight lettered paragraphs where French has six, and the contents are
offset rather than relettered, because English breaks the opening conditions into
paragraphs while French leaves them in the subsection's opening text. Pairing by
position would silently attach English text to unrelated French text - the exact
mis-attribution failure mode this project is built to avoid.

**Expected magnitude (Act):** 28,289 rows, of which 27,348 (96.67%) have both
languages and **941 (3.33%) carry `bilingual_gap = 1`**, spread across 157 of 785
sections. The acceptance tests should assert this count, not drive it to zero.

---

## 2026-09-18 - Redistribution terms: record verbatim, stay non-commercial

**Decided (Matt):** quote the Justice Canada reproduction clause and the Open
Government Licence terms verbatim in the README. The project stays
non-commercial. The interaction between the standing permission to reproduce
enactments and the prohibition on commercial redistribution of site materials is
logged as an **open legal question, not a blocker**.

**Why:** the obligations we can meet are concrete and we meet them - due
diligence on accuracy (the acceptance tests), no representation as an official
version, and attribution with non-endorsement. What a *downstream commercial*
user may do is a question for someone qualified to answer it, and not a reason to
delay publishing a non-commercial dataset.

---

## 2026-09-18 - meta stores consolidation_date and retrieved_date separately

**Decided (Matt):** `meta` carries `consolidation_date` (from `lims:pit-date` in
the XML root, `2026-06-18`) and `retrieved_date` (when we fetched the file) as
two distinct fields.

**Why:** they answer different questions. `consolidation_date` tells a reader
which version of the law they are looking at; `retrieved_date` tells them when
our copy was made. Collapsing them loses one of the two. This supersedes the
earlier entry in this file that proposed a single `snapshot_date`.

---

## 2026-09-18 - Uniqueness constraint is (act, citation_path)

**Decided (Matt):** `UNIQUE (act, citation_path)`, not `UNIQUE (citation_path)`.

**Why:** both instruments live in one `sections` table and both have a section
200. Citation paths are only unique within an instrument.

---

## 2026-09-18 - citation_path uses the English label form in both languages

**Decided (Matt):** `citation_path` is built with English label conventions for
records in both languages - `(a)` rather than the French `a)`. The raw label as
published is preserved per language in `label_en` and `label_fr`.

**Why:** the citation path is the join key between the two languages, so it has
to be identical on both sides; one convention had to win, and English bracketing
is the form used in most citation practice. Storing the native labels separately
means nothing published is lost - a French-language consumer can still render
`b)` as Justice Canada prints it.

**Normalisation rules this implies** (all from `<Label>` only, never from body
text): bracket bare French labels (`a)` -> `(a)`); translate range connectors in
labels (`et` -> `and`, `à` -> `to`), which alone resolved 41 of 42 subsection
mismatches; strip trailing periods. The 13 malformed source labels catalogued in
`docs/source-notes.md` section 3 are handled explicitly, not by a general rule.

---

## 2026-09-18 - Anomalies are catalogued, never counted

**Decided (Matt):** the build writes `data/bilingual_gaps.csv` and
`data/label_anomalies.csv`. Tests compare those files against committed fixtures
in `tests/fixtures/` and **fail on any difference**. Changing a fixture is a
deliberate commit with a stated reason.

**Never assert a bare number.** A test that says `assert len(gaps) == 941` passes
while a gap silently moves from one provision to another. A test that diffs the
catalogue catches that. The number in `docs/source-notes.md` is descriptive
prose, not a contract.

**Session 2 scope note:** only `label_anomalies.csv` can be produced this
session, since bilingual gaps need the French file. `bilingual_gaps.csv` and its
fixture arrive in session 3 with French. The catalogue-and-diff mechanism is
built now so the second one slots into a pattern that already exists.

---

## 2026-09-18 - Label normalisation: derive the path, never alter the source

**Decided (Matt):** `citation_path` is derived from `<Label>` through a
documented normalisation. The label as published is preserved verbatim in
`label_raw`. Where normalisation had to do anything beyond the ordinary
bracketing, `label_anomaly = 1` and the case appears in
`data/label_anomalies.csv`.

**The rule, in order of application.** Input is the `<Label>` element's text and
nothing else - never body text, never position, never a number pattern.

1. **Collapse whitespace.** Internal runs of whitespace (including the
   non-breaking spaces the French file uses after `«`) become a single space;
   leading and trailing whitespace is stripped.
2. **Section level: take the label bare.** `87` stays `87`; `110.6` stays
   `110.6`. Strip a single trailing period if present.
3. **Below section level: strip stray quotation marks.** Remove leading or
   trailing `"`, `"`, `«`, `»` and any space left behind. This is what turns the
   English `"(a)` and the French `« a)` at 181.7 and 190.21 into `(a)`.
   **Sets `label_anomaly = 1`.**
4. **Range connectors.** Within a label, ` et ` becomes ` and `, and ` à `
   becomes ` to `, so the French `(10) et (11)` and `(14.01) à (14.1)` match the
   English `(10) and (11)` and `(14.01) to (14.1)`. This alone resolved 41 of 42
   subsection mismatches. Not an anomaly - it is ordinary bilingual form.
5. **Bracket bare labels.** A token ending in `)` but not starting with `(`
   becomes bracketed: the French `a)` becomes `(a)`, `b.1)` becomes `(b.1)`.
   Applied to each token in a range as well. Not an anomaly.
6. **Repair unmatched brackets.** A label with an opening `(` and no closing `)`
   gets the closing bracket added: the English `(b` at 12.4 becomes `(b)`.
   **Sets `label_anomaly = 1`.**
7. **A label that is still not a recognisable form after all of the above** is
   kept as-is in the path, `label_anomaly = 1`, and listed in the catalogue for
   a human to look at. Nothing is dropped and nothing is guessed.

**What this rule never does:** it never changes `<Text>`. Source text is
reproduced exactly as published, including the `[Repealed, ...]` markers, which
are inline inside `<Text>` and are carried through untouched. Normalisation
applies to the derived key only.

**Why derive rather than correct:** the malformed labels are defects in the
published XML, not in the law. Correcting the source would make our copy differ
from what Justice Canada publishes, which breaks the round-trip test and the
promise that text is reproduced exactly. Deriving a clean key while keeping the
raw label means both the citation works and the source is intact, and
`label_anomaly` tells a reader exactly where we had to do something.

---

## 2026-09-18 - Continued text: non-addressable rows, not a column

**Decided:** text that belongs to a unit but appears *after* one of its children
(`ContinuedParagraph`, `ContinuedSectionSubsection`, `ContinuedSubparagraph`,
`ContinuedClause`, `ContinuedDefinition`) is stored as its **own row** in
`sections`, with `is_addressable = 0`, `level = 'continued'`, and a
`citation_path` formed from the parent's path plus a non-citable suffix
(`6(1)(f)~c1`, `~c2`, ...). Unlabelled `Definition` elements and the `Formula`
family are handled the same way.

**Why a row and not a column.** A `text_continued` column assumes continued text
always trails its unit. It does not. Of the 1,337 units in the English Act that
contain continued text, **802 have it interleaved between structural children**,
not trailing. ITA 6(1)(f) is typical - its child sequence is `SSSSCSCS`, and the
fragments read "to or under which the taxpayer's employer has made a
contribution..." and "exceeds", sitting between subparagraphs (iii.1) and (iv)
and between (iv) and (v). They are connective tissue in the middle of a list. A
single column would have to either reorder them to the end, which corrupts the
text, or drop them, which breaks the round-trip. 131 units have two such
fragments, 21 have three, and one has five.

**Why `is_addressable`.** Continued text is not an addressable unit of the Act -
nobody cites `6(1)(f)~c1`, and CLAUDE.md's `sections` table is defined as one row
per addressable unit. The flag keeps both promises at once: citation queries and
the structure test filter `is_addressable = 1` and see exactly the addressable
units; the round-trip test reads every row in `order_index` order and reproduces
the source. The `~` suffix is deliberately not valid citation syntax so it can
never be mistaken for one.

**Flagged for Matt's review.** This adds `is_addressable`, `label_raw` and
`label_anomaly` to the column list in CLAUDE.md. The alternative was a second
table, which keeps `sections` literally one-row-per-addressable-unit but makes
the round-trip test a two-table merge rather than the single ordered read
CLAUDE.md describes. I went with the flag because it matches the test as written.
Say if you would rather have the separate table.

---

## 2026-09-18 - Two refinements to the label rule, found by running it

**Decided:** added rule 2b (a bare numeral is the correct label form at
subsubclause level) and rule 3b (remove whitespace immediately inside brackets,
so `(b )` normalises to `(b)` instead of splitting into two tokens). Both are
written into `docs/citation-path-rule.md`.

**Why:** the first run of the rule as specified produced 176 label anomalies.
150 of them were subsubclauses labelled `1`, `2`, `3` - the ordinary published
form for that level, not a defect. A catalogue that is 85% false positives is one
nobody reads, which defeats the point of cataloguing rather than counting. After
the refinement the English Act yields 26 anomalies, all genuine.

**Note on process:** the rule was written first and then corrected against
reality, which is the right way round. The correction is recorded here rather
than quietly folded into the spec.

---

## 2026-09-18 - A round-trip test that shares code with the parser proves nothing

**Decided:** `parse.source_text()` reconstructs the source by a deliberately
different method from the parser - a mixed-content walk over `.text` and `.tail`
- and `tests/test_roundtrip.py` carries a second check that accounts for every
character against the raw XML by a third route.

**Why this exists.** The first version of the round-trip passed exactly, with
zero normalisation, and it was wrong. Both the parser and the round-trip target
skipped every `<Label>` element unconditionally. That is right for a Label on a
subsection, which is stored in a column - but wrong for the `<Label>` and
`<FormulaTerm>` on a `FormulaDefinition`, which carry the variable name that
introduces the sentence. The database was missing 93 characters of formula
variable names, and the test could not see it because it had the same blind spot.

An independent character accounting against the raw file caught it. The lesson is
general enough to write down: **a verification that reuses the logic it is
verifying only proves the logic is self-consistent.** Every acceptance test in
this project should be able to say what it would catch that the parser could get
wrong.

**Second fix from the same investigation:** the walker now captures any subtree
containing nothing it tracks structurally (`_is_text_leaf`), rather than
recursing into it and emitting nothing. That is a structural test, not a list of
element names, so an element type nobody anticipated is captured rather than
silently dropped.

---

## 2026-09-18 - Schedules are not in the sections table

**Decided:** `sections` covers the `<Body>` of the Act - 763 sections. The file
holds 785 `Section` elements; the other 22 are inside `<Schedule>` elements
titled "RELATED PROVISIONS" (16) and "AMENDMENTS NOT IN FORCE" (6).

**Why:** those are appended material, not the enacted text, and they carry a
different meaning - amendments not in force are, by definition, not the law as
consolidated. Including them in the same table as enacted provisions would let a
reader retrieve a provision that is not in effect without noticing.

**Flagged for Matt.** There is a third schedule, "Listed Corporations", which
contains no `Section` elements and is genuinely part of the Act. It is currently
not captured at all. See PLAN.md.

---
