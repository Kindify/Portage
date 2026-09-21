# Indicator definitions

**This file is generated.** `python -m portage.build` writes it from the view
definitions in `portage.sqlite` and the prose in `portage/indicators.py`. A
test asserts that the copy on disk matches what the generator produces, and
that every column of `indicators` has an entry and every entry names a real
column. Edit `portage/indicators.py`, then rebuild - editing this file by hand
will fail the test.

The preamble below is written by hand and is not derived from the SQL.

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

In `portage.sqlite`, as `CREATE VIEW`. Not a stored table: a stored indicator
is a judgment that outlives the reasoning behind it, and a view forces the
computation to stay visible and to be re-derived from the source tables every
time it is read. The same SQL is exported to `views/` as one file per view, for
reading without opening the database.

**One thing this forces.** SQLite views cannot take parameters, so the two
views CLAUDE.md describes as "parameterized on a year" are not parameterized.
They **expose the year as a column** and the reader supplies the threshold:
`WHERE end_year < 2027`. There are deliberately no per-threshold views.
Choosing the year is the reader's judgment, and a view called
`v_end_date_before_2027` would make that choice look like a finding.

---

## Which edition each number is read from

Costs, references and beneficiary counts are stored one row per language.
Reading both would count a measure twice, so `measure_figure_basis` records one
edition per measure and every indicator reads from it: English wherever the
measure has an English record, French for the 18 measures that exist only in
French.

This changes no figure. The cost signatures - year, value and `value_kind` -
match exactly for all 172 measures that carry both editions, which is what the
Phase 1 join was built on. References are not quite so clean: six measures
resolve differently in the two editions, and they are catalogued in
`data/measure_reference_edition_diffs.csv` rather than reconciled.

---

## Settled by Matt, 2026-09-20

1. **Parameterized views**: year exposed as a column; no per-threshold views.
2. **`indicators` grain**: one row per measure, `_en` / `_fr` on the copied
   labels, and `join_method` carried through so unjoined singles stay visible.
3. **`cost_status`**: five values, `no_cost_table` added.
4. **Temporal scope**: cited provisions only.

---

## Views

| view | rows in this build | what it returns |
|---|---|---|
| `measure_resolved_provisions` | 332 | Every resolved provision a measure cites, one row per reference, with the top-level section it sits in. |
| `measure_provision_overlap` | 230 | One row per pair of measures that cite the same resolved provision, with the provision. |
| `indicators` | 247 | One row per measure - 247, matching `measures` exactly, not one row per language. |
| `v_not_costed` | 10 | Measures where Finance published a cost table and no year in it carries a number. |
| `v_withheld` | 9 | Measures with at least one cost cell published as "X", which Finance's own legend defines as withheld for confidentiality. |
| `v_no_beneficiary_count` | 172 | Measures with no parsed beneficiary count, with the published sentence in both languages. |
| `v_end_bound_by_year` | 695 | One row per extracted end bound on a provision a measure cites, with the year as a column. |
| `v_last_change_by_year` | 247 | One row per measure with the latest year Finance lists in its implementation and recent history field, as a column for the reader to filter on. |
| `v_objective_internal` | 70 | Measures every one of whose objective categories Finance's Part 3 lists under "Objectives that are internal to the tax system". |
| `v_overlapping_programs` | 208 | Measures where Finance's "other relevant government programs" field names something. |
| `v_shared_provisions` | 34 | Resolved provisions cited by more than one measure, with the measures. |
| `v_not_in_consolidation` | 13 | Measures citing a provision the consolidation does not contain, with the reference as published. |
| `v_provision_footprint` | 332 | For every resolved provision: the measure citing it, and the number of other measures that cite the same provision or another provision of the same section. |

---

## `indicators`, column by column

The formula is the SQL below; this is the meaning and the null rule beside it.

