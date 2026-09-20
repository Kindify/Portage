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

## 2026-09-19 - Spot-check samples exclude rows a checker cannot verify

**Decided (Matt):** `_spot_check_sample` excludes any row whose first sentence is
under 25 characters or begins with a repealed-provision marker
(`[Repealed, ...]` / `[Abrogé, ...]`).

**Why:** seven of the eighty rows in the first hand-check round had to be skipped
as unsearchable. "at the earlier of" appears hundreds of times in the Act and
locates nothing on the official site; a bare repeal note has no text to compare.
Beyond wasting the checker's time, handing someone a row they cannot verify
tempts a tired checker into marking it passed, which would quietly corrupt the
one piece of evidence in this project that does not come from the XML.

**Scale:** the filter removes about 6% of candidate rows for short text and about
1.4% for repeal notes. The sampling pool stays far larger than the sample.

**The checked sample is preserved.** Changing the filter changes which rows the
seed selects, so the four files that were actually verified are kept as
`tests/spot_checks/verified_2026-09_*.md` and the build no longer writes to those
names. `RESULTS.md` refers to them. Regenerating a sample must never orphan the
evidence for a sample already checked.

---

## 2026-09-19 - ITR 1206(1): no label was altered

**Investigated** following a query raised during hand verification (ITR French,
sample row 8) about whether the label read `(1)` or `(01)`.

**Finding: `(1)`, everywhere, and Portage changed nothing.**

- The published French XML gives `<Label>(1)</Label>` for subsection 1206(1).
- The English XML gives `(1)`.
- The official site renders `(1)` - checked directly against
  `laws-lois.justice.gc.ca/fra/reglements/C.R.C.,_ch._945/section-1206.html`.
- The complete set of subsection labels under 1206 is
  `(1) (2) (3) (3.1) (4) (4.1) (4.2) (4.3) (5) (6) (7) (8) (8.1) (9)`. **No
  label in section 1206 contains a zero, in either language.**
- The stored row has `label_raw = '(1)'`, `label_raw_fr = '(1)'`,
  `label_anomaly = 0`, `label_anomaly_fr = 0`, `alignment = 'verified'`.

**No catalogue entry is warranted**, because no normalisation took place - this
was not a case of Portage deriving a path from a malformed label. Recorded here
anyway, since a question asked and answered is worth more in the log than in
nobody's memory.

---

## 2026-09-19 - Tagged cross-references: what the source actually marks up

**Built** `cross_references` from the two reference elements the source tags:
`XRefExternal` (1,423 across both instruments) and `DefinitionRef` (1,259).
Every row carries `method = 'tagged'`. 5,363 rows across both instruments and
both languages.

**`XRefInternal` is effectively absent and that is the headline.** The English
Act, the English Regulations and the French Regulations contain **none**. The
French Act contains **one**. So the source tags no provision-to-provision
references at all, and this table cannot be read as a reference graph. A test
asserts the count so that if Justice Canada starts tagging them, we find out.

**`XRefExternal` resolves to nothing, by design.** It names an *instrument*, not
a provision - "Income Tax Act", "Inquiries Act" - and 1,539 of them point at
instruments this dataset does not hold. A further 546 carry no `link` attribute
at all. Pointing these at a provision would require inventing one.

**`DefinitionRef` carries no attributes whatsoever** - just the term text. There
is no pointer to the defining provision, so resolution is by matching the term
against definition sites in the same instrument, and only a **unique** match
counts. 950 of 2,526 resolve, **37.6%**.

**Resolution rate is reported, not maximised.** Two decisions pushed the rate
*down* and both were right:

1. **Inline definition sites are indexed.** A term is defined in two structural
   forms: inside a `<Definition>` element (2,191 in the English Act) and marked
   up inline in a provision's own `<Text>` with no wrapper (a further 962). ITA
   10.1(5) reads "an *eligible derivative*, of a taxpayer for a taxation year,
   **means** a swap agreement..." - a definition by any reading, simply not
   wrapped. Indexing only the wrapped form left 148 references looking as though
   nothing defined them, which is false. Including both cut unique resolution
   from 51.9% to 38.2%, because more real candidates means more real ambiguity.
