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