| column | meaning | null when |
|---|---|---|
| `measure_id` | Key into `measures`. | never |
| `join_method` | How the two editions were paired in Phase 1 - `content`, `content_categorical`, or null. | the measure is a single, present in one edition only |
| `name_en` | The measure name as published in the English edition. | the English edition has no record for this measure |
| `name_fr` | The measure name as published in the French edition. | the French edition has no record for this measure |
| `cost_figure_basis` | Which published row is taken as the measure's cost figure - `total_row`, `single_component`, `components_only`, `multiple_total_rows` or `no_cost_table`. From `measure_figure_basis`. | never |
| `cost_figure_row_label` | The published label of that row, verbatim. | the basis is `components_only`, `multiple_total_rows` or `no_cost_table` - there is no single published row to name |
| `cost_edition` | Which edition's cost rows were read. English wherever the measure has them; the two editions' cost signatures match exactly, so this changes no figure, only which rows are counted. | the measure has no cost rows in either edition |
| `cost_latest_estimate` | Value in millions of dollars of the most recent year on the figure row whose `value_kind` is `estimate`. Projections are excluded. | no year on the figure row is an estimate, or there is no figure row |
| `cost_latest_estimate_year` | That year. | as `cost_latest_estimate` |
| `cost_latest_estimate_raw` | The published cell text behind that figure, carried through so Finance's own notation travels with the number. | as `cost_latest_estimate` |
| `cost_latest_projection` | Value of the most recent year on the figure row whose `value_kind` is `projection`. Finance marks projections in the column header - `(P)` in English, `(proj.)` in French - so this is published, not inferred. | no year on the figure row is a projection, or there is no figure row |
| `cost_latest_projection_year` | That year. | as `cost_latest_projection` |
| `cost_latest_projection_raw` | The published cell text. | as `cost_latest_projection` |
| `cost_first_estimate` | Value of the earliest year on the figure row whose `value_kind` is `estimate`, within the report's window of 2020 to 2027. | as `cost_latest_estimate` |
| `cost_first_estimate_year` | That year. | as `cost_first_estimate` |
| `cost_first_estimate_raw` | The published cell text. | as `cost_first_estimate` |
| `cost_change_abs` | `cost_latest_estimate` minus `cost_first_estimate`, in millions of dollars. Not adjusted for inflation and not annualised. | either input is null, or the two years are the same year |
| `cost_change_pct` | `cost_change_abs` divided by `cost_first_estimate`, as a ratio rather than a percentage - 0.5 means half as much again. | either input is null, the years are equal, or `cost_first_estimate` is 0 |
| `cost_status` | One of `costed` (a numeric cell in every published year), `partially_costed` (in some), `not_costed` (in none), `no_cost_table` (Finance published no cost table at all) or `withheld` (at least one cell is `X`). Read across every cost row of the measure, not only the figure row, so a caption row carrying no numbers does not make a costed measure look partial. Derived from `value_kind` alone, never from the numbers. `withheld` takes precedence. | never |
| `cost_withheld_years` | Count of distinct years in which at least one cell is published as `X`, which Finance's legend defines as withheld for confidentiality. A withheld cell is not an absence of data and is never a zero. | never; 0 where none |
| `beneficiaries_latest` | The count from `measure_beneficiary_counts`, most recent year first, only where `method = 'pattern'`. | the published sentence carried no single number-and-year pair a pattern could read - 172 of 247 measures |
| `beneficiaries_latest_year` | That year. | as `beneficiaries_latest` |
| `beneficiaries_raw_en` | Finance's number-of-beneficiaries field as published in English, whether or not a count was parsed from it. | the English edition has no record for this measure, or left the field empty |
| `beneficiaries_raw_fr` | The same field as published in French. | as `beneficiaries_raw_en`, for French |
| `cost_per_beneficiary` | `cost_latest_estimate` converted to dollars and divided by `beneficiaries_latest`. Dollars per beneficiary, not millions. | either input is null, the two years differ, or the count is 0 |
| `cost_per_beneficiary_note` | `years_differ` where that is why the ratio is null. | the ratio was computed, or an input was missing for some other reason |
| `introduced_year` | The earliest year Finance lists in the implementation and recent history field. This is the earliest year **in that field**, which is not necessarily the year the measure was enacted. | no history row carries a year a pattern could read |
| `last_change_year` | The latest such year. | as `introduced_year` |
| `years_since_last_change` | `report_year` (2026) minus `last_change_year`. | `last_change_year` is null |
| `history_events` | Count of history rows Finance lists for the measure. | never; 0 where none |
| `objective_source_year` | The year in the trailing parenthetical Finance attaches to the objective field - `(Budget 1998)` gives 1998. Where the parenthetical names several documents the last year is taken. Nothing is read from the sentence itself. | the objective has no trailing parenthetical, or none with a year in it |
| `objective_source_raw` | That parenthetical as published, without its brackets. | the objective has no trailing parenthetical |
| `objective_source_method` | `pattern` where a year was read, else `none`. | never |
| `category_en` | Finance's category field, verbatim - structural, non-structural, or refundable credit. | Finance left the field empty, or the edition has no record |
| `category_fr` | The same field in French. | as `category_en` |
| `objective_category_en` | Finance's objective category field, verbatim. A measure may carry several, run together in one cell. | as `category_en` |
| `objective_category_fr` | The same field in French. | as `category_en` |
| `subject_en` | Finance's subject field, verbatim. | as `category_en` |
| `subject_fr` | The same field in French. | as `category_en` |
| `ccofog_code_en` | Finance's CCOFOG 2014 code, verbatim. | as `category_en` |
| `ccofog_code_fr` | The same field in French. | as `category_en` |
| `type_of_tax_en` | Finance's tax field, verbatim. | as `category_en` |
| `type_of_tax_fr` | The same field in French. | as `category_en` |
| `type_of_measure_en` | Finance's type-of-measure field, verbatim. | as `category_en` |
| `type_of_measure_fr` | The same field in French. | as `category_en` |
| `objective_category_internal` | 1 where every objective category the measure carries is one Finance's Part 3 lists under "Objectives that are internal to the tax system", else 0. Finance's own grouping, read from each edition's own markup and shipped as a fixture. | no category in the measure's cell matched Finance's published vocabulary - 9 measures, catalogued in `data/objective_categories_unmatched.csv` |
| `objective_category_mixed` | 1 where the measure carries both internal and other categories, so that an `objective_category_internal` of 0 can be told apart from a measure with no internal category at all. | as `objective_category_internal` |
| `has_overlapping_program` | 1 where Finance's "other relevant government programs" field names something, 0 where it says n/a. Finance's statement that related spending exists, and nothing more - not a duplication finding. | the field is empty in both editions |
| `overlapping_program_raw_en` | That field as published in English. | as `category_en` |
| `overlapping_program_raw_fr` | The same field in French. | as `category_en` |
| `provisions_cited` | Count of reference rows Finance lists for the measure, in the edition named by `measure_figure_basis.reference_lang`. | never; 0 where none |
| `provisions_resolved` | Of those, the count with `status = 'resolved'`. | never; 0 |
| `provisions_not_in_consolidation` | Of those, the count with `status = 'not_in_consolidation'` - the gap between the report's as-of date of 31 December 2025 and the consolidation's of 18 June 2026. | never; 0 |
| `provisions_repealed_stub` | Of the measure's resolved references, the count pointing at a provision whose whole text is a repeal tombstone - "[Repealed, 2001, c. 17, s. 3(1)]". The citation path still resolves, but the provision is gone. Distinct from `provisions_not_in_consolidation`, which is a path the consolidation never had: this is a path it has, pointing at nothing. | never; 0 |
| `sections_touched` | Distinct top-level sections among the resolved paths. The section is the leading run of the citation path before the first `(`, `"` or `~`, so `110(1)(d)` is section 110 and `54"principal residence"` is section 54. | never; 0 |
| `shared_with_measures` | Count of other measures citing at least one of the same resolved citation paths. A pure join over `measure_provision_overlap`. | never; 0 |
| `amending_acts_count` | Summed over the distinct top-level sections the measure cites: the number of statute entries in that section's Phase 0 `history_note` after the first. Entries are semicolon separated after the `[NOTE: ...]` prefix; the first entry is the enactment that put the section there, so the rest are amendments. **Double counts by design**: a section cited by several measures contributes to each, because this is a property of the measure's legal footprint and not a partition of the Act. | no section the measure cites carries a history note |
| `amending_acts_method` | `pattern` wherever a count was produced. | `amending_acts_count` is null |
| `earliest_end_date` | Earliest `end` bound extracted from the text of the provisions the measure cites. Whether that date has passed is **not** computed: there is no `is_expired` and no comparison against the build date, because "expired" depends on when you ask and on facts outside this dataset. | no cited provision has an extracted end bound - every row, until Phase 2 step 3 fills `provision_temporal_scope` |
| `latest_end_date` | The latest such bound. | as `earliest_end_date` |
| `has_step_down` | 1 where any cited provision has a `step_down` bound, else 0. | no cited provision has any extracted temporal scope |

