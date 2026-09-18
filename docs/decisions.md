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

## 2026-09-18 - Definitions are keyed by their defined term, not by position

**Decided (Matt):** `citation_path` for a definition is the subsection path plus
the defined term: `248(1)"active business"`. English term preferred, French term
where English is absent, ordinal only where neither exists. Fallbacks are
catalogued in `data/definition_key_fallbacks.csv` against a committed fixture.

**Why - the evidence that settled it.** Session 2 used a document-order ordinal.
Session 3 checked whether it could serve as a bilingual key. **It cannot: each
language file alphabetises its definitions in its own language.** In 248(1),
ordinal 1 is "absorbed capacity" in the English file and "tax shelter"
(*abri fiscal*) in the French. Ordinal 2 is "active business" and "separation
agreement". Joining on position would have mis-paired almost every definition in
the Act.

**Two bugs found while implementing it**, both worth recording because both
produced plausible-looking wrong answers:

1. **A descendant search returns the wrong term.** `.//DefinedTermEn` finds the
   first English term *anywhere* in the definition, which is usually a
   cross-reference to a different definition quoted in the body. It keyed
   "action admissible" to a phrase from its own body text and collided three
   definitions in 135.2(1) onto one path. The term must be read from the direct
   children of the definition's own `<Text>`.
2. **But the equivalent term is not in the opening `<Text>`.** For a definition
   with paragraphs, the "(english term)" is published after the last paragraph.
   Restricting to the opening `<Text>` dropped the English equivalent on more
   than half of them - 984 of 2,202 in the French file, against 2,078 when the
   whole subtree is searched. So: own term from the opening `<Text>`, equivalent
   from the last match in the subtree, nested definitions excluded.

**Normalisation** is Unicode NFC plus collapsed whitespace, nothing more. Case
preservation and quote handling were measured against the real files and changed
the join rate by exactly zero, so neither is applied.

**Duplicate terms are real.** 44.1(1) defines "eligible small business
corporation share" twice, with different text. Duplicates get a `#2` suffix,
`label_anomaly = 1` and a catalogue row, rather than one of them being lost to
the uniqueness constraint. The same mechanism covers duplicate *labels*, which
also occur: the French 142.6(8)b) numbers two subparagraphs `(iv)` where the
English has `(iv)` and `(v)` - a typo in the published XML.

---

## 2026-09-18 - alignment_unverified: joining on a shared label is not evidence

**Decided:** where a provision's set of children differs between the two
language files, the children that happen to share a path are kept as one row but
marked `alignment_unverified = 1` and catalogued in
`data/alignment_unverified.csv`. Consumers wanting only verified pairs filter
`bilingual_gap = 0 AND alignment_unverified = 0`.

**Why.** Joining on `citation_path` is not by itself enough to honour "never
force alignment". ITA 51(1) is the proof: English lists paragraphs (a) to (f),
French lists a) to d), and the join produced four *paired* rows -

```
51(1)(a)  EN "a capital property of the taxpayer that is another share..."
          FR "sauf pour l'application des paragraphes 20(21) et 44.1(6)..."
```

- which are not translations of each other at all. English breaks the opening
conditions into lettered paragraphs; French leaves them in the subsection text
and letters only the rules. The label `(a)` is the same on both sides and means
something different. Four silently wrong pairs, exactly the mis-attribution this
project exists to prevent.

**The test is structural, not semantic.** It compares the *set of child labels*
under each parent. It makes no judgment about whether two texts correspond - it
only marks where the label alone is not evidence that they do. Addressable
children and non-addressable fragments are compared separately, because a
subsection whose continued-text fragments differ in number says nothing about
whether its paragraphs correspond.

**This is a flag, not a decision.** Marking a pair unverified asserts nothing. It
records that we do not know, which is the honest state. Whether those 2,408 rows
should instead be split into single-language rows is Matt's call - see PLAN.md.

**Scale:** 125 provisions have differing addressable child sets, covering 333
addressable rows; fragments add the rest, for 2,408 in total. 31,888 bilingual
pairs are verified.

---

## 2026-09-18 - Uniqueness is tested on the shipped citation_path, never on a proxy

**Decided (Matt):** every uniqueness test runs against the `citation_path` as it
is written to the database. No test may assert uniqueness of a structural proxy -
a label tuple, an element path, a pre-disambiguation key - and infer that the
shipped column is therefore unique.

**Why.** The proxy and the shipped value can diverge, and when they do the test
passes while the database is wrong. This session had two live examples of exactly
that shape: a test that measured "English terms duplicated within the same parent
element" returned zero, while the shipped paths collided three ways in the
English file and eleven in the French, because the parent element and the parent
*path* are not the same thing. Uniqueness is a property of the column that ships.
Test the column that ships.

**In practice:** `tests/test_structure.py::test_citation_paths_are_unique` groups
on `(act, citation_path)` in SQL, against the built database, after every
disambiguation rule has been applied. The `UNIQUE (act, citation_path)`
constraint is a second line of defence, not the test.

