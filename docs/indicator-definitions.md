# Indicator definitions

**Definitions settled; no SQL written yet.** This is the list of views, what
each one means, and what null means in it, written before implementation - the
same order as the citation-path rule and the reference grammar. The four open
questions at the foot of the first draft were answered by Matt on 2026-09-20 and
are folded in below.

Once the views exist, this file is **generated**: each entry's SQL comes from the
view definition in the database and the prose comes from a dict in code. A test
asserts the file is current, and the build fails if a view exists with no entry
or an entry with no view.

---

## What an indicator is allowed to be

From CLAUDE.md, restated because every definition below has to be checked
against it:

> An indicator is a number or category that a reader could recompute from the
> published sources by following a written formula.

So: no composite index, no weight, no ordering baked into the data, nothing
imputed, and nothing that says what a reader should conclude. Finance's caveats
travel with the number - any indicator that uses a cost cell carries the
`value_kind` and `raw_value` that produced it.

**Null is null.** A measure with no cost estimate has a null cost, never zero.
A ratio with a null input is null. Where a rule would otherwise have to guess,
the answer is null and the reason is a column.

---

## Where the views live

In `portage.sqlite`, as `CREATE VIEW`. Not a stored table: a stored indicator is
a judgment that outlives the reasoning behind it, and a view forces the
computation to stay visible and to be re-derived from the source tables every
time it is read. The static site materialises them at export time.

**One thing this forces.** SQLite views cannot take parameters, so the two views
CLAUDE.md describes as "parameterized on a year" are not parameterized. They
**expose the year as a column** and the reader supplies the threshold:
`WHERE end_year < 2027`. There are deliberately no per-threshold views. Choosing
the year is the reader's judgment, and a view called `v_end_date_before_2027`
would make that choice look like a finding.

---

## 1. `indicators` - one row per measure

**One row per `measures` row**, not per language: 247 rows, matching `measures`
exactly. The numeric indicators are language-independent; only the copied
classification labels differ, and those carry `_en` / `_fr` suffixes, the same
shape `measures` already uses. Doubling every row to carry a handful of
translated labels would make the language a property of the measure, which it
is not.

`join_method` is carried through from `measures` - `content`,
`content_categorical`, or null - so that **the 36 unjoined singles are visible
in every indicator query**. A single is a real measure whose other-language
record could not be paired; its classification labels will be present in one
language and null in the other, and a reader filtering on `subject_en` would
otherwise lose the 18 French-only measures without noticing.

| column | meaning | null when |
|---|---|---|
| `measure_id` | key into `measures` | never |
| `join_method` | how the two editions were paired | the measure is a single, present in one language only |
| `name_en`, `name_fr` | measure name as published | that language has no record for this measure |

Every column below is computed from Phase 0 and Phase 1 tables.

### Cost, from `measure_costs`

The **figure used** for a measure is Finance's `Total` row where the measure
publishes one, and the measure's single component row where it does not. Of 183
measures with any cost rows: 52 publish a Total, 130 publish exactly one
component, and **1 publishes several components with no Total**. That one
measure gets null cost figures and `cost_figure_basis = 'components_only'`,
because adding components together would be arithmetic Finance did not publish.

| column | meaning | null when |
|---|---|---|
| `cost_figure_basis` | `total_row`, `single_component`, or `components_only` | never |
| `cost_latest_estimate` | value of the most recent year whose `value_kind` is `estimate`; projections excluded | no estimate in any year, or basis is `components_only` |
| `cost_latest_estimate_year` | that year | same |
| `cost_latest_estimate_raw` | the published cell text for that figure | same |
| `cost_latest_projection` | most recent year with `value_kind = 'projection'` | no projection |
| `cost_latest_projection_year` | that year | same |
| `cost_first_estimate` | earliest year with `value_kind = 'estimate'` in the report's window (2020-2027) | no estimate |
| `cost_first_estimate_year` | that year | same |
| `cost_change_abs` | `cost_latest_estimate - cost_first_estimate` | either input null, **or the two years are the same** |
| `cost_change_pct` | `cost_change_abs / cost_first_estimate` | either input null, years equal, **or `cost_first_estimate` is 0** |
| `cost_status` | one of five - see below | never |
| `cost_withheld_years` | count of cells with `value_kind = 'withheld_confidential'` | never; 0 where none |