2. **Ambiguity is never broken by picking one.** 1,233 references name a term
   defined in several places - "investment tax credit" is referenced 21 times
   and defined in several. Taking the nearest or the first would be a guess
   presented as a result. They stay unresolved with the candidate paths listed.

**Cross-instrument resolution is not attempted.** 81 of 97 unresolved English
Regulations references match a definition in the *Act* (35 uniquely), because
the Regulations lean on the Act's definitions. Resolving them needs the prose
signal - "as defined in subsection 207.5(1) **of the Act**" - which is pattern
extraction, and belongs with the rest of that work rather than smuggled in here.

**Unresolved rows are kept**, with a stated reason and, where ambiguous, the
candidate paths, in `data/unresolved_tagged_references.csv` against a fixture.

---

## 2026-09-19 - Reference resolution: three states, and candidates are kept

**Decided (Matt).** Supersedes the entry above it, which resolved a reference to
a single target or not at all. The rule is now written out in full in
`docs/reference-rule.md`, and was written before it was implemented.

**A reference has three possible outcomes, not two.** `unique` (one candidate
definition), `ambiguous` (several) and `unresolved` (none). Every candidate gets
a row in **`definition_ref_candidates` (ref_id, definition_id)**, and the
reference itself never picks one.

**Why `ambiguous` is an answer and not a failure.** A term is often defined
several times in the same instrument, each definition governing a different
Part or purpose - "person" is defined in **15** places in the English Act,
"transaction" and "beneficiary" in 9 each. Which one governs a particular
sentence is a scope question, and CLAUDE.md puts scope outside the data. Storing
all the candidates lets a consumer apply its own scope rule in the open, instead
of inheriting a silent guess from us. Collapsing this into "resolved / not
resolved" would have thrown away the most interesting thing the table knows.

**Matching is exact and nothing looser:** `normalise_term` (NFC, collapsed
whitespace, case preserved) then string equality against `defined_term_en` or
`defined_term_fr`, on definition records in the same instrument that carry text
in that language.

**Known gap, kept visible.** Candidates are `<Definition>` records only. The
source also defines terms inline - `<DefinedTermEn>` inside a provision's own
`<Text>`, 962 of them in the English Act, e.g. ITA 10.1(5) "an *eligible
derivative* ... **means** a swap agreement". Those are not candidates under this
rule, so roughly 150 references whose term really is defined somewhere come out
`unresolved`. Stated in `docs/reference-rule.md` and catalogued rather than
papered over. Extending the rule to inline sites is a decision for later; it
would raise coverage and lower the `unique` share, because more real candidates
means more real ambiguity.

**Terms defined more than once are now catalogued in their own right** -
`data/terms_defined_more_than_once.csv`, 249 distinct terms - because that is a
finding about the Act, not merely the reason a reference failed to resolve.

**`XRefExternal` resolves to nothing, and the rule says why.** It may resolve
only where the target is the ITA or Regulations *and* the reference names a
provision. The second condition is never met: the element's text is always an
instrument *title*. Of 2,837 elements exactly one contains anything resembling a
provision number, and that is `The Loans Act, 1983(2)` - part of a title.

**`XRefInternal`: stored, noted, not resolved.** There is exactly one in the
whole corpus, in the French Act at `93(5.2)(a)`, and its text is `51`. It is
left unresolved because resolving it would be **wrong**: the surrounding prose
reads "l'article 51 de la *Loi de 2012 apportant des modifications techniques
concernant l'impôt et les taxes*" - section 51 of a different Act. An element
named `XRefInternal` holding a bare section number looks exactly like a
reference to the current instrument, and the single case in the corpus is the
counter-example to that assumption. It is the cheapest possible warning about
what pattern extraction will face.

**Numbers:** 5,364 references. `DefinitionRef` 2,526 - unique 1,237 (49.0%),
ambiguous 801 (31.7%), unresolved 488 (19.3%). `XRefExternal` 2,837, all
unresolved. `XRefInternal` 1, unresolved. `definition_ref_candidates` holds
3,888 rows; the most candidates for one reference is 15.

---

## 2026-09-19 - Inline definition sites and other-instrument candidates

