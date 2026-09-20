# Portage (working title)

Bilingual, open dataset making Canada's federal Income Tax Act navigable for
the public interest. Phase 0 turns the Act and its Regulations into
subsection-level records with full citation paths. Later phases link each
record to Finance Canada's tax expenditure report and publish indicators.

Owner: Matt. Generalist, not a tax expert, not a professional developer.
Explain choices in plain language. Prefer boring, well-documented tools.

## Principles (non-negotiable)

- Evidence, not recommendations. The tool returns text, citations, costs,
  dates and cross-references. It never says a provision should change.
- Provenance on everything. Every record carries its source URL and the
  snapshot date it was taken from.
- Text is reproduced exactly as published. No paraphrase, no cleanup that
  changes meaning, no inferred structure.
- Bilingual from the start. Every record has English and French text,
  linked by the same citation path.
- Attribution to sections is mechanical, never judgment. If a mapping needs
  a human tax opinion, it does not go in the data.
- Open source (MIT for code). Data follows the Open Government Licence
  terms of Justice Canada and Finance Canada, with attribution.

## Phase 0 scope

Deliver one SQLite file, `portage.sqlite`, containing:

1. `sections`: one row per addressable unit of the Income Tax Act
   (RSC 1985, c 1 (5th Supp)) and the Income Tax Regulations
   (CRC, c 945): section, subsection, paragraph, subparagraph, clause.
   Plus non-addressable rows (`is_addressable = 0`) for text that belongs
   to a unit but is not itself citable - continued text, definitions,
   formulas, headings. Those carry a derived path containing `~`, which
   is deliberately not valid citation syntax.

   Identity and structure:
     id, act, citation_path, level, parent_id, parent_path,
     order_index (English document order), order_index_fr (French),
     is_addressable, UNIQUE (act, citation_path)

   Labels, as published and as derived:
     label_raw, label_raw_fr - verbatim, never altered
     label_anomaly, anomaly_reason, label_anomaly_fr, anomaly_reason_fr

   Content:
     heading_en, heading_fr (from MarginalNote)
     text_en, text_fr
     defined_term_en, defined_term_fr (definitions are keyed by term)
     history_note (section level only - the source attaches it there)

   Bilingual state:
     bilingual_gap - the path exists in one language only
     alignment_unverified - the path exists in both, but its parent's
       set of child labels differs between the files, so a shared label
       is not evidence that the two texts correspond. Consumers wanting
       only verified pairs filter bilingual_gap = 0 AND
       alignment_unverified = 0.

   Provenance:
     source_url, source_url_fr

2. `cross_references`: one row per reference from one unit to another
   found in the text (from_id, to_citation_path, to_id if resolved,
   raw_text). Mechanical extraction only.
3. FTS5 virtual tables over text_en and text_fr.
4. A `meta` table with source, consolidation_date and retrieved_date
   (kept separate - one describes the law, the other our copy), build
   timestamp, and row counts.
5. Catalogue files, written by the build and diffed against committed
   fixtures in `tests/fixtures/`. Anomalies are catalogued, never
   counted - a bare number passes while a case moves silently:
     data/label_anomalies.csv
     data/definition_key_fallbacks.csv
     data/bilingual_gaps.csv
     data/alignment_unverified.csv

Nothing else in Phase 0. No embeddings, no web front end, no MCP server
yet. Those are later phases.

## Data source

Primary: A2AJ Canadian Legal Data, federal legislation, Parquet/HuggingFace.
See https://a2aj.ca/data/ for current locations. Check first whether their
records preserve the Justice Laws XML hierarchy. If they are flat text,
fall back to the official Justice Laws XML for the two instruments
(laws-lois.justice.gc.ca) and record which source was used in `meta`.

Parse from XML structure only. Never infer structure from bold text,
line breaks, indentation or number patterns. Three attribution bugs
came from text heuristics during scoping; that approach is banned.

## Acceptance tests (pytest, must pass before anything is published)

1. Round-trip: concatenating text_en of all records in order_index order
   reproduces the source text of the Act exactly (after a documented,
   minimal whitespace normalization). Same for French.
2. Structure: every record has a parent (except top-level sections);
   citation paths are unique; section numbers appear in source order;
   section count matches the Justice Laws table of contents.
3. Known citations resolve to the right text. Fixtures:
   - 245(1) contains the definition of "tax benefit"
   - 125(7) contains the definition of "active business carried on by
     a corporation"
   - 248(1) contains a definition of "active business"
   - 95(1) contains a definition of "active business" (foreign affiliate)
   - 87(4) exists as its own record under 87
   - 55(3)(b) exists as its own record under 55(3)
   - 118.02(2) text contains "before 2025"
   - 127.44(1) text contains "2040"
