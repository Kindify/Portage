# Portage (working title)

A bilingual, open dataset that makes Canada's federal **Income Tax Act**
(RSC 1985, c 1 (5th Supp)) and the **Income Tax Regulations** (CRC, c 945)
navigable at the subsection level.

> This dataset makes provisions navigable. It does not interpret them and is
> not legal advice.

## Status

**Phase 0 and Phase 1 complete**, released as `v0.1.0` and `v0.2.0`.
**Phase 2 in progress**: the indicator views are built; the temporal-scope
extraction is not. `python -m portage.build` produces `portage.sqlite`:

| | |
|---|---|
| Income Tax Act | 37,136 rows |
| Income Tax Regulations | 11,896 rows |
| total | **49,032 rows**, 41,817 addressable provisions |
| consolidation date | 2026-06-18 |
| round trip, all four files | **exact, zero normalisation** |
| tax expenditure measures | 229 per language, 774 references, 6,440 cost cells |
| indicator views | 13, over 247 measures |
| tests | 136, all passing |
| hand checks | 40 provision spot checks, 60 reference checks, all recorded |

What is not built yet: the temporal-scope extraction (`v_end_bound_by_year`
returns nothing until it is), and one hand-recomputation fixture. See
`PLAN.md`.

## What this is

One SQLite file with one row per addressable unit of the two instruments -
section, subsection, paragraph, subparagraph, clause - each carrying:

- its full citation path (for example `110.6(2.1)(a)(ii)`)
- the English and French text exactly as published
- the heading, if the source gives one
- the history note (amending-statute reference), if the source gives one
- the source URL and the snapshot date it was taken from

Plus a table of cross-references between provisions, full-text search indexes
over the English and French text, and a `meta` table recording exactly which
source and snapshot the file was built from.

Plus the Department of Finance's *Report on Federal Tax Expenditures 2026* as
data - 229 measures per language, with their legal references resolved to the
provisions above, their cost tables, their histories - and a set of SQL views
that compute indicators over both. Every indicator column's formula, inputs and
null rule is in `docs/indicator-definitions.md`, which the build generates from
the view SQL.

**The views compute facts, not judgments.** There is no score, no ranking, no
weight, and no column that says what a reader should conclude. A measure with no
cost estimate has a null cost, never a zero. Nothing computes whether a date has
passed. Sorting is the reader's action, not the dataset's.

## What this is not

- It is not an interpretation of the Act. It reproduces text and structure.
- It does not say which tax expenditures are worth keeping, or which are
  loopholes, or which are candidates for anything. The indicators make those
  questions answerable by a person; they do not answer them.
- It is not legal or tax advice, and it makes no recommendations.
- It is not a consolidation service. It is a snapshot, dated in `meta`.
- It is not authoritative. For anything that matters, check the official
  consolidation at <https://laws-lois.justice.gc.ca>.

## Source

**Justice Laws Website, Department of Justice Canada** - the official XML
consolidations. Chosen over the A2AJ dataset because A2AJ's records stop at the
section level; the reasoning is in `docs/source-notes.md` and `docs/decisions.md`.

| Instrument | Language | URL |
|---|---|---|
| Income Tax Act, RSC 1985, c 1 (5th Supp) | EN | <https://laws-lois.justice.gc.ca/eng/XML/I-3.3.xml> |
| Income Tax Act | FR | <https://laws-lois.justice.gc.ca/fra/XML/I-3.3.xml> |
| Income Tax Regulations, CRC c 945 | EN | <https://laws-lois.justice.gc.ca/eng/XML/C.R.C.,_c._945.xml> |
| Income Tax Regulations | FR | <https://laws-lois.justice.gc.ca/fra/XML/C.R.C.,_ch._945.xml> |

**Consolidation date: 2026-06-18** (`lims:pit-date`, as stamped in the source
files themselves). Every build writes the source URLs and this date into the
`meta` table, and every record carries its own `source_url` and `snapshot_date`.

## Licence

**Code:** MIT. See `LICENSE`.

**Project status: non-commercial.** This dataset is published for public-interest
and non-commercial use.

### Justice Canada reproduction terms