---

## `measure_resolved_provisions`

Every resolved provision a measure cites, one row per reference, with the
top-level section it sits in. This is the join the legal-footprint indicators
and four of the canned views are built on, kept in one place so that the rule
for reading a section number out of a citation path is written once. Only the
edition named in `measure_figure_basis.reference_lang` is read, so a measure
present in both languages is not counted twice.

**Columns:** `measure_id`, `lang`, `order_index`, `act`, `section_id`, `citation_path`, `top_section`

**Rows in this build:** 332

```sql
CREATE VIEW measure_resolved_provisions AS
SELECT  r.measure_id,
        r.lang,
        r.order_index,
        s.act,
        s.id            AS section_id,
        s.citation_path,
        SUBSTR(s.citation_path, 1, MIN(
            CASE WHEN INSTR(s.citation_path,'(')>0 THEN INSTR(s.citation_path,'(')-1 ELSE LENGTH(s.citation_path) END,
            CASE WHEN INSTR(s.citation_path,'"')>0 THEN INSTR(s.citation_path,'"')-1 ELSE LENGTH(s.citation_path) END,
            CASE WHEN INSTR(s.citation_path,'~')>0 THEN INSTR(s.citation_path,'~')-1 ELSE LENGTH(s.citation_path) END))              AS top_section
FROM measure_references r
JOIN measure_figure_basis b
     ON b.measure_id = r.measure_id AND b.reference_lang = r.lang
JOIN sections s ON s.id = r.section_id
WHERE r.status = 'resolved';
```