4. Spot-check file: `tests/spot_checks.md` lists 20 random citation paths
   with the first sentence of their text, for Matt to verify by hand
   against laws-lois.justice.gc.ca. Regenerate on every build.
5. Cross-references: every `to_citation_path` that matches an existing
   record resolves; unresolved ones are listed in a report, not dropped.

## Stack

Python 3.11+, pandas, pyarrow, lxml, sqlite3 (stdlib), pytest. Add nothing
else for Phase 0 without saying why. Everything runs on a laptop with
`python -m portage.build`. No servers, no accounts, no API calls.

## Working conventions

- Start every session by reading this file and `PLAN.md`.
- Before writing code: inspect the real source data and describe its
  structure in `docs/source-notes.md`. Do not assume.
- Small commits with plain-language messages.
- Stage files explicitly by name. Never `git add -A` or `git add .`.
  If untracked files exist at commit time, list them and ask before
  including any. Twice a section written by Matt was swept into a commit
  whose message said nothing about it.
- When something is uncertain (source format, licence terms, an
  ambiguous citation), stop and ask rather than guess.
- Log every design decision in `docs/decisions.md` with the date.
- Keep the README honest: what the data is, what it is not, source,
  snapshot date, licence, and the sentence "This dataset makes provisions
  navigable. It does not interpret them and is not legal advice."

  "# Phase 1: Finance tax expenditure map"

Phase 0 delivered the Act and Regulations as subsection-level records in
both languages, verified by round-trip, uniqueness on the shipped key,
symmetric bilingual join, and hand spot checks. Phase 1 links Finance
Canada's Report on Federal Tax Expenditures to those records. Same
principles: evidence not recommendations, provenance on everything,
Finance's own references only (Tier 1), no tax opinions in the data.

## Order of work

1. Tagged cross-references first. Build `cross_references` from the
   XRefExternal, XRefInternal and DefinitionRef elements already in the
   XML, with method='tagged'. Resolve DefinitionRef to definition records.
   This is the resolution machinery Phase 1 reuses.
2. Inspect the report before parsing it (source-notes first, as in
   Phase 0).
3. Parse, resolve, catalogue, test.

## Source

Report on Federal Tax Expenditures 2026, Department of Finance Canada,
Parts 3 to 7 (Part 3 is the introduction to the descriptions; Parts 4
to 7 hold the measures, alphabetically). English:
https://www.canada.ca/en/department-finance/services/publications/federal-tax-expenditures/2026/part-3.html
and the corresponding part-4 to part-7 pages. Find the French edition
from the page's language toggle and record its URLs. Check whether the
same data exists on open.canada.ca under the Open Government Licence;
if so, record both, prefer the OGL terms, and quote the canada.ca terms
too.

Each measure on the page is a fixed-field block. Expected fields:
description, type of tax, beneficiaries, type of measure, legal
reference, implementation and recent history, objective (with the
budget or document that stated it), category, reason it is not part
of the benchmark, subject, CCOFOG code, other relevant government
programs, source of data, estimation method, projection method, number
of beneficiaries, and a cost table (millions of dollars by year,
projections included). Confirm the actual field set in
docs/source-notes.md before writing the parser. Fields absent for a
measure are stored as null, never as an empty string or zero.

## Tables

- `measures`: id, name_en, name_fr, report_year, part, source_url_en,
  source_url_fr, retrieved_date, plus one column per descriptive field
  in each language (type_of_tax_en/fr, beneficiaries_en/fr, ... ).
  Keep Finance's wording verbatim.
- `measure_references`: measure_id, raw_text (the legal reference cell
  as published), instrument (ITA or ITR or other), citation_path,
  resolved (0/1), method ('pattern'), order_index. One row per
  provision Finance lists. Unresolved rows stay in the table.
- `measure_costs`: measure_id, year, value_millions (nullable),
  value_kind: one of 'estimate', 'projection', 'small' (published as
  "S"), 'not_available' (published as "n.a."), 'no_estimate'
  (published as "No estimate is available" or equivalent). The
  published token is kept in `raw_value`. None of these is ever
  stored as 0.
- `measure_history`: measure_id, year (if parseable), text_en, text_fr,
  order_index. One row per event Finance lists under implementation
  and recent history.
- `measure_beneficiary_counts`: measure_id, year, count, raw_value.

## Bilingual join

Measures are ordered alphabetically in each language, so order differs
between editions, exactly as definitions did in Phase 0. Do not join by
position. Join on the language-independent content: the set of legal
references plus the cost table values, which are identical numbers in
both editions. Any measure that does not join uniquely is catalogued in
data/measure_join_gaps.csv with a fixture, and both language records
survive as singles.

## Reference extraction rule

