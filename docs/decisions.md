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