---

## `measure_provision_overlap`

One row per pair of measures that cite the same resolved provision, with the
provision. A pure join: no threshold, no score, and no statement that sharing a
provision means anything. Each unordered pair appears once in each direction,
so that a query filtered to one measure sees all of its partners.

**Columns:** `measure_id`, `other_measure_id`, `act`, `citation_path`

**Rows in this build:** 230

```sql
CREATE VIEW measure_provision_overlap AS
SELECT  a.measure_id   AS measure_id,
        b2.measure_id  AS other_measure_id,
        a.act,
        a.citation_path
FROM measure_resolved_provisions a
JOIN measure_resolved_provisions b2
     ON b2.act = a.act
    AND b2.citation_path = a.citation_path
    AND b2.measure_id <> a.measure_id
GROUP BY a.measure_id, b2.measure_id, a.act, a.citation_path;
```

---

## `indicators`

One row per measure - 247, matching `measures` exactly, not one row per
language. The numeric indicators are language-independent; the copied
classification labels carry `_en` / `_fr` suffixes. `join_method` is carried
through so that the 36 measures that could not be paired across the two
editions stay visible in every query made over this view.

Every column is computed here from the Phase 0 and Phase 1 tables and from the
Phase 2 extraction tables. Nothing is stored, nothing is imputed, and a null
input produces a null output rather than a zero.

**Columns:** `measure_id`, `join_method`, `name_en`, `name_fr`, `cost_figure_basis`, `cost_figure_row_label`, `cost_edition`, `cost_latest_estimate`, `cost_latest_estimate_year`, `cost_latest_estimate_raw`, `cost_latest_projection`, `cost_latest_projection_year`, `cost_latest_projection_raw`, `cost_first_estimate`, `cost_first_estimate_year`, `cost_first_estimate_raw`, `cost_change_abs`, `cost_change_pct`, `cost_status`, `cost_withheld_years`, `beneficiaries_latest`, `beneficiaries_latest_year`, `beneficiaries_raw_en`, `beneficiaries_raw_fr`, `cost_per_beneficiary`, `cost_per_beneficiary_note`, `introduced_year`, `last_change_year`, `years_since_last_change`, `history_events`, `objective_source_year`, `objective_source_raw`, `objective_source_method`, `category_en`, `category_fr`, `objective_category_en`, `objective_category_fr`, `subject_en`, `subject_fr`, `ccofog_code_en`, `ccofog_code_fr`, `type_of_tax_en`, `type_of_tax_fr`, `type_of_measure_en`, `type_of_measure_fr`, `objective_category_internal`, `objective_category_mixed`, `has_overlapping_program`, `overlapping_program_raw_en`, `overlapping_program_raw_fr`, `provisions_cited`, `provisions_resolved`, `provisions_not_in_consolidation`, `provisions_repealed_stub`, `sections_touched`, `shared_with_measures`, `amending_acts_count`, `amending_acts_method`, `earliest_end_date`, `latest_end_date`, `has_step_down`

**Rows in this build:** 247