The Income Tax Act and Income Tax Regulations are reproduced under the Department
of Justice Canada [Terms and Conditions](https://www.justice.gc.ca/eng/terms-avis/index.html).
The governing clause for enactments, quoted in full:

> Anyone may, without charge or request for permission, reproduce enactments and
> consolidations of enactments of the Government of Canada, and decisions and
> reasons for decisions of federally constituted courts and administrative
> tribunals, provided due diligence is exercised in ensuring the accuracy of the
> materials reproduced and the reproduction is not represented as an official
> version.

The non-commercial reproduction clause, which requires reproductions to state:

> the reproduction is a copy of an official work that is published by the
> Government of Canada and that the reproduction has not been produced in
> affiliation with, or with the endorsement of the Government of Canada

and the commercial clause:

> Reproduction of multiple copies of materials on this site, in whole or in part,
> for the purposes of commercial redistribution is prohibited except with written
> permission from the Department of Justice Canada.

### Open Government Licence - Canada

The source data is published under the
[Open Government Licence - Canada](https://open.canada.ca/en/open-government-licence-canada).
Under it you are free to:

> Copy, modify, publish, translate, adapt, distribute or otherwise use the
> Information in any medium, mode or format for any lawful purpose.

subject to the attribution condition:

> Acknowledge the source of the Information by including any attribution
> statement specified by the Information Provider(s) and, where possible, provide
> a link to this licence.

and the no-warranty clause:

> The Information is licensed "as is", and the Information Provider excludes all
> representations, warranties, obligations, and liabilities, whether express or
> implied, to the maximum extent permitted by law.

**Contains information licensed under the Open Government Licence – Canada.**

### Our statements under those terms

- This is an **unofficial** reproduction. It is **not** an official version of
  the *Income Tax Act* or the *Income Tax Regulations*.
- It has **not** been produced in affiliation with, or with the endorsement of,
  the Government of Canada.
- The works reproduced are the *Income Tax Act* (RSC 1985, c 1 (5th Supp)) and
  the *Income Tax Regulations* (CRC, c 945), published by the Department of
  Justice Canada.
- Due diligence on accuracy is exercised through the acceptance tests described
  in `CLAUDE.md`, which must pass before any build is published.
- For the official consolidation, see <https://laws-lois.justice.gc.ca>.

**Open legal question, not a blocker.** Justice Canada's standing permission to
reproduce enactments is not conditioned on non-commercial use, while a separate
clause restricts commercial redistribution of site materials generally. How those
interact for a downstream *commercial* user of this dataset has not been
determined and is not something this project takes a position on. The project
itself is non-commercial. Both clauses are quoted above and in
`docs/source-notes.md` so anyone can read them directly.

## Methods - how the data was checked

Three independent guards. Each catches a different class of error, and this
session proved that none of them subsumes the others.

**1. Round-trip against a separate reconstruction.** Concatenating every record
in document order must reproduce the source file character-for-character. No
normalisation is applied - not even the "minimal whitespace normalization" the
project's own brief allows for. The comparison target is built by a deliberately
different method from the parser (a mixed-content walk over `.text` and `.tail`),
and a second test accounts for every character against the raw XML by a third
route.

This matters because the first version of the round-trip **passed while the
database was missing text**. The parser and the check shared a blind spot - both
skipped every `<Label>` - so the formula variable names vanished and the test
could not see it. A verification that reuses the logic it is verifying only
proves that logic is self-consistent.

**2. Uniqueness on the shipped key.** Uniqueness is tested against
`citation_path` as written to the database, after every disambiguation rule, and
never against a structural proxy. An earlier proxy check reported *zero*
duplicate terms per parent element while the shipped paths collided three ways in
English and eleven in French - the parent element and the parent path are not the
same thing.

**3. Symmetric bilingual join.** An English and a French record are joined only
if both files agree about both terms. 2,021 of 2,046 definition joins pass. The
rest are unjoined and catalogued. This caught 44.1(1) "eligible small business
corporation share" - a term the Act defines twice - where the join had paired one
definition's English text with the other's French text.

**4. Hand verification against the official site.** The three guards above all
read the same four XML files the build reads. If those files were misread the
same way twice, no automated check in this project would notice. The only test
that leaves that loop is a person comparing the build against the published text
on <https://laws-lois.justice.gc.ca>.

Forty citations, ten per instrument per language, were checked by hand against
laws-lois.justice.gc.ca on September 18 and 19, 2026, from seeded random samples
of twenty per file. For each, the checker confirmed that the record's text
appears on the official site at the citation path the record claims. All forty
matched. Seven sampled rows were skipped because their text was too short to
search reliably or was a repealed-provision note; thirty-three were not checked.
The full sample and results are in `tests/spot_checks/` for anyone who wants to
extend the check. One convention surfaced: the official site displays provisions
inside definitions by label path only, while Portage citation paths include the
defined term in quotation marks so that paths stay unique.

One query raised during checking was followed up and found to be nothing: the
French Regulations row `1206(1)"stated percentage"(a)(ii)`, noted as displaying
on the site as `1206(01)(a)(ii)`. The published XML puts that definition inside
subsection `(1)`, the official page renders it under `(1)`, and Portage stores
`label_raw_fr` as `(1)` unaltered. No label in section 1206 contains a zero in
either language, no label was changed, and there is nothing to catalogue - the
underlying difference is the same definition-path convention noted above.

The samples that were checked are preserved as `verified_2026-09_*.md`. Sample
generation has since been changed to exclude rows whose first sentence is under
25 characters or begins with a repealed-provision marker, so a future checker is
not handed rows that cannot be searched for.

**5. Position is never a join key.** Every time this project has needed to match
something across English and French, the tempting shortcut has been position -
the first definition, the first measure, row 1 of the CSV - and every time it
has been wrong. Each edition is ordered **alphabetically in its own language**,
so position encodes the spelling of a word, not the identity of a thing.

It has now appeared six times:

| Where | What position would have paired |
|---|---|
| Definitions in 248(1) | "absorbed capacity" with "tax shelter" |
| Pages of the report | Part 4 holds 49 measures in English, 99 in French |
| Measures within a page | alphabetical in each language |
| Subject list on Part 3 | "Arts and culture" with "Arrangements fiscaux intergouvernementaux" |
| Objective category list | same |
| Open data CSV rows | 39.8% aligned; row 1 is a wage subsidy against a Quebec abatement |

So nothing in this dataset is paired by position. Definitions are keyed by their
defined term; provisions by their citation path; measures by the content of
their references and cost figures, and then by Finance's own categorical fields.
Where a published list has to be read across languages, the list supplies the
**vocabulary** and the pairing is learned from records already matched on
independent evidence - never from the order the terms happen to be printed in.

The rule generalises beyond this project: in any bilingual Government of Canada
publication, assume each language is sorted in its own alphabet until shown
otherwise.

Alongside these, fourteen catalogue files are written by every build and diffed
line-by-line against committed fixtures. Anomalies are catalogued, never counted:
a total stays the same while a case moves silently from one provision to another,
so the tests compare the list, not its length.

### The rule that keys definitions went through three versions

Each passed its own check and was then shown wrong by a *different* measurement.
Recorded because the shape of that sequence is the point.

| Version | Rule | Result | What exposed it |
|---|---|---|---|
| 1 | first defined term anywhere in the subtree | 3 collisions in English, 11 in French | the search returned cross-references to *other* definitions |
| 2 | term and equivalent both from the opening `<Text>` | 1,219 French definitions reported no English term, against ~130 expected | the equivalent is published after the paragraphs, not in the opening text |
| 3 | own term from the opening `<Text>`; equivalent = last match in the subtree | 0 collisions, 2,046 joins | held - then the symmetry check unjoined a further 25 |

Full detail in `docs/citation-path-rule.md` and `docs/source-notes.md`.

## Known limits

Read these before using the data. Each is a deliberate boundary, not a bug, and
each is catalogued in a file the tests check.

**Cross-references contain no provision-to-provision links at all.** The
`cross_references` table holds only what the source marks up as elements:
`XRefExternal`, which names another *instrument* rather than a provision;
`DefinitionRef`, which names a defined term; and `XRefInternal`, of which the
entire corpus contains **one**. References like "Notwithstanding subsections
152(4) to (5)" are **not in this table**. **Do not read it as a reference
graph.**

**A reference has three outcomes, and "ambiguous" is an answer.** Of 5,364
tagged references, 950 resolve to exactly one definition (`unique`), 1,207 name
a term defined in several places (`ambiguous`), and 3,207 resolve to nothing
(`unresolved`). Every candidate definition is recorded in
`definition_ref_candidates`, and a reference with several candidates **never
picks one** - "person" is defined in 15 places in the English Act, and which
definition governs a given sentence is a question of scope this dataset does not
answer. Join the candidates table and apply your own rule in the open. The 400
terms defined more than once are listed in
`data/terms_defined_more_than_once.csv`.

**Candidates come in two kinds and two scopes.** `candidate_kind` is
`definition_record` (a `<Definition>` element) or `inline_defined_term` (a term
marked up in a provision's own text with no `<Definition>` wrapper - 964 such
sites in the English Act, found by element nesting and never by looking for the
word "means"). `candidate_scope` is `same_instrument` or `other_instrument`.
**Only same-instrument candidates decide the resolution.** A definition in the
Act is recorded as a candidate for a Regulations reference so you can see it,
but it never resolves one: whether the Act's definition governs a word in the
Regulations is a legal question, usually settled by prose the markup does not
carry. 691 references have other-instrument candidates. The full rule, with the
before-and-after numbers, is in `docs/reference-rule.md`.

**Measures are joined in two passes, and 18 are not joined at all.** 201 of 229
measures pair on the content of their legal references and cost figures. A
second pass over the remainder uses Finance's own categorical fields - CCOFOG
codes, type of tax, objective category and subject - and pairs a further **10**,
marked `join_method = 'content_categorical'`. The remaining **18 measures in
each language stay single**, listed in `data/measure_join_gaps.csv`. They are
mostly measures with no resolvable reference, no numeric cost and a categorical
signature shared with others, which leaves nothing language-independent to join
on. CCOFOG codes are numeric and identical across editions; the French terms for
subject and objective category are mapped to English through
`data/finance_category_map.csv`, learned from the measures joined in the first
pass and vocabulary-checked against the fixed lists Finance publishes on Part 3.

**Reference resolution, reported two ways.** Of the 774 references extracted
from the report's *Legal reference* field, **600 resolve to a provision - 77.5%**.
That figure is bounded below 100% by construction: 53 references name an
instrument this dataset does not hold, chiefly the Excise Tax Act, and 79 name a
Schedule, Class or Part, which Phase 0 does not model - neither can ever resolve,
however good the grammar is. Measured over the references that *could* resolve,
those citing the Income Tax Act or its Regulations, **600 of 657 resolve -
91.3%**. The remainder are 31 `schedule_or_class`, 19 `not_in_consolidation`,
5 `term_not_joined` and 2 `no_provision`. Every unresolved reference keeps its
raw text and a status in `data/unresolved_references.csv`.

**A cited range is linked to its endpoints only.** `sections 110.6 to 110.7`
produces two references, not everything between them, and `paragraphs (d) to
(d.6)` gives `(d)` and `(d.6)`. Expanding a range would mean deciding what lies
inside it, which is a reading of the citation rather than a fact in it, and it
would make the reference set depend on which consolidation was loaded. So a
measure citing a range is **not** linked to the provisions between its
endpoints. `raw_text` keeps the range as published if you want to expand it
yourself.

**Beneficiary counts are read from prose, and mostly are not.** The field is a
sentence, so a year and a count can only be extracted by pattern, and only where
the sentence contains exactly one number-and-year pair. **75 of 458 rows are
populated**; the rest keep their published sentence with NULL count. Every row
carries `method` - `'pattern'` or `'none'` - and `raw_value` always holds what
was published. This is the weakest field in the dataset: unlike a reference, a
wrong count does not announce itself by failing to resolve.

**The tax expenditure report is a dated snapshot, and its dates do not line up
with the Act's.** The 2026 Report on Federal Tax Expenditures states the law as
of **31 December 2025**; the Income Tax Act consolidation in this dataset is as
of **18 June 2026**. So Finance sometimes cites a provision that has since been
repealed or renumbered - 118.6(2), 38.3, 38.4 and 12.2(9) are examples. Those
references carry `status = 'not_in_consolidation'`, which is a statement about
the six-month gap between two dated documents, **not** a parsing failure and
not an error by Finance. 33 references are in that state.

**Two cost symbols are Portage's inference, not Finance's legend.** Finance
documents `n.a.`/`n.d.`, `–`, `X` and `S`/`F` in the metadata published with the
open data. The report's tables also contain a **bare hyphen** (`-`, 36 cells)
and **`n.d` without its final period** (16 cells), which the legend does not
mention. We read them as the documented `–` and `n.d.` respectively. Those two
rows are marked `legend_match = 'variant'` in `data/cost_tokens.csv`; every
documented symbol is marked `legend`, and the empty cell - also undocumented -
is marked `portage`. `raw_value` always keeps what was published, so any reader
who disagrees can reclassify without reparsing.

**The Part 7 appendix is excluded.** *Additional Information on Relevant
Government Programs by Subject* is a reference table, not a tax measure. It has
no caption id in English but does in French, with 17 body rows, so it passes
every structural test for a measure; it is excluded because the Part 3 index
does not link it. Measures are defined by that index, which gives 229 in each
language.

**Schedules and amendments-not-in-force are not captured.** The `sections` table
covers the enacted `<Body>`. The file also contains three `<Schedule>` elements -
"RELATED PROVISIONS" (16 sections), "AMENDMENTS NOT IN FORCE" (6 sections) and
"Listed Corporations" (no sections) - and the Regulations have ten. None of them
is in the database.
Amendments not in force are, by definition, not the law as consolidated, and
mixing them into the same table would let a reader retrieve a provision that is
not in effect without noticing. "Listed Corporations" is genuinely part of the
Act and its omission is a gap, not a principle.

**History notes are section-level only.** The source attaches `HistoricalNote`
to sections, not to subsections - 762 notes against 763 sections. The
`history_note` column exists on every row but is only ever populated on sections.
It does not tell you when a particular subsection was amended.

**About 3% of records exist in one language only.** English and French genuinely
structure some provisions differently. Those rows carry `bilingual_gap = 1` with
NULL on one side, and are listed in `data/bilingual_gaps.csv`. Alignment is never
forced.

**Some pairs are joined by label but unverified.** Where a provision's set of
child labels differs between the two files, a shared label is not evidence that
the two texts correspond - English 51(1)(a) is a condition while French 51(1)a)
is a rule. Those rows carry `alignment_unverified = 1` and are listed in
`data/alignment_unverified.csv`. **For verified bilingual pairs only, filter
`bilingual_gap = 0 AND alignment_unverified = 0`.**

**Definitions are keyed by their defined term**, not by position - each language
file alphabetises definitions in its own language, so position means nothing
across languages. Where no English term is published the key falls back to the
French term, and where neither exists to an ordinal; both cases are listed in
`data/definition_key_fallbacks.csv`.

**Not every bilingual pair rests on the same evidence.** The `alignment` column
says how each row's two languages came to be together: `verified` (joined on a
key read from the source - a label path or a defined term both files agree
about), `positional` (joined on an ordinal this project assigned, so all that is
known is that the two texts sit in the same place inside the same provision),
`unverified`, `split`, or `single`. Continued text, formulas and headings have no
labels, so they are `positional`. **For the strongest subset, filter
`alignment = 'verified'`** - 42,181 rows.