Legal references are a short structured field, not prose. Extraction
by pattern is permitted here because failure is visible: a reference
either resolves to an existing citation_path or it does not. Write the
grammar into docs/reference-rule.md before implementing (section,
subsection, paragraph, subparagraph, clause; ranges "to"; lists "and";
"of the Act", "of the Regulations"; Part and Schedule references).
Anything the grammar does not cover is stored unresolved with the raw
text, never dropped and never guessed.

## Acceptance tests

1. Every measure on every page is captured: count of parsed measures
   equals the count of measure headings on the page, both languages.
2. Every measure has at least one measure_references row, or is listed
   in data/measures_without_references.csv (fixture).
3. Resolution rate is reported, not asserted. Unresolved references go
   to data/unresolved_references.csv (fixture). A build that resolves
   100% is suspicious, not good.
4. Fixture check: "Deferral for asset transfers to a corporation and
   corporate reorganizations" resolves to sections 55, 85, 87 and 88 and
   has no cost estimate for any year (value_kind 'no_estimate').
5. Fixture check: the measure whose legal reference is paragraph
   20(1)(ss) resolves to citation_path 20(1)(ss) in the Act.
6. Cost tokens: every distinct raw_value seen across all cost cells is
   listed in data/cost_tokens.csv with its mapped value_kind (fixture).
   A new token fails the build until it is classified.
7. Bilingual join: every joined measure pair has identical
   measure_references sets and identical measure_costs values.
8. Precision sample: tests/spot_checks/references.md lists 30 random
   (raw_text, citation_path) pairs for Matt to confirm by hand, seeded,
   never overwritten once results are recorded.

## Explicitly out of Phase 1

- Interacting provisions Finance does not list (Tier 2). Expose the
  Act's cross-reference graph instead; no curated additions.
- Any indicator, ranking or score. That is Phase 2, and it is computed
  from these tables, never stored as judgment inside them.
- Temporal scope extraction from the Act's text (also Phase 2).
- Any front end.

Phase 2: Indicators

Phase 1 delivered Finance's tax expenditure map as data: 229 measures per language, references resolved to the Act and Regulations, cost tables verified against Finance's own CSV, two hand-checked precision samples. Phase 2 computes indicators over those tables so that a reader can sort, filter and compare. It produces facts with derivations. It never produces a score, a rank, a weight, or a recommendation.

The line this phase must not cross

An indicator is a number or category that a reader could recompute from the published sources by following a written formula. If a column would need a judgment call to fill (is this measure worth keeping, is this loophole-shaped, is this fair), it does not exist in this dataset. "Low-hanging fruit" is something a human concludes after reading the indicators; the dataset only makes the reading possible.

Concretely:

No composite index. No column that combines two indicators with a weight.
No ordering baked into the data. Sorting is the reader's action in the front end or query.
Every indicator column has a derivation entry in docs/indicator-definitions.md: formula, inputs, what null means, and the source of each input. The build fails if a column exists without an entry (keep the definitions as a dict in code and generate the doc from it, then test that the doc is current).
Null is null. A measure with no cost estimate has null cost, never zero. A ratio with a null input is null. Nothing is imputed.
Finance's caveats travel with the number: value_kind and raw_value are carried through to any indicator that uses a cost cell.
Small is not waste. Nothing in the data or the docs characterizes a low-cost or low-claimant measure as a candidate for anything.
Indicators (one row per measure in indicators)

Cost, from measure_costs:

cost_latest_estimate, cost_latest_estimate_year: the most recent year with value_kind='estimate' (projections excluded). Null if none.
cost_latest_projection, cost_latest_projection_year.
cost_first_estimate, cost_first_estimate_year: earliest estimate year in the report's window.
cost_change_abs, cost_change_pct: latest estimate minus first estimate, and the ratio; null if either is non-numeric or the years are equal.
cost_status: one of costed (numeric in every year), partially_costed (numeric in some years), not_costed (Finance published a cost table and no year in it carries a number), no_cost_table (Finance published no cost table at all), withheld (any X cell). Derived from value_kind only; withheld takes precedence. Five values, not four: 53 measures have no cost table, and folding them into not_costed merges a measurement result with a publishing decision.
cost_figure_basis: which published row the cost figures are read from - total_row, single_component, components_only, multiple_total_rows, or no_cost_table. The last two carry null cost figures: adding components Finance did not add would be arithmetic it did not publish, and five measures publish several Total rows because they publish more than one cost table, where choosing between them would be judgment.

Beneficiaries, from measure_beneficiary_counts:

beneficiaries_latest, beneficiaries_latest_year: only where method='pattern'. Null otherwise, with beneficiaries_raw_en and beneficiaries_raw_fr carrying the published sentence in both cases. Two columns, not one: a single column would drop the published French sentence whenever an English one exists, and the field is a copied label like the classification labels, which already carry _en / _fr.
cost_per_beneficiary: cost_latest_estimate divided by beneficiaries_latest only when the years match; otherwise null and cost_per_beneficiary_note says the years differ. In dollars per beneficiary - the cost cell is in millions, so the view multiplies by a million first. Read literally the division would give millions of dollars per beneficiary, which is recomputable but not readable.

Age and history, from measure_history and the objective field:

introduced_year: earliest year in measure_history, if parseable.
last_change_year: latest year in measure_history.
years_since_last_change: report year minus last_change_year.
objective_source_year: the year in the parenthetical Finance attaches to the objective ("(Budget 1998)"). Extracted by pattern from that short field; method column; raw text kept; null if absent.

Classification, copied from Finance's fields, no interpretation:

category (structural / non-structural / refundable credit).
objective_category, and objective_category_internal (1 if Finance's Part 3 lists that category under "objectives that are internal to the tax system", else 0). This is Finance's own grouping; store the list as a fixture.
subject, ccofog_code, type_of_tax, type_of_measure.
has_overlapping_program: 1 if the "other relevant government programs" field is non-null and not "n/a". The field text is stored beside it. This is Finance's statement that related spending exists, nothing more.

Legal footprint, from measure_references joined to sections:

provisions_cited: count of reference rows.
provisions_resolved: count with status resolved.
sections_touched: distinct top-level sections.
provisions_not_in_consolidation: count with that status (the as-of-date mismatch).
shared_with_measures: count of other measures citing at least one of the same resolved citation_paths, and a separate measure_provision_ overlap table listing the pairs. Pure join.
amending_acts_count: from Phase 0 history_note on each cited section: the number of amending-statute entries in the note (they are semicolon-separated, "1994, c. 7, Sch. II, s. 15"). Pattern extraction over a formulaic field; method column; catalogue of unparsed notes with fixture. Summed over the measure's cited sections, with a note that a section shared by several measures is counted for each.

Temporal scope, from the text of cited provisions:

This is the one extraction that needs a model. For each cited provision, extract date-bounded conditions ("taxation years before 2025", "acquired after 2024 and before 2035", "on or before March 31, 2027") into a provision_temporal_scope table: section id, phrase exactly as it appears in the text, bound_kind (start / end / step-down), date or year, and method='extracted_llm'.
Rules: the phrase must be a verbatim substring of text_en (a test asserts this for every row); the model never infers a date that the text does not state; the extraction prompt, model name and run date are recorded in meta; the API is called from a batch script, never from the build, and its output is committed as data with a fixture.
Indicators derived: earliest_end_date, latest_end_date across a measure's provisions, and has_step_down. Whether a date has "passed" is not computed; the reader compares against their own date.
Precision sample of 30 rows for Matt: phrase beside its extracted bound. Same protocol as Phase 1.
Views (SQL files in views/, each with a one-paragraph header)

These are the canned questions from the use-case list, as queries over the tables. Each is a filter, never a ranking:

not_costed.sql: measures with cost_status = not_costed.
withheld.sql: measures with any X cell.
no_beneficiary_count.sql.
end_date_before.sql: parameterized on a year; provisions with an end bound before it.
last_change_before.sql: parameterized on a year.
objective_internal.sql: Finance's internal-to-the-tax-system measures.
overlapping_programs.sql.
shared_provisions.sql: provisions cited by more than one measure.
not_in_consolidation.sql: measures citing repealed provisions.
provision_footprint.sql: for a given citation_path, every measure citing it and every measure sharing a section with it.
Acceptance tests
Every indicators column has a definitions entry; doc generated from code and tested current.
Hand recomputation fixtures: cost_change for three named measures from the published tables (Matt supplies the three from the report pages, computes them in a spreadsheet, and the test asserts equality).
Reorganization deferral: cost_status = no_cost_table, beneficiaries null, provisions_resolved = 4. Finance published no cost table for this measure at all, which is what the fifth cost_status value exists to say; this test asked for not_costed before that value existed.
No indicator is non-null where any of its inputs is null.
Temporal scope: every phrase is a verbatim substring of its provision's text_en; every row has a model, prompt hash and run date in meta.
Views run without error and return the row counts recorded in a fixture for this edition.
Precision sample for temporal scope recorded by hand.
Explicitly out of Phase 2
Any qualitative flag ("objective no longer applies", "beneficiary field disagrees with cost table"). Those are Phase 3 candidates and need the same model-extraction discipline plus a human decision on whether they belong in a dataset at all.
Evaluations linkage. Finance's list of published evaluations is not keyed to measures; linking by title would be judgment. Catalogue the list as published; do not link.
Any front end. Views are SQL; presentation comes after Phase 3 test users have asked their questions.
Any text that says what a reader should do with an indicator.