```sql
CREATE VIEW indicators AS
WITH base AS (
    SELECT
        m.id                AS measure_id,
        b.cost_lang, b.cost_basis, b.cost_row_label,
        b.reference_lang, b.text_lang,

        (SELECT c.value_millions FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'estimate'
          ORDER BY c.year DESC LIMIT 1)                 AS latest_estimate,
        (SELECT c.year FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'estimate'
          ORDER BY c.year DESC LIMIT 1)                 AS latest_estimate_year,
        (SELECT c.raw_value FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'estimate'
          ORDER BY c.year DESC LIMIT 1)                 AS latest_estimate_raw,
        (SELECT c.value_millions FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'estimate'
          ORDER BY c.year ASC LIMIT 1)                  AS first_estimate,
        (SELECT c.year FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'estimate'
          ORDER BY c.year ASC LIMIT 1)                  AS first_estimate_year,
        (SELECT c.raw_value FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'estimate'
          ORDER BY c.year ASC LIMIT 1)                  AS first_estimate_raw,
        (SELECT c.value_millions FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'projection'
          ORDER BY c.year DESC LIMIT 1)                 AS latest_projection,
        (SELECT c.year FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'projection'
          ORDER BY c.year DESC LIMIT 1)                 AS latest_projection_year,
        (SELECT c.raw_value FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.row_label = b.cost_row_label AND c.value_kind = 'projection'
          ORDER BY c.year DESC LIMIT 1)                 AS latest_projection_raw,

        (SELECT COUNT(DISTINCT c.year) FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang) AS years_published,
        (SELECT COUNT(DISTINCT c.year) FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.value_kind IN ('estimate','projection'))    AS years_numeric,
        (SELECT COUNT(DISTINCT c.year) FROM measure_costs c
          WHERE c.measure_id = m.id AND c.lang = b.cost_lang
            AND c.value_kind = 'withheld_confidential')       AS withheld_years,

        (SELECT bc.count FROM measure_beneficiary_counts bc
          WHERE bc.measure_id = m.id AND bc.method = 'pattern'
          ORDER BY bc.year DESC LIMIT 1)                AS beneficiaries_latest,
        (SELECT bc.year FROM measure_beneficiary_counts bc
          WHERE bc.measure_id = m.id AND bc.method = 'pattern'
          ORDER BY bc.year DESC LIMIT 1)                AS beneficiaries_latest_year,

        (SELECT MIN(h.year) FROM measure_history h
          WHERE h.measure_id = m.id AND h.year IS NOT NULL)   AS introduced_year,
        (SELECT MAX(h.year) FROM measure_history h
          WHERE h.measure_id = m.id AND h.year IS NOT NULL)   AS last_change_year,
        (SELECT COUNT(*) FROM measure_history h
          WHERE h.measure_id = m.id)                          AS history_events,

        (SELECT os.year FROM measure_objective_source os
          WHERE os.measure_id = m.id AND os.lang = b.text_lang) AS objective_source_year,
        (SELECT os.raw_text FROM measure_objective_source os
          WHERE os.measure_id = m.id AND os.lang = b.text_lang) AS objective_source_raw,
        (SELECT os.method FROM measure_objective_source os
          WHERE os.measure_id = m.id AND os.lang = b.text_lang) AS objective_source_method,

        (SELECT COUNT(*) FROM measure_objective_categories oc
          WHERE oc.measure_id = m.id AND oc.lang = b.text_lang) AS objective_categories,
        (SELECT COUNT(*) FROM measure_objective_categories oc
          WHERE oc.measure_id = m.id AND oc.lang = b.text_lang
            AND oc.group_name = 'internal')                    AS objective_categories_internal,

        (SELECT COUNT(*) FROM measure_references r
          WHERE r.measure_id = m.id AND r.lang = b.reference_lang) AS provisions_cited,
        (SELECT COUNT(*) FROM measure_references r
          WHERE r.measure_id = m.id AND r.lang = b.reference_lang
            AND r.status = 'resolved')                             AS provisions_resolved,
        (SELECT COUNT(*) FROM measure_references r
          WHERE r.measure_id = m.id AND r.lang = b.reference_lang
            AND r.status = 'not_in_consolidation')                 AS provisions_not_in_consolidation,
        (SELECT COUNT(*) FROM measure_references r
          JOIN sections rs ON rs.id = r.section_id
          WHERE r.measure_id = m.id AND r.lang = b.reference_lang
            AND r.status = 'resolved'
            AND rs.is_repealed_stub = 1)                           AS provisions_repealed_stub,
        (SELECT COUNT(DISTINCT p.act || ' ' || p.top_section)
           FROM measure_resolved_provisions p
          WHERE p.measure_id = m.id)                               AS sections_touched,
        (SELECT COUNT(DISTINCT o.other_measure_id)
           FROM measure_provision_overlap o
          WHERE o.measure_id = m.id)                               AS shared_with_measures,
        (SELECT SUM(aa.amending_entries) FROM (
            SELECT DISTINCT p.act, p.top_section
              FROM measure_resolved_provisions p
             WHERE p.measure_id = m.id) cited
          JOIN sections t ON t.act = cited.act
                         AND t.citation_path = cited.top_section
                         AND t.level = 'section'
          JOIN section_amending_acts aa ON aa.section_id = t.id)   AS amending_acts_count,

        (SELECT MIN(COALESCE(t.bound_date, PRINTF('%04d', t.bound_year)))
           FROM provision_temporal_scope t
           JOIN measure_resolved_provisions p ON p.section_id = t.cited_section_id
          WHERE p.measure_id = m.id AND t.bound_kind = 'end')      AS earliest_end_date,
        (SELECT MAX(COALESCE(t.bound_date, PRINTF('%04d', t.bound_year)))
           FROM provision_temporal_scope t
           JOIN measure_resolved_provisions p ON p.section_id = t.cited_section_id
          WHERE p.measure_id = m.id AND t.bound_kind = 'end')      AS latest_end_date,
        (SELECT COUNT(*)
           FROM provision_temporal_scope t
           JOIN measure_resolved_provisions p ON p.section_id = t.cited_section_id
          WHERE p.measure_id = m.id)                               AS temporal_rows,
        (SELECT COUNT(*)
           FROM provision_temporal_scope t
           JOIN measure_resolved_provisions p ON p.section_id = t.cited_section_id
          WHERE p.measure_id = m.id AND t.bound_kind = 'step_down') AS step_down_rows
    FROM measures m
    JOIN measure_figure_basis b ON b.measure_id = m.id
)
SELECT
    m.id                            AS measure_id,
    m.join_method,
    m.name_en,
    m.name_fr,

    b.cost_basis                    AS cost_figure_basis,
    b.cost_row_label                AS cost_figure_row_label,
    b.cost_lang                     AS cost_edition,
    b.latest_estimate               AS cost_latest_estimate,
    b.latest_estimate_year          AS cost_latest_estimate_year,
    b.latest_estimate_raw           AS cost_latest_estimate_raw,
    b.latest_projection             AS cost_latest_projection,
    b.latest_projection_year        AS cost_latest_projection_year,
    b.latest_projection_raw         AS cost_latest_projection_raw,
    b.first_estimate                AS cost_first_estimate,
    b.first_estimate_year           AS cost_first_estimate_year,
    b.first_estimate_raw            AS cost_first_estimate_raw,
    CASE WHEN b.latest_estimate IS NOT NULL
          AND b.first_estimate  IS NOT NULL
          AND b.latest_estimate_year <> b.first_estimate_year
         THEN b.latest_estimate - b.first_estimate END       AS cost_change_abs,
    CASE WHEN b.latest_estimate IS NOT NULL
          AND b.first_estimate  IS NOT NULL
          AND b.latest_estimate_year <> b.first_estimate_year
          AND b.first_estimate <> 0
         THEN (b.latest_estimate - b.first_estimate) / b.first_estimate END
                                                             AS cost_change_pct,
    CASE WHEN b.years_published = 0          THEN 'no_cost_table'
         WHEN b.withheld_years  > 0          THEN 'withheld'
         WHEN b.years_numeric   = 0          THEN 'not_costed'
         WHEN b.years_numeric   = b.years_published THEN 'costed'
         ELSE 'partially_costed' END                         AS cost_status,
    b.withheld_years                AS cost_withheld_years,

    b.beneficiaries_latest,
    b.beneficiaries_latest_year,
    m.number_of_beneficiaries_en    AS beneficiaries_raw_en,
    m.number_of_beneficiaries_fr    AS beneficiaries_raw_fr,
    CASE WHEN b.latest_estimate IS NOT NULL
          AND b.beneficiaries_latest IS NOT NULL
          AND b.beneficiaries_latest <> 0
          AND b.latest_estimate_year = b.beneficiaries_latest_year
         THEN b.latest_estimate * 1000000.0 / b.beneficiaries_latest END
                                                             AS cost_per_beneficiary,
    CASE WHEN b.latest_estimate IS NOT NULL
          AND b.beneficiaries_latest IS NOT NULL
          AND b.latest_estimate_year <> b.beneficiaries_latest_year
         THEN 'years_differ' END                             AS cost_per_beneficiary_note,

    b.introduced_year,
    b.last_change_year,
    CASE WHEN b.last_change_year IS NOT NULL
         THEN m.report_year - b.last_change_year END         AS years_since_last_change,
    b.history_events,

    b.objective_source_year,
    b.objective_source_raw,
    b.objective_source_method,

    m.category_en, m.category_fr,
    m.objective_category_en, m.objective_category_fr,
    m.subject_en, m.subject_fr,
    m.ccofog_2014_code_en AS ccofog_code_en,
    m.ccofog_2014_code_fr AS ccofog_code_fr,
    m.tax_en AS type_of_tax_en, m.tax_fr AS type_of_tax_fr,
    m.type_of_measure_en, m.type_of_measure_fr,
    CASE WHEN b.objective_categories = 0 THEN NULL
         WHEN b.objective_categories_internal = b.objective_categories THEN 1
         ELSE 0 END                                          AS objective_category_internal,
    CASE WHEN b.objective_categories = 0 THEN NULL
         WHEN b.objective_categories_internal > 0
          AND b.objective_categories_internal < b.objective_categories THEN 1
         ELSE 0 END                                          AS objective_category_mixed,
    CASE WHEN COALESCE(m.other_relevant_government_programs_en,
                       m.other_relevant_government_programs_fr) IS NULL THEN NULL
         WHEN TRIM(LOWER(COALESCE(m.other_relevant_government_programs_en,
                                  m.other_relevant_government_programs_fr)))
              IN ('n/a','s.o.','s. o.','n.a.') THEN 0
         ELSE 1 END                                          AS has_overlapping_program,
    m.other_relevant_government_programs_en AS overlapping_program_raw_en,
    m.other_relevant_government_programs_fr AS overlapping_program_raw_fr,

    b.provisions_cited,
    b.provisions_resolved,
    b.provisions_not_in_consolidation,
    b.provisions_repealed_stub,
    b.sections_touched,
    b.shared_with_measures,
    b.amending_acts_count,
    CASE WHEN b.amending_acts_count IS NOT NULL THEN 'pattern' END
                                                             AS amending_acts_method,

    b.earliest_end_date,
    b.latest_end_date,
    CASE WHEN b.temporal_rows = 0 THEN NULL
         WHEN b.step_down_rows > 0 THEN 1 ELSE 0 END         AS has_step_down
FROM measures m
JOIN base b ON b.measure_id = m.id;
```