**Some citation paths are ours, not Justice Canada's.** The published XML
sometimes repeats a label or a defined term inside one provision - the French
142.6(8)b) numbers two subparagraphs `(iv)` where the English has `(iv)` and
`(v)`, and 44.1(1) defines "eligible small business corporation share" twice.
The duplication is the source's; the `#2` suffix we add to tell the two records
apart is **ours**. `label_raw` keeps the label exactly as published and the text
is never altered, but a path like `142.6(8)(b)(iv)#2` is an artefact of this
dataset and is **not a citation Justice Canada would recognise**. The same
applies to any path containing `~`. All such cases are listed in
`data/label_anomalies.csv`.

**Definition joins must be symmetric.** An English and a French definition are
paired only if both files agree about both terms. 2,021 of 2,046 pass; the 25
that do not are unjoined and listed in `data/definition_join_suspects.csv`,
with the French record at `<path>~fr`.

**Table structure is not modelled.** The Regulations contain five tables (157
rows, 314 cells). Their text is preserved exactly and in document order, but
which cell belongs to which row and column is not recorded - a table reads as a
run of text fragments.

**This is a dated snapshot, not a consolidation service.** `meta` records
`consolidation_date` and `retrieved_date` separately.

**It is unofficial.** For anything that matters, check
<https://laws-lois.justice.gc.ca>.

## Setup

The project pins Python 3.12 and uses [uv](https://docs.astral.sh/uv/) to manage
both the interpreter and the dependencies. uv installs its own copy of Python,
so the system Python that ships with macOS is never touched.

From a clean checkout, on macOS or Linux:

```sh
# 1. Install uv (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"          # or restart your shell

# 2. Install the pinned Python and create the virtual environment
uv python install 3.12
uv venv --python 3.12

# 3. Install the dependencies into it
uv pip install -r requirements.txt
```

That creates `.venv/` in the project directory. It is gitignored - everyone
builds their own. To use it:

```sh
source .venv/bin/activate
python -m portage.build
pytest
```

Or without activating, prefix commands with `uv run`, e.g. `uv run pytest`.

## Build

```
pip install -r requirements.txt
python -m portage.build
pytest
```

(Not wired up yet - see `PLAN.md`.)