**Decided (Matt).** Two additions to the reference rule, both recorded in
`docs/reference-rule.md` before implementing.

**1. Inline definition sites are now candidates**, `candidate_kind =
'inline_defined_term'`; existing ones are `'definition_record'`.

The precondition Matt set was that they be identifiable without matching prose.
They are: an inline site is a `DefinedTermEn` / `DefinedTermFr` element with no
`<Definition>` ancestor. Element nesting alone - nothing looks for "means" or
any other wording, so the ban on text heuristics is untouched. There are 964 in
the English Act, 854 in the French Act, 431 and 373 in the Regulations.

**What it did to the numbers**, over the 2,526 `DefinitionRef` rows:

| Candidate classes | unique | | ambiguous | unresolved |
|---|---|---|---|---|
| `definition_record` only | 1,237 | 49.0% | 801 | 488 |
| `inline_defined_term` only | 341 | 13.5% | 568 | 1,617 |
| both (in force) | 950 | 37.6% | 1,207 | 369 |

Of the 950 unique resolutions, 888 land on a definition record and 62 on an
inline site.

**The unique share fell from 49.0% to 37.6% and that is the right direction.**
Unresolved dropped from 488 to 369: 119 references that appeared to have no
definition anywhere turned out to have one. Most became `ambiguous` rather than
`unique`, because the term was already defined elsewhere as well. A term defined
in both forms has two real definitions. Reporting that is worth more than a
higher percentage bought by ignoring one of them.

**2. Other-instrument definitions are candidates, never resolutions.**
`candidate_scope` is `'same_instrument'` or `'other_instrument'`, and resolution
is computed over same-instrument candidates alone. 691 references carry
other-instrument candidates across 2,384 candidate rows.

**Why they cannot resolve:** whether a definition in the Act governs a word used
in the Regulations is a question about how the two instruments relate, and the
answer is normally carried in prose the markup does not encode - "as defined in
subsection 207.5(1) **of the Act**". Resolving from a term match alone would be
a legal conclusion drawn from a string comparison.

**3. The `XRefInternal` case is now a fixture for the Phase 1 grammar.**
`test_bare_section_number_never_resolves` pins ITA French `93(5.2)(a)`: a bare
section number with no instrument qualifier never resolves.

It is worth keeping because every signal in the markup points the wrong way. The
element is called `XRefInternal`. It sits in the Income Tax Act. Its content is
a bare section number, and section 51 of the Income Tax Act exists. Only the
surrounding prose - "de la *Loi de 2012 apportant des modifications
techniques*" - says it means another Act. A rule that trusted the markup would
have produced a link that is wrong, confident and invisible. The reference
grammar Phase 1 must write will meet that shape constantly.

**Totals now:** 5,364 references. `DefinitionRef` 2,526 - unique 950, ambiguous
1,207, unresolved 369. `XRefExternal` 2,837, all unresolved. `XRefInternal` 1,
unresolved. `definition_ref_candidates` holds 10,459 rows: 3,888 same-instrument
definition records, 4,187 same-instrument inline sites, 894 and 1,490
other-instrument.

---

## 2026-09-19 - The tax expenditure report: HTML is the source, the CSV is the check

**Decided** after inspecting the real pages (`docs/source-notes.md` section 7).

**Parse the HTML pages.** The open.canada.ca release is under the Open
Government Licence and is genuinely useful, but it is a *summary of cost
information*: `MEASURE, GROUP, SUBJECT, CATEGORY, TAX, DETAILS` and eight year
columns. It has no description, no objective, and **no legal reference**. The
field Phase 1 exists to use is only in the web pages. The CSV becomes an
independent check on the cost figures - valuable precisely because Finance
produced it and we did not.

**A measure is a table the Part 3 index links to** - not a table with a caption
id. The Part 7 appendix, *Additional Information on Relevant Government Programs
by Subject*, has no caption id in English but does in French, with 17 body rows,
so it passes every structural test for a measure. Counting index links gives 229
in both languages and excludes it. The shape test would have silently added a
230th "measure" in French only.