**`cost_status` has five values**, one more than CLAUDE.md lists:

| value | meaning |
|---|---|
| `costed` | a numeric value in every year of the window |
| `partially_costed` | numeric in some years, not all |
| `not_costed` | Finance published a cost table, and no year carries a number |
| `no_cost_table` | Finance published **no cost table at all** for this measure |
| `withheld` | any cell is `X`, withheld by Finance for confidentiality |

`no_cost_table` is the addition. 46 measures have no cost rows whatever, and
folding them into `not_costed` merged two different statements: *Finance
published a table showing no estimate* and *Finance published no table*. The
first is a measurement result; the second is a publishing decision. A reader
asking "what is uncosted" usually means the first.

Derived from `value_kind` alone, never from the numbers. `withheld` takes
precedence when any cell is `X`, because the reader needs to know the series is
incomplete by Finance's choice rather than by absence of data.

**Division by zero is a real case**: a first estimate of 0 is published for some
measures. `cost_change_pct` is null there, not infinite.

### Beneficiaries, from `measure_beneficiary_counts`

| column | meaning | null when |
|---|---|---|
| `beneficiaries_latest` | the count, only where `method = 'pattern'` | method is `none` - the published sentence carried no single number-and-year pair |
| `beneficiaries_latest_year` | its year | same |
| `beneficiaries_raw` | the published sentence, **always**, whether or not a count was parsed | never, where the field is non-empty |
| `cost_per_beneficiary` | `cost_latest_estimate / beneficiaries_latest` | either input null, **or the two years differ** |
| `cost_per_beneficiary_note` | `years_differ` where that is why it is null, else null | when the ratio is computed or both inputs are null |

**Expected coverage is low and that is the honest state**: only 75 of 458
beneficiary rows carry a parsed count. Most of this column will be null.

### Age and history, from `measure_history`

| column | meaning | null when |
|---|---|---|
| `introduced_year` | earliest year in the measure's history rows | no history row carries a parseable year |
| `last_change_year` | latest year in those rows | same |
| `years_since_last_change` | `report_year (2026) - last_change_year` | `last_change_year` null |
| `history_events` | count of history rows | never; 0 where none |

`introduced_year` is **the earliest year Finance lists in this field**, which is
not necessarily the year the measure was enacted. The column name says
"introduced" because that is what the field is about; the definition says what
it actually measures.

### Objective source year, from the objective field

| column | meaning | null when |
|---|---|---|
| `objective_source_year` | the year in the parenthetical Finance attaches to the objective, e.g. "(Budget 1998)" | no parenthetical, or no year in it |
| `objective_source_raw` | the parenthetical as published | same |
| `objective_source_method` | `pattern` where a year was read, `none` otherwise | never |

### Classification, copied from Finance with no interpretation

`category`, `objective_category`, `subject`, `ccofog_code`, `type_of_tax`,
`type_of_measure` - each copied verbatim from the `measures` row. Null where
Finance left the field empty.

| column | meaning | null when |
|---|---|---|
| `objective_category_internal` | 1 if Finance's Part 3 lists this category under "Objectives that are internal to the tax system", else 0 | `objective_category` is null |
| `has_overlapping_program` | 1 if "other relevant government programs" is non-null and not "n/a", else 0 | the field is null |
| `overlapping_program_raw` | that field as published | field null |

Finance's Part 3 puts 12 categories under "internal to the tax system" and 10
under "Other objectives". **The list ships as a fixture**, so a change in
Finance's grouping shows up as a failing test rather than a silent
reclassification. `has_overlapping_program` is Finance's statement that related
spending exists, and nothing more.

A measure may carry several categories in one field - the cells run them
together. `objective_category_internal` is 1 only where **every** category
present is internal; where they are mixed it is 0, and
`objective_category_mixed` is 1 so the reader can tell the two cases apart.

### Legal footprint, from `measure_references` joined to `sections`

| column | meaning | null when |
|---|---|---|
| `provisions_cited` | count of reference rows for the measure | never; 0 where none |
| `provisions_resolved` | count with `status = 'resolved'` | never; 0 |
| `provisions_not_in_consolidation` | count with that status - the as-of-date mismatch between the report (31 Dec 2025) and the consolidation (18 Jun 2026) | never; 0 |
| `sections_touched` | distinct top-level sections among resolved paths | never; 0 |
| `shared_with_measures` | count of *other* measures citing at least one of the same resolved `citation_path`s | never; 0 |
| `amending_acts_count` | number of amending-statute entries in the Phase 0 `history_note` of each cited section, summed | null where **no** cited section has a history note |
| `amending_acts_method` | `pattern` | never |