---

## `v_not_costed`

Measures where Finance published a cost table and no year in it carries a
number. This is a measurement result, not a publishing decision: measures with
no cost table at all are `no_cost_table` and are not here. The view says
nothing about whether a measure should be costed.

**Columns:** `measure_id`, `name_en`, `name_fr`, `join_method`, `cost_figure_basis`, `cost_status`, `provisions_cited`, `provisions_resolved`

**Rows in this build:** 10

```sql
CREATE VIEW v_not_costed AS
SELECT measure_id, name_en, name_fr, join_method, cost_figure_basis,
       cost_status, provisions_cited, provisions_resolved
FROM indicators
WHERE cost_status = 'not_costed';
```

---

## `v_withheld`

Measures with at least one cost cell published as "X", which Finance's own
legend defines as withheld for confidentiality. A withheld cell is not an
absence of data and is never a zero; the count of years affected is given so a
reader can see how much of the series is missing by Finance's choice.

**Columns:** `measure_id`, `name_en`, `name_fr`, `join_method`, `cost_withheld_years`, `cost_status`, `cost_figure_basis`

**Rows in this build:** 9

```sql
CREATE VIEW v_withheld AS
SELECT measure_id, name_en, name_fr, join_method,
       cost_withheld_years, cost_status, cost_figure_basis
FROM indicators
WHERE cost_withheld_years > 0;
```