---

## 2026-09-18 - Duplicate labels are the source's; disambiguated paths are ours

**Decided:** where the published XML repeats a label or a defined term within one
provision, the duplication is recorded as a defect **in the source**, and the
`#2` suffix that separates the records is recorded as **ours**. Both facts are
stated in README's Known limits, so nobody reads `142.6(8)(b)(iv)#2` as a
citation Justice Canada would recognise.

**The cases.** The French file numbers two subparagraphs `(iv)` in 142.6(8)b)
where the English has `(iv)` and `(v)` - a numbering error in the published
consolidation. 44.1(1) defines "eligible small business corporation share" twice,
which is not an error but does mean the term alone does not identify a provision.
Six duplicate labels and five duplicate terms in total.

**Why it matters that the distinction is explicit.** We do not correct the
source: `label_raw` holds `(iv)` verbatim on both records and the text is
untouched. But we cannot ship two rows with the same key either. So the suffix is
an artefact of this dataset, not of the law, and a reader who cites
`142.6(8)(b)(iv)#2` to a court would be citing something that does not exist. The
README says this in as many words.

---

## 2026-09-18 - Split divergent addressable rows; flag only fragments

**Decided (Matt, option (c)):** where a provision's set of children differs
between the two language files, **addressable** children that share a path are
**split** - the English record keeps the path, the French record moves to
`<path>~fr`, both carry `bilingual_gap = 1`, and each points at the other through
`same_path_counterpart`. **Fragments** stay joined and carry
`alignment_unverified = 1`.

**Why the asymmetry.** Addressable rows are the ones a person cites. A citation
that returns two unrelated texts is the failure this project exists to prevent,
and 51(1)(a) - an opening condition in English, a rule in French - is exactly
that. Fragments are continued text and formula groups: not citable, and each
language round-trips in its own order, so the risk is smaller and a flag is
proportionate.

**Verified:** no row under 51(1) carries `text_en` and `text_fr` together, which
is asserted by a test rather than checked once by hand. 51(1) *itself* stays
joined - the subsection does correspond in both languages; only its internal
division differs.

The exact criterion is written out in `docs/citation-path-rule.md` section 6.

---

## 2026-09-18 - Range connectors apply at section level too

**Decided:** the ` et ` -> ` and ` and ` à ` -> ` to ` normalisation applies to
section labels as well as to labels below section level.

**Why:** the Regulations number sections `3000 to 3002` / `3000 à 3002` and
`7302 and 7303` / `7302 et 7303`. The Act has no section-level ranges, so the
original rule did not cover them, and the two languages failed to join - the
provisions appeared French-only.

**How it was caught:** the section-count test expected 499 and found 501. Worth
noting because the test that caught it was written for a different purpose
entirely, and because the failure was visible only once a *second instrument*
exercised the rule. A rule validated against one document is validated against
one document.

---

## 2026-09-18 - Alignment status: positional joins are named, not hidden

**Decided (Matt):** every row records how its two languages came to be together,
in an `alignment` column: `verified`, `positional`, `unverified`, `split`,
`single`. Fragment pairs joined on an ordinal this project assigned are
`positional`, explicitly distinct from `verified`.

**Why.** "Both languages are present" is not one fact. A row where English
`87(4)` meets French `87(4)` is joined on a label read from the source. A row
where English `6(1)(f)~c1` meets French `6(1)(f)~c1` is joined on an ordinal we
invented, and rests on the assumption that both languages put their continued
fragments in the same order. The source never says they do. It is usually true,
and the consequences are smaller than for a citable provision, but a reader is
entitled to know which joins rest on a key and which rest on counting.

This is the same species of assumption that ordinals failed at for definitions,
where each file turned out to alphabetise in its own language. That failure is
the reason to name this one rather than leave it implicit.

**Definitions are excluded** from the positional class when they have a defined
term, because the term is a real key and is separately tested for symmetry. Only
the handful falling back to a `~d` ordinal are positional. Correcting this also
fixed a mistake in the divergence test: it had been comparing definition *sets*
between languages and flagging 2,369 definitions as unverified, when a subsection
holding different definitions in each language says nothing about whether a term
present in both is the same definition.

**Distribution:** verified 42,181, positional 2,900, single 2,817, split 938,
unverified 196. `data/alignment_positional.csv` lists the positional rows against
a committed fixture.

---

## 2026-09-18 - The spot-check results file is never overwritten by the build

**Decided (Matt):** `tests/spot_checks/RESULTS.md` is generated pre-filled with
all eighty citations if it does not exist, and **never** regenerated afterwards.

**Why:** it is the only check in the project that does not compare the XML
against itself. Every automated guard reads the same four files the build reads;
if those were misread the same way twice, nothing here would catch it. A build
that clobbered the hand-recorded results would destroy the one independent piece
of evidence the project has.

**And the README does not claim it is done until it is.** The Methods section
carries an explicit "not yet completed" status rather than an empty promise.

---