`amending_acts_count` **double counts by design**: a section cited by several
measures contributes its amending entries to each. It is a property of the
measure's legal footprint, not a partition of the Act. Notes are semicolon
separated after a `[NOTE: ...]` prefix; 1,240 sections carry one. Unparsed notes
go to a catalogue with a fixture.

### Temporal scope, from `provision_temporal_scope`

| column | meaning | null when |
|---|---|---|
| `earliest_end_date` | earliest `end` bound across the measure's **cited** provisions | no cited provision has an end bound |
| `latest_end_date` | latest such bound | same |
| `has_step_down` | 1 if any cited provision has a `step-down` bound, else 0 | no cited provision has any extracted scope |

**Whether a date has passed is not computed.** There is no `is_expired`, no
`days_remaining`, no comparison against the build date. The reader compares
against their own date, because "expired" depends on when you ask and on facts
outside this dataset.

---

## 2. Supporting tables

### `provision_temporal_scope` - the one extraction that needs a model

**Scope: the cited provisions only**, not the whole Act - roughly 400 distinct
provisions behind ~600 resolved references. Extracting scope from the entire Act
would be a different project, and nothing in Phase 2 needs it.

One row per date-bounded condition found in a cited provision's text:
`section_id`, the phrase **exactly as it appears**, `bound_kind`
(`start` / `end` / `step_down`), the date or year, `method = 'extracted_llm'`.

Rules, all from CLAUDE.md:

- the phrase must be a **verbatim substring** of `text_en`, asserted by a test
  for every row;
- the model never infers a date the text does not state;
- prompt, model name and run date recorded in `meta`;
- the API is called from a batch script, **never from the build**, and its
  output is committed as data with a fixture;
- a precision sample of 30 rows for hand checking, same protocol as Phase 1.

### `measure_provision_overlap`

One row per pair of measures sharing a resolved `citation_path`, with the path.
A pure join, no threshold, no score.

---

## 3. Canned-question views

Each is a **filter**, never a ranking. None carries an `ORDER BY` that implies
importance; ordering is the reader's action.

| view | returns | note |
|---|---|---|
| `v_not_costed` | measures with `cost_status = 'not_costed'` | |
| `v_withheld` | measures with any `X` cell, and the count | Finance withheld for confidentiality; not an absence of data |
| `v_no_beneficiary_count` | measures where `beneficiaries_latest` is null, with the published sentence | mostly a statement about the field's prose, not the measure |
| `v_end_bound_by_year` | one row per provision end bound, with `end_year` as a column | the reader filters: `WHERE end_year < 2027` |
| `v_last_change_by_year` | one row per measure with `last_change_year` as a column | same |
| `v_objective_internal` | measures whose every objective category is internal to the tax system | Finance's grouping, from the fixture |
| `v_overlapping_programs` | measures where `has_overlapping_program = 1`, with the field text | |
| `v_shared_provisions` | resolved `citation_path`s cited by more than one measure, with the measures | |
| `v_not_in_consolidation` | measures citing a provision absent from the consolidation, with the paths | the six-month as-of gap, not an error by anyone |
| `v_provision_footprint` | for every resolved `citation_path`: the measures citing it, and the measures sharing its top-level section | the "for a given path" filter is the reader's `WHERE` |

---

## Settled by Matt, 2026-09-20

1. **Parameterized views**: year exposed as a column; no per-threshold views.
2. **`indicators` grain**: one row per measure, `_en` / `_fr` on the copied
   labels, and `join_method` carried through so unjoined singles stay visible.
3. **`cost_status`**: five values, `no_cost_table` added.
4. **Temporal scope**: cited provisions only.

## Still open

Nothing blocking. Two things to decide while writing the SQL, both small:

- Whether `sections_touched` counts the top-level section of a path like
  `110(1)(d)` as `110`, which is the obvious reading, or as the `sections` row
  whose level is `section`. They are the same thing in every case checked, but
  the SQL has to pick one and the doc should say which.
- Whether `v_provision_footprint` returns one row per (path, measure) pair or
  one per path with a count. The first is more useful and much longer.