---

## `v_no_beneficiary_count`

Measures with no parsed beneficiary count, with the published sentence in
both languages. Mostly this is a statement about the prose of Finance's
"number of beneficiaries" field rather than about the measure: only 75 of the
published sentences carry a single number-and-year pair that a pattern can
read, and all 75 are in the English edition.

**Columns:** `measure_id`, `name_en`, `name_fr`, `join_method`, `beneficiaries_raw_en`, `beneficiaries_raw_fr`

**Rows in this build:** 172

```sql
CREATE VIEW v_no_beneficiary_count AS
SELECT measure_id, name_en, name_fr, join_method,
       beneficiaries_raw_en, beneficiaries_raw_fr
FROM indicators
WHERE beneficiaries_latest IS NULL;
```

---

## `v_end_bound_by_year`

One row per extracted end bound on a provision a measure cites, with the
year as a column. The view is not filtered to any year: SQLite views take no
parameters, and a view named for a threshold would make the choice of
threshold look like a finding. The reader supplies it -
`WHERE end_year < 2027`. Whether a bound has passed is not computed here.

Empty until Phase 2 step 3 fills `provision_temporal_scope`.

**Columns:** `measure_id`, `name_en`, `name_fr`, `act`, `cited_citation_path`, `provision_citation_path`, `phrase`, `bound_kind`, `bound_date`, `bound_precision`, `end_year`, `method`

**Rows in this build:** 695

```sql
CREATE VIEW v_end_bound_by_year AS
SELECT p.measure_id,
       m.name_en, m.name_fr,
       p.act,
       p.citation_path AS cited_citation_path,
       s.citation_path AS provision_citation_path,
       t.phrase,
       t.bound_kind,
       t.bound_date,
       t.bound_precision,
       COALESCE(t.bound_year, CAST(SUBSTR(t.bound_date,1,4) AS INTEGER)) AS end_year,
       t.method
FROM provision_temporal_scope t
JOIN sections s ON s.id = t.section_id
JOIN measure_resolved_provisions p ON p.section_id = t.cited_section_id
JOIN measures m ON m.id = p.measure_id
WHERE t.bound_kind = 'end';
```

---

## `v_last_change_by_year`

One row per measure with the latest year Finance lists in its implementation
and recent history field, as a column for the reader to filter on. A null year
means no history event carried a year a pattern could read, which is not the
same as no change.

**Columns:** `measure_id`, `name_en`, `name_fr`, `join_method`, `introduced_year`, `last_change_year`, `years_since_last_change`, `history_events`

