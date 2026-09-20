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
