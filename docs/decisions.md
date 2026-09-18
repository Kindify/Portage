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