**Rows in this build:** 247

```sql
CREATE VIEW v_last_change_by_year AS
SELECT measure_id, name_en, name_fr, join_method,
       introduced_year, last_change_year, years_since_last_change,
       history_events
FROM indicators;
```

---

## `v_objective_internal`

Measures every one of whose objective categories Finance's Part 3 lists
under "Objectives that are internal to the tax system". Finance's grouping,
read from each edition's own markup and shipped as a fixture. Measures carrying
both internal and other categories are excluded here and are marked
`objective_category_mixed` in `indicators`.

**Columns:** `measure_id`, `name_en`, `name_fr`, `join_method`, `objective_category_en`, `objective_category_fr`, `category_en`, `category_fr`, `cost_status`

**Rows in this build:** 70

```sql
CREATE VIEW v_objective_internal AS
SELECT measure_id, name_en, name_fr, join_method,
       objective_category_en, objective_category_fr,
       category_en, category_fr, cost_status
FROM indicators
WHERE objective_category_internal = 1;
```

---

## `v_overlapping_programs`

Measures where Finance's "other relevant government programs" field names
something. This is Finance's statement that related spending exists and nothing
more: it is not a duplication finding, and the field text travels with the flag
so a reader can see what was actually said.

**Columns:** `measure_id`, `name_en`, `name_fr`, `join_method`, `overlapping_program_raw_en`, `overlapping_program_raw_fr`

**Rows in this build:** 208

```sql
CREATE VIEW v_overlapping_programs AS
SELECT measure_id, name_en, name_fr, join_method,
       overlapping_program_raw_en, overlapping_program_raw_fr
FROM indicators
WHERE has_overlapping_program = 1;
```

---

## `v_shared_provisions`

Resolved provisions cited by more than one measure, with the measures. A
provision appearing here is one Finance's report reaches from several
directions; the view counts the measures and lists them, and draws no
conclusion from the count.

**Columns:** `act`, `citation_path`, `measures_citing`, `measure_ids`

**Rows in this build:** 34

```sql
CREATE VIEW v_shared_provisions AS
SELECT p.act,
       p.citation_path,
       COUNT(DISTINCT p.measure_id) AS measures_citing,
       GROUP_CONCAT(DISTINCT p.measure_id) AS measure_ids
FROM measure_resolved_provisions p
GROUP BY p.act, p.citation_path
HAVING COUNT(DISTINCT p.measure_id) > 1;
```

---

## `v_not_in_consolidation`

Measures citing a provision the consolidation does not contain, with the
reference as published. This is the as-of-date gap - the report states the law
as at 31 December 2025 and the consolidation is dated 18 June 2026 - and it is
not an error by Finance or by Justice Canada.

**Columns:** `measure_id`, `name_en`, `name_fr`, `raw_text`, `instrument`, `citation_path`, `lang`, `reason`

**Rows in this build:** 13

```sql
CREATE VIEW v_not_in_consolidation AS
SELECT r.measure_id,
       m.name_en, m.name_fr,
       r.raw_text,
       r.instrument,
       r.citation_path,
       r.lang,
       r.reason
FROM measure_references r
JOIN measure_figure_basis b
     ON b.measure_id = r.measure_id AND b.reference_lang = r.lang
JOIN measures m ON m.id = r.measure_id
WHERE r.status = 'not_in_consolidation';
```

---

## `v_provision_footprint`

For every resolved provision: the measure citing it, and the number of other
measures that cite the same provision or another provision of the same section.
One row per (provision, measure) pair, which is the longer shape and the useful
one - a reader asking about a single provision filters
`WHERE citation_path = '20(1)(ss)'` and sees each measure on its own row.

**Columns:** `act`, `citation_path`, `top_section`, `measure_id`, `name_en`, `name_fr`, `other_measures_citing_provision`, `other_measures_in_section`

**Rows in this build:** 332

```sql
CREATE VIEW v_provision_footprint AS
SELECT p.act,
       p.citation_path,
       p.top_section,
       p.measure_id,
       m.name_en,
       m.name_fr,
       (SELECT COUNT(DISTINCT q.measure_id) FROM measure_resolved_provisions q
         WHERE q.act = p.act AND q.citation_path = p.citation_path
           AND q.measure_id <> p.measure_id)            AS other_measures_citing_provision,
       (SELECT COUNT(DISTINCT q.measure_id) FROM measure_resolved_provisions q
         WHERE q.act = p.act AND q.top_section = p.top_section
           AND q.measure_id <> p.measure_id)            AS other_measures_in_section
FROM measure_resolved_provisions p
JOIN measures m ON m.id = p.measure_id
GROUP BY p.act, p.citation_path, p.measure_id;
```