**Never key a French field on its label.** The field set is 17 on every measure
in both languages, but the French labels vary 25 ways for those 17 fields:
non-breaking spaces, real synonyms (`Thème`/`Objet`, `Source des données`/`Source
de données`, `régime`/`système fiscal de référence`), the English acronym in the
French edition (`Code CCOFOG 2014`), and two measures where the *Tax* field is
labelled `Direction de la politique de l'impôt` - a branch of the department,
not a field name. Every variant sits at one fixed row position, so position is
the key and the label is recorded alongside.

**The part number is provenance, not a join key.** Part 4 holds 49 measures in
English and 99 in French. Measures are alphabetical within each language, so the
page boundaries land in different places - the Phase 0 definition problem, one
level up.

**Cost token classification comes from Finance, not from us.** The metadata CSV
documents the symbols: `n.a.`/`n.d.` "No data available to support a meaningful
estimate or projection"; `–` "Tax expenditure not in effect"; `X` "Not published
for confidentiality reasons"; `S`/`F` under $500,000. `X`, a bare U+002D hyphen
alongside the U+2013 en dash, and empty cells all occur in the tables and none
was anticipated in CLAUDE.md's list. Having the publisher's own legend means
`cost_tokens.csv` starts from an authority rather than a guess.

---

## 2026-09-19 - Phase 1 step 3: the measure tables

**The snapshot is committed and the build never fetches.** `data/finance/2026/`
holds the ten HTML pages and the four open data CSVs, 3.4 MB, with
`MANIFEST.json` recording SHA-256, byte counts, source URLs, both licences and
the retrieved date. It is a fixed dated edition under the Open Government
Licence, and canada.ca rejects scripted fetches often enough that a build
depending on a live fetch would not be reproducible. `.gitignore` excludes
`data/` file-by-file, because git cannot re-include a path inside an excluded
directory.

**Correction to the note of earlier today:** curl *can* fetch canada.ca, with a
full browser header set and `--retry-all-errors`. The rejections are
intermittent, not systematic. The earlier claim was true of the attempts made,
not of the technique.

**Fields are keyed by row position.** 17 fields on every measure in both
languages; English labels stable, French varying 25 ways including two measures
that label the Tax field `Direction de la politique de l'impôt`. Every variant
sits at one fixed slot. `data/field_label_variants.csv` is diffed against a
fixture, so a new label at any position fails the build.

**Cost tokens are catalogued as symbols, not values.** Listing all ~1,600
distinct numbers would churn the fixture on every edition while hiding the one
thing the catalogue exists to catch - an unannounced new symbol. Numbers are one
aggregate row. `legend_match` separates what Finance documents (`legend`) from
what we inferred (`variant` for the bare hyphen and `n.d`; `portage` for the
empty cell).

**Repealed citations get their own status.** `not_in_consolidation` - 33 of
them. The report states the law as of 31 December 2025, the Act consolidation is
18 June 2026, and a six-month gap between two dated documents is not a parsing
failure. Stated in README.

**The bilingual join is by reference set plus cost values, never position.**
193 of 229 measures join uniquely; 36 do not and are catalogued in
`data/measure_join_gaps.csv`, with both language records surviving as singles.
Most failures are measures whose references do not resolve and whose costs are
all symbols, leaving nothing language-independent to join on. Adding a name or
order tie-breaker would be judgment, and CLAUDE.md puts judgment outside the
data.

**Three grammar bugs the French edition exposed**, each of which produced a
plausible wrong answer:

1. French writes a paragraph label without its opening bracket - `alinéa
   118(1)d)` where English writes `paragraph 118(1)(d)`. Phase 0's citation
   paths use the English form, so French reference text is normalised before
   extraction. Until it was, the two editions never produced the same reference
   set and only 152 measures joined.
2. `section 146.1Canada Education Savings Act` read as the provision `146.1C`.
3. `section 258 (rebate)` read as the provision `258(rebate)`.

**Beneficiary counts are populated only where unambiguous.** The field is prose.
75 of 458 rows carry a parsed year and count; the rest keep their raw text with
NULL count. A half-read sentence is worse than an honest blank.

**Validated against Finance's own numbers.** 559 cost cells have a counterpart
in the open data CSV and **all 559 match**. This is the only check on Phase 1's
figures that does not read the pages we parsed.

---
