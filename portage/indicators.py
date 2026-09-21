"""Phase 2: the indicator views and the extractions they read.

CLAUDE.md's "Phase 2: Indicators" governs, with the four amendments Matt
adopted on 2026-09-20. The written definitions came first, in
`docs/indicator-definitions.md`; this module implements them and then
regenerates that file from the view SQL plus the prose below.

Two kinds of thing live here, and the difference matters:

**Extraction tables** are stored, because they are the result of reading a
published field with a rule - splitting an objective-category cell against
Finance's vocabulary, counting statute entries in a history note, deciding
which published cost row is the measure's own figure. Each carries a `method`
column and each is catalogued against a fixture, the same discipline Phase 1
used for references.

**Indicator views** are never stored. A stored indicator is a judgment that
outlives the reasoning behind it; a view re-derives itself from the source
tables every time it is read, and its formula stays visible in the file it is
documented in.

Nothing here ranks, weights, scores or orders. No view carries an ORDER BY
that would imply importance.
"""

import csv
import json
import re

from .finance import PAGES, ROOT, SNAPSHOT, text_of, normalise_label
from .measures_build import _fold, _terms_in

from lxml import html as LH


# --------------------------------------------------------------------------
# Extraction tables
# --------------------------------------------------------------------------

SCHEMA = """
-- Finance's own grouping of objective categories, from Part 3. The two groups
-- are marked up differently in the two editions - English uses a <strong>
-- paragraph ending in a colon, French an <h5> - so each list is read from its
-- own edition's markup. Neither is derived from the other's order.
CREATE TABLE objective_category_groups (
    lang              TEXT    NOT NULL,
    group_name        TEXT    NOT NULL,   -- 'internal' | 'other'
    term_as_published TEXT    NOT NULL,
    order_index       INTEGER NOT NULL,
    heading_as_published TEXT NOT NULL,
    PRIMARY KEY (lang, term_as_published)
);

-- One row per objective category a measure carries. The published cell runs
-- several categories together with no separator ("To encourage employment To
-- support business activity"), so the cell is matched against Finance's own
-- vocabulary, longest term first. Never split on punctuation.
CREATE TABLE measure_objective_categories (
    measure_id        INTEGER NOT NULL REFERENCES measures(id),
    lang              TEXT    NOT NULL,
    term_as_published TEXT    NOT NULL,
    group_name        TEXT    NOT NULL,
    method            TEXT    NOT NULL,   -- 'vocabulary'
    PRIMARY KEY (measure_id, lang, term_as_published)
);

-- The year in the parenthetical Finance attaches to the objective field,
-- e.g. "(Budget 1998)". Pattern extraction over a short formulaic tail;
-- raw_text is kept whether or not a year was read.
CREATE TABLE measure_objective_source (
    measure_id      INTEGER NOT NULL REFERENCES measures(id),
    lang            TEXT    NOT NULL,
    raw_text        TEXT,
    year            INTEGER,
    method          TEXT    NOT NULL,     -- 'pattern' | 'none'
    PRIMARY KEY (measure_id, lang)
);

-- Statute entries in a section's Phase 0 history_note. Entries are semicolon
-- separated after the "[NOTE: ...]" prefix. The first entry is the enactment
-- that put the section there; the rest are amendments, which is why
-- amending_entries is statute_entries - 1 and both are stored.
CREATE TABLE section_amending_acts (
    section_id      INTEGER PRIMARY KEY REFERENCES sections(id),
    act             TEXT    NOT NULL,
    citation_path   TEXT    NOT NULL,
    statute_entries INTEGER NOT NULL,
    amending_entries INTEGER NOT NULL,
    first_entry     TEXT,
    method          TEXT    NOT NULL      -- 'pattern'
);

-- Which published rows are a measure's own figures, and which edition they
-- were read from. One row per measure, including measures with no cost table.
--
-- cost_basis:
--   total_row          exactly one row labelled Total (or one qualified Total
--                      where the measure publishes no unqualified one)
--   single_component   no Total row, and exactly one component row label
--   components_only    no Total row and several component labels
--   multiple_total_rows several Total rows - the measure publishes more than
--                      one cost table, and choosing between them would be
--                      judgment
--   no_cost_table      Finance published no cost table for this measure
--
-- cost_row_label is null for every basis but total_row and single_component,
-- and every cost figure derived from it is null in consequence.
CREATE TABLE measure_figure_basis (
    measure_id      INTEGER PRIMARY KEY REFERENCES measures(id),
    cost_lang       TEXT,
    cost_basis      TEXT    NOT NULL,
    cost_row_label  TEXT,
    reference_lang  TEXT,
    text_lang       TEXT    NOT NULL,
    method          TEXT    NOT NULL      -- 'row_label'
);

-- Phase 2 step 3 fills this from a batch script, never from the build.
-- It is created empty so the indicator views resolve to null until it exists.
CREATE TABLE provision_temporal_scope (
    id              INTEGER PRIMARY KEY,
    -- Where the phrase literally is. The verbatim test checks the phrase
    -- against THIS row's text_en.
    section_id      INTEGER NOT NULL REFERENCES sections(id),
    -- The provision Finance cited, which is how the bound reaches a measure.
    -- Equal to section_id under the 'cited' scope; an ancestor under
    -- 'cited_and_subtree', where a cited section's text lives in its
    -- subsections. The indicator joins on this, so the scope choice does not
    -- need a schema change.
    cited_section_id INTEGER NOT NULL REFERENCES sections(id),
    phrase          TEXT    NOT NULL,     -- verbatim substring of text_en
    bound_kind      TEXT    NOT NULL,     -- 'start' | 'end' | 'step_down'
    -- 'YYYY-MM-DD' or 'YYYY-MM'. A phrase that says "before March 2025"
    -- states a month, and writing 2025-03-01 would invent a day the Act does
    -- not give. bound_precision says which you have, so nothing has to guess
    -- whether a date is exact.
    bound_date      TEXT,
    bound_year      INTEGER,
    bound_precision TEXT,                 -- 'day' | 'month' | 'year'
    -- How the stored phrase was located in text_en. 'exact' where the model's
    -- string was already a literal substring; 'whitespace_normalized' where
    -- it matched only after folding exotic spaces. Either way the stored
    -- phrase is the source's own bytes.
    phrase_match    TEXT,
    -- Which batch produced this row. Two batches made this dataset and they
    -- ran under different output ceilings, so a single run-level field would
    -- have been a false claim about half the rows.
    batch_id        TEXT,
    -- Which version of the prompt produced this row. Round 1 ran under one
    -- prompt; the taxonomy rerun runs under another that adds the 'at' kind
    -- and the phase-down rule. Both sets live in this table, and a row that
    -- could not say which prompt wrote it would be unreadable evidence.
    prompt_sha256   TEXT,
    -- Whether the request that produced this row carried the provision's
    -- parent and children as context: 'parent+children', 'parent',
    -- 'children' or 'none'. Rows written before context existed are null.
    context_used    TEXT,
    method          TEXT    NOT NULL      -- 'extracted_llm'
);

CREATE INDEX idx_temporal_section ON provision_temporal_scope(section_id);
CREATE INDEX idx_temporal_cited ON provision_temporal_scope(cited_section_id);
CREATE INDEX idx_mobjcat_measure ON measure_objective_categories(measure_id);
"""


_OBJECTIVE_HEADING = {"en": "Objective", "fr": "Objectif"}

#: Which of Finance's two group headings a list belongs to. Matched on a
#: distinctive substring of the published heading, in each edition's own words.
_GROUP_MARKERS = {
    "en": (("internal to the tax system", "internal"), ("other objectives", "other")),
    "fr": (("inhérents au régime fiscal", "internal"), ("autres objectifs", "other")),
}


def objective_category_groups():
    """Finance's internal / other grouping of objective categories, per language.

    Part 3 lists the categories under two headings. The headings are marked up
    differently in the two editions, so each is found in its own edition rather
    than by assuming the two lists run in the same order - the same rule that
    kept the category vocabulary honest in Phase 1.

    Returns [(lang, group_name, term, order_index, heading), ...].
    """
    rows = []
    for lang, heading_text in _OBJECTIVE_HEADING.items():
        name, _url = PAGES[(lang, 3)]
        doc = LH.fromstring((SNAPSHOT / name).read_bytes())
        for h in doc.xpath("//main//h3|//main//h4"):
            if normalise_label(text_of(h)).lower() != heading_text.lower():
                continue
            group, heading, order = None, None, 0
            for sib in h.itersiblings():
                if sib.tag in ("h2", "h3", "h4"):
                    break
                if not (sib.tag == "div" and "row" in (sib.get("class") or "")):
                    continue
                for el in sib.xpath(".//p|.//h5"):
                    label = normalise_label(text_of(el))
                    if not label:
                        continue
                    is_heading = el.tag == "h5" or bool(el.xpath("./strong"))
                    if is_heading:
                        folded = _fold(label)
                        group = next(
                            (g for marker, g in _GROUP_MARKERS[lang]
                             if marker in folded), None)
                        heading = label
                        continue
                    if group is None:
                        continue
                    order += 1
                    rows.append((lang, group, label, order, heading))
            break
    return rows


_YEAR = re.compile(r"\b(1[89]\d\d|20\d\d)\b")
#: The objective field ends with a parenthetical naming the document that
#: stated the objective - "(Budget 1998)". Only a trailing parenthetical
#: counts: a bracketed aside mid-sentence is not Finance's source note.
_TRAILING_PAREN = re.compile(r"\(([^()]{1,200})\)\s*\.?\s*$")


def objective_source(text):
    """(raw_text, year, method) for one objective field.

    The year is the last one in the trailing parenthetical: "(Budget 1998)"
    gives 1998, and "(Budget 2016 and Budget 2018)" gives 2018, which is the
    document Finance names last. Nothing is read from the sentence itself - a
    year in the prose is not a statement about where the objective came from.
    """
    if not text:
        return None, None, "none"
    match = _TRAILING_PAREN.search(text.strip())
    if not match:
        return None, None, "none"
    raw = match.group(1).strip()
    years = _YEAR.findall(raw)
    if not years:
        return raw, None, "none"
    return raw, int(years[-1]), "pattern"


_NOTE_PREFIX = re.compile(r"^\[NOTE:.*?\]\s*", re.S)


def amending_entries(note):
    """(statute_entries, amending_entries, first_entry) for one history note.

    Entries are semicolon separated after the "[NOTE: ...]" prefix. The first
    is the enactment that put the section there - "R.S., 1985, c. 1
    (5th Supp.), s. 3" for a section carried over, "1998, c. 19, s. 24" for one
    added in 1998 - so the amendments are the entries after it.

    Returns (0, 0, None) for a note that yields no entry, which is what the
    unparsed catalogue is for.
    """
    body = _NOTE_PREFIX.sub("", note or "")
    parts = [p.strip() for p in body.split(";") if p.strip()]
    if not parts:
        return 0, 0, None
    return len(parts), len(parts) - 1, parts[0]


def _cost_basis(row_labels_in_order):
    """(basis, row_label) from a measure's cost row labels, in document order.

    A measure publishes zero, one or more cost tables. The figure used is
    Finance's Total row; where the measure publishes no Total, its single
    component row; where it publishes several Totals - because it has several
    cost tables - there is no figure, because picking one would be judgment
    and adding them would be arithmetic Finance did not publish.

    Qualified Totals ("Total - personal income tax") count as Totals. A measure
    that publishes exactly one of them and no unqualified Total has published
    one total and it is used; a measure that publishes several has not.
    """
    blocks = []
    for label in row_labels_in_order:
        if not blocks or blocks[-1] != label:
            blocks.append(label)
    if not blocks:
        return "no_cost_table", None

    exact = [b for b in blocks if _fold(b) == "total"]
    totals = [b for b in blocks if _fold(b).startswith("total")]

    if len(exact) == 1:
        return "total_row", exact[0]
    if len(exact) > 1:
        return "multiple_total_rows", None
    if len(totals) == 1:
        return "total_row", totals[0]
    if len(totals) > 1:
        return "multiple_total_rows", None
    if len(set(blocks)) == 1:
        return "single_component", blocks[0]
    return "components_only", None


# --------------------------------------------------------------------------
# Views
# --------------------------------------------------------------------------

#: The top-level section of a citation path, in pure SQL so that a reader with
#: nothing but sqlite3 gets the same answer the build gets. A path is cut at
#: the first of "(", '"' or "~": 110(1)(d) is section 110, and the definition
#: path 54"principal residence" is section 54.
_TOP_SECTION = """SUBSTR(%(p)s, 1, MIN(
            CASE WHEN INSTR(%(p)s,'(')>0 THEN INSTR(%(p)s,'(')-1 ELSE LENGTH(%(p)s) END,
            CASE WHEN INSTR(%(p)s,'"')>0 THEN INSTR(%(p)s,'"')-1 ELSE LENGTH(%(p)s) END,
            CASE WHEN INSTR(%(p)s,'~')>0 THEN INSTR(%(p)s,'~')-1 ELSE LENGTH(%(p)s) END))"""


VIEWS = [
(
"measure_resolved_provisions",
"""Every resolved provision a measure cites, one row per reference, with the
top-level section it sits in. This is the join the legal-footprint indicators
and four of the canned views are built on, kept in one place so that the rule
for reading a section number out of a citation path is written once. Only the
edition named in `measure_figure_basis.reference_lang` is read, so a measure
present in both languages is not counted twice.

Includes `resolved_combined_stub` references. Those cite a subsection that
Justice Laws repealed inside a node covering several - "118.6(2) and (2.1)" -
and **`citation_path` here is that node's path, not the one Finance wrote**.
The measure's footprint does include it: Finance cites it and it locates a
real row in the Act. What it cannot do is stand for the cited path, which is
why the status is separate and why the reference table keeps Finance's
wording.""",
"""
CREATE VIEW measure_resolved_provisions AS
SELECT  r.measure_id,
        r.lang,
        r.order_index,
        s.act,
        s.id            AS section_id,
        s.citation_path,
        %s              AS top_section
FROM measure_references r
JOIN measure_figure_basis b
     ON b.measure_id = r.measure_id AND b.reference_lang = r.lang
JOIN sections s ON s.id = r.section_id
WHERE r.status IN ('resolved', 'resolved_combined_stub')
""" % (_TOP_SECTION % {"p": "s.citation_path"}),
),
(
"measure_provision_overlap",
"""One row per pair of measures that cite the same resolved provision, with the
provision. A pure join: no threshold, no score, and no statement that sharing a
provision means anything. Each unordered pair appears once in each direction,
so that a query filtered to one measure sees all of its partners.""",
"""
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
GROUP BY a.measure_id, b2.measure_id, a.act, a.citation_path
""",
),
(
"indicators",
"""One row per measure - 247, matching `measures` exactly, not one row per
language. The numeric indicators are language-independent; the copied
classification labels carry `_en` / `_fr` suffixes. `join_method` is carried
through so that the 36 measures that could not be paired across the two
editions stay visible in every query made over this view.

Every column is computed here from the Phase 0 and Phase 1 tables and from the
Phase 2 extraction tables. Nothing is stored, nothing is imputed, and a null
input produces a null output rather than a zero.""",
"""
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
            AND r.status IN ('resolved', 'resolved_combined_stub')
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
JOIN base b ON b.measure_id = m.id
""",
),
]


VIEWS += [
(
"v_not_costed",
"""Measures where Finance published a cost table and no year in it carries a
number. This is a measurement result, not a publishing decision: measures with
no cost table at all are `no_cost_table` and are not here. The view says
nothing about whether a measure should be costed.""",
"""
CREATE VIEW v_not_costed AS
SELECT measure_id, name_en, name_fr, join_method, cost_figure_basis,
       cost_status, provisions_cited, provisions_resolved
FROM indicators
WHERE cost_status = 'not_costed'
""",
),
(
"v_withheld",
"""Measures with at least one cost cell published as "X", which Finance's own
legend defines as withheld for confidentiality. A withheld cell is not an
absence of data and is never a zero; the count of years affected is given so a
reader can see how much of the series is missing by Finance's choice.""",
"""
CREATE VIEW v_withheld AS
SELECT measure_id, name_en, name_fr, join_method,
       cost_withheld_years, cost_status, cost_figure_basis
FROM indicators
WHERE cost_withheld_years > 0
""",
),
(
"v_no_beneficiary_count",
"""Measures with no parsed beneficiary count, with the published sentence in
both languages. Mostly this is a statement about the prose of Finance's
"number of beneficiaries" field rather than about the measure: only 75 of the
published sentences carry a single number-and-year pair that a pattern can
read, and all 75 are in the English edition.""",
"""
CREATE VIEW v_no_beneficiary_count AS
SELECT measure_id, name_en, name_fr, join_method,
       beneficiaries_raw_en, beneficiaries_raw_fr
FROM indicators
WHERE beneficiaries_latest IS NULL
""",
),
(
"v_end_bound_by_year",
"""One row per extracted end bound on a provision a measure cites, with the
year as a column. The view is not filtered to any year: SQLite views take no
parameters, and a view named for a threshold would make the choice of
threshold look like a finding. The reader supplies it -
`WHERE end_year < 2027`. Whether a bound has passed is not computed here.

Empty until Phase 2 step 3 fills `provision_temporal_scope`.""",
"""
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
WHERE t.bound_kind = 'end'
""",
),
(
"v_last_change_by_year",
"""One row per measure with the latest year Finance lists in its implementation
and recent history field, as a column for the reader to filter on. A null year
means no history event carried a year a pattern could read, which is not the
same as no change.""",
"""
CREATE VIEW v_last_change_by_year AS
SELECT measure_id, name_en, name_fr, join_method,
       introduced_year, last_change_year, years_since_last_change,
       history_events
FROM indicators
""",
),
(
"v_objective_internal",
"""Measures every one of whose objective categories Finance's Part 3 lists
under "Objectives that are internal to the tax system". Finance's grouping,
read from each edition's own markup and shipped as a fixture. Measures carrying
both internal and other categories are excluded here and are marked
`objective_category_mixed` in `indicators`.""",
"""
CREATE VIEW v_objective_internal AS
SELECT measure_id, name_en, name_fr, join_method,
       objective_category_en, objective_category_fr,
       category_en, category_fr, cost_status
FROM indicators
WHERE objective_category_internal = 1
""",
),
(
"v_overlapping_programs",
"""Measures where Finance's "other relevant government programs" field names
something. This is Finance's statement that related spending exists and nothing
more: it is not a duplication finding, and the field text travels with the flag
so a reader can see what was actually said.""",
"""
CREATE VIEW v_overlapping_programs AS
SELECT measure_id, name_en, name_fr, join_method,
       overlapping_program_raw_en, overlapping_program_raw_fr
FROM indicators
WHERE has_overlapping_program = 1
""",
),
(
"v_shared_provisions",
"""Resolved provisions cited by more than one `measures` row, with the rows.

**The count is of rows, not of measures, and the two differ.** `measures`
holds 211 joined pairs and 36 unjoined singles, and an English single and its
French counterpart are two rows describing one measure. A path cited by both
therefore reports 2 where the honest answer is 1 - the Accelerated Investment
Incentive, rows 205 and 237, is the clearest case.

`unjoined_singles_citing` says how much of the count could be that, so the
inflation is visible in the view rather than needing to be known about.

**It is not collapsed, and the attempt is why.** Collapsing on the resolved
provision set merges "Expensing of advertising costs" with "Expensing of
employee training costs", which cite the same provision and are different
measures. Adding cost values - Phase 1's full join signature - separates
those two but then fails to pair the donation measures, whose editions parsed
88 and 48 cost rows from the same tables. Restricting to unique
one-English-one-French groups collapses nothing at all. There is no mechanical
key that pairs the singles that should pair without merging the ones that
should not, which is exactly why Phase 1 left them as singles. Encoding a
guess here would put a judgment in a view whose whole claim is that it makes
none.""",
"""
CREATE VIEW v_shared_provisions AS
SELECT p.act,
       p.citation_path,
       COUNT(DISTINCT p.measure_id)                    AS measure_rows_citing,
       SUM(CASE WHEN m.join_method IS NULL THEN 1 ELSE 0 END)
                                                       AS unjoined_singles_citing,
       GROUP_CONCAT(DISTINCT p.measure_id)             AS measure_ids
FROM measure_resolved_provisions p
JOIN measures m ON m.id = p.measure_id
GROUP BY p.act, p.citation_path
HAVING COUNT(DISTINCT p.measure_id) > 1
""",
),
(
"v_not_in_consolidation",
"""Measures citing a provision the consolidation does not contain, with the
reference as published. This is the as-of-date gap - the report states the law
as at 31 December 2025 and the consolidation is dated 18 June 2026 - and it is
not an error by Finance or by Justice Canada.""",
"""
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
WHERE r.status = 'not_in_consolidation'
""",
),
(
"v_provision_footprint",
"""For every resolved provision: the measure citing it, and the number of other
measures that cite the same provision or another provision of the same section.
One row per (provision, measure) pair, which is the longer shape and the useful
one - a reader asking about a single provision filters
`WHERE citation_path = '20(1)(ss)'` and sees each measure on its own row.""",
"""
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
GROUP BY p.act, p.citation_path, p.measure_id
""",
),
]


# --------------------------------------------------------------------------
# Build
# --------------------------------------------------------------------------

def build_indicators(conn, write_catalogue):
    """Populate the Phase 2 extraction tables and create the views.

    Returns a dict of row counts for `meta`. Every extraction here is
    catalogued against a committed fixture, so a change in Finance's wording or
    in Justice Canada's history notes fails a test instead of moving a number.
    """
    conn.executescript(SCHEMA)
    counts = {}

    # -- Finance's objective-category grouping, from Part 3 -----------------
    group_rows = objective_category_groups()
    conn.executemany(
        """INSERT INTO objective_category_groups
           (lang, group_name, term_as_published, order_index, heading_as_published)
           VALUES (?,?,?,?,?)""",
        [(lang, group, term, order, heading)
         for lang, group, term, order, heading in group_rows])
    counts["objective_category_groups"] = write_catalogue(
        "objective_category_groups.csv",
        [(lang, group, order, term, heading)
         for lang, group, term, order, heading in group_rows],
        ["lang", "group_name", "order_index", "term_as_published",
         "heading_as_published"])

    vocabulary = {}
    groups = {}
    for lang, group, term, _order, _heading in group_rows:
        vocabulary.setdefault(lang, []).append(term)
        groups[(lang, term)] = group

    # -- Objective categories per measure, split against that vocabulary ----
    cat_rows, uncatalogued = [], []
    for mid, lang, cell in _field_rows(conn, "objective_category"):
        terms = _terms_in(cell, vocabulary.get(lang, []))
        if not terms:
            uncatalogued.append((mid, lang, cell))
            continue
        for term in sorted(terms):
            cat_rows.append((mid, lang, term, groups[(lang, term)], "vocabulary"))
    conn.executemany(
        """INSERT INTO measure_objective_categories
           (measure_id, lang, term_as_published, group_name, method)
           VALUES (?,?,?,?,?)""", cat_rows)
    counts["measure_objective_categories"] = len(cat_rows)
    counts["objective_categories_unmatched"] = write_catalogue(
        "objective_categories_unmatched.csv", uncatalogued,
        ["measure_id", "lang", "field_as_published"])

    # -- The year Finance attaches to the objective -------------------------
    src_rows = []
    for mid, lang, cell in _field_rows(conn, "objective"):
        raw, year, method = objective_source(cell)
        src_rows.append((mid, lang, raw, year, method))
    conn.executemany(
        """INSERT INTO measure_objective_source
           (measure_id, lang, raw_text, year, method) VALUES (?,?,?,?,?)""",
        src_rows)
    counts["measure_objective_source"] = write_catalogue(
        "measure_objective_source.csv",
        [(mid, lang, method, year if year is not None else "", raw or "")
         for mid, lang, raw, year, method in src_rows],
        ["measure_id", "lang", "method", "year", "raw_text"])

    # -- Statute entries in the Phase 0 history notes -----------------------
    amend_rows, unparsed = [], []
    for sid, act, path, note in conn.execute(
            """SELECT id, act, citation_path, history_note FROM sections
               WHERE history_note IS NOT NULL ORDER BY act, id"""):
        statutes, amending, first = amending_entries(note)
        if statutes == 0:
            unparsed.append((act, path, " ".join((note or "").split())[:200]))
            continue
        amend_rows.append((sid, act, path, statutes, amending, first, "pattern"))
    conn.executemany(
        """INSERT INTO section_amending_acts
           (section_id, act, citation_path, statute_entries, amending_entries,
            first_entry, method) VALUES (?,?,?,?,?,?,?)""", amend_rows)
    counts["section_amending_acts"] = len(amend_rows)
    counts["amending_acts_unparsed"] = write_catalogue(
        "amending_acts_unparsed.csv", unparsed,
        ["act", "citation_path", "history_note"])

    # -- Which rows are a measure's own figures, and from which edition -----
    basis_rows, basis_catalogue = [], []
    for (mid,) in conn.execute("SELECT id FROM measures ORDER BY id"):
        text_lang = conn.execute(
            "SELECT CASE WHEN name_en IS NOT NULL THEN 'en' ELSE 'fr' END "
            "FROM measures WHERE id=?", (mid,)).fetchone()[0]
        cost_lang = _preferred_lang(conn, "measure_costs", mid)
        ref_lang = _preferred_lang(conn, "measure_references", mid)
        labels = [r[0] for r in conn.execute(
            "SELECT row_label FROM measure_costs WHERE measure_id=? AND lang=? "
            "ORDER BY order_index", (mid, cost_lang))] if cost_lang else []
        basis, label = _cost_basis(labels)
        basis_rows.append((mid, cost_lang, basis, label, ref_lang, text_lang,
                           "row_label"))
        basis_catalogue.append(
            (mid, basis, cost_lang or "", label or "", ref_lang or "",
             len(set(labels))))
    conn.executemany(
        """INSERT INTO measure_figure_basis
           (measure_id, cost_lang, cost_basis, cost_row_label, reference_lang,
            text_lang, method) VALUES (?,?,?,?,?,?,?)""", basis_rows)
    counts["measure_figure_basis"] = write_catalogue(
        "measure_cost_basis.csv", basis_catalogue,
        ["measure_id", "cost_basis", "cost_edition", "cost_row_label",
         "reference_edition", "distinct_row_labels"])

    # -- Where the two editions disagree about a measure's references -------
    diffs = [tuple(r) for r in conn.execute(
        """SELECT measure_id,
                  SUM(lang='en') AS en_rows,
                  SUM(lang='fr') AS fr_rows,
                  (SELECT GROUP_CONCAT(citation_path, '; ') FROM
                     (SELECT citation_path FROM measure_references x
                       WHERE x.measure_id=r.measure_id AND x.lang='en'
                         AND x.status='resolved' ORDER BY citation_path)),
                  (SELECT GROUP_CONCAT(citation_path, '; ') FROM
                     (SELECT citation_path FROM measure_references x
                       WHERE x.measure_id=r.measure_id AND x.lang='fr'
                         AND x.status='resolved' ORDER BY citation_path))
             FROM measure_references r
            GROUP BY measure_id
           HAVING COUNT(DISTINCT lang) = 2
              AND (en_rows <> fr_rows
                   OR IFNULL((SELECT GROUP_CONCAT(citation_path, '; ') FROM
                        (SELECT citation_path FROM measure_references x
                          WHERE x.measure_id=r.measure_id AND x.lang='en'
                            AND x.status='resolved' ORDER BY citation_path)),'')
                    <> IFNULL((SELECT GROUP_CONCAT(citation_path, '; ') FROM
                        (SELECT citation_path FROM measure_references x
                          WHERE x.measure_id=r.measure_id AND x.lang='fr'
                            AND x.status='resolved' ORDER BY citation_path)),''))
            ORDER BY measure_id""")]
    counts["measure_reference_edition_diffs"] = write_catalogue(
        "measure_reference_edition_diffs.csv",
        [(m, e, f, en or "", fr or "") for m, e, f, en, fr in diffs],
        ["measure_id", "en_rows", "fr_rows", "resolved_en", "resolved_fr"])

    # -- Temporal scope, from the committed extraction ----------------------
    counts.update(load_temporal_scope(conn, ROOT / "data"))

    # -- The views ----------------------------------------------------------
    for _name, _prose, sql in VIEWS:
        conn.execute(sql)
    counts["views"] = len(VIEWS)
    return counts


def load_temporal_scope(conn, data_dir):
    """Load data/provision_temporal_scope.csv, if the batch script has run.

    The API is never called from the build. The build reads what the batch
    script committed, and re-checks the verbatim rule on the way in: a row
    whose phrase is not a substring of its provision's text_en is dropped
    here, not stored and then asserted about. The committed CSV is evidence,
    not authority.
    """
    path = data_dir / "provision_temporal_scope.csv"
    run_path = data_dir / "temporal_scope_run.json"
    if not path.exists():
        return {"provision_temporal_scope": 0, "temporal_scope_dropped": 0}

    texts = dict(conn.execute(
        "SELECT id, text_en FROM sections WHERE text_en IS NOT NULL"))
    kept, dropped = 0, 0
    with open(path, encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            sid = int(row["section_id"])
            if row["phrase"] not in (texts.get(sid) or ""):
                dropped += 1
                continue
            conn.execute(
                """INSERT INTO provision_temporal_scope
                   (section_id, cited_section_id, phrase, bound_kind,
                    bound_date, bound_year, bound_precision, phrase_match,
                    batch_id, prompt_sha256, context_used, method)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,'extracted_llm')""",
                (sid, int(row["cited_section_id"]), row["phrase"],
                 row["bound_kind"], row["bound_date"] or None,
                 int(row["bound_year"]) if row["bound_year"] else None,
                 row.get("bound_precision") or None,
                 row.get("phrase_match") or None,
                 row.get("batch_id") or None,
                 row.get("prompt_sha256") or None,
                 row.get("context_used") or None))
            kept += 1

    if run_path.exists():
        run = json.loads(run_path.read_text(encoding="utf-8"))
        batches = run.get("batches") or []
        rows_meta = [
            ("temporal_scope_model", str(run.get("model"))),
            ("temporal_scope_effort", str(run.get("effort"))),
            ("temporal_scope_prompt_sha256", str(run.get("prompt_sha256"))),
            ("temporal_scope_run_date", str(run.get("run_date"))),
            ("temporal_scope_scope", str(run.get("scope"))),
            # How the last run chose its provisions. The scope alone cannot
            # tell a 27-provision repair from a 814-provision sweep.
            ("temporal_scope_selection",
             str((run.get("selection") or {}).get("how", "unrecorded"))),
            ("temporal_scope_scope_filter",
             str((run.get("selection") or {}).get("scope_filter") or "none")),
            ("temporal_scope_method", "extracted_llm"),
            # Every batch that produced a row, and the ceiling each ran under.
            ("temporal_scope_batch_ids",
             "; ".join(str(b.get("batch_id")) for b in batches)),
            ("temporal_scope_batch_count", str(len(batches))),
            ("temporal_scope_prompt_sha256_in_rows",
             "; ".join(run.get("prompt_sha256_in_rows") or [])),
            ("temporal_scope_batch_max_tokens",
             "; ".join("%s=%s" % (b.get("batch_id"), b.get("max_tokens"))
                       for b in batches)),
        ]
        conn.executemany(
            "INSERT OR REPLACE INTO meta (key, value) VALUES (?,?)", rows_meta)
    return {"provision_temporal_scope": kept, "temporal_scope_dropped": dropped}


def _field_rows(conn, field):
    """(measure_id, lang, value) for one bilingual measures column pair."""
    rows = []
    for lang in ("en", "fr"):
        for mid, value in conn.execute(
                "SELECT id, %s_%s FROM measures ORDER BY id" % (field, lang)):
            if value is not None:
                rows.append((mid, lang, value))
    return rows


def _preferred_lang(conn, table, measure_id):
    """Which edition's rows to read for a measure: English where it has any.

    The two editions publish the same numbers - the cost signatures match
    exactly for all 172 measures that carry both - so this changes no figure.
    It decides only which rows are counted, so that a measure present in both
    languages is not counted twice. Measures that exist only in French read
    from French.
    """
    for lang in ("en", "fr"):
        n = conn.execute(
            "SELECT COUNT(*) FROM %s WHERE measure_id=? AND lang=?" % table,
            (measure_id, lang)).fetchone()[0]
        if n:
            return lang
    return None


# --------------------------------------------------------------------------
# Column definitions
# --------------------------------------------------------------------------

#: (meaning, "null when") for every column of `indicators`. CLAUDE.md requires
#: a derivation entry per column; the formula is the view SQL, and this is the
#: meaning and the null rule beside it. A test asserts that the set of keys
#: here and the set of columns in the built view are the same, in both
#: directions - a column with no entry fails the build, and so does an entry
#: for a column that no longer exists.
COLUMN_NOTES = {
"measure_id": ("Key into `measures`.", "never"),
"join_method": (
    "How the two editions were paired in Phase 1 - `content`, "
    "`content_categorical`, or null.",
    "the measure is a single, present in one edition only"),
"name_en": ("The measure name as published in the English edition.",
            "the English edition has no record for this measure"),
"name_fr": ("The measure name as published in the French edition.",
            "the French edition has no record for this measure"),

"cost_figure_basis": (
    "Which published row is taken as the measure's cost figure - `total_row`, "
    "`single_component`, `components_only`, `multiple_total_rows` or "
    "`no_cost_table`. From `measure_figure_basis`.", "never"),
"cost_figure_row_label": (
    "The published label of that row, verbatim.",
    "the basis is `components_only`, `multiple_total_rows` or `no_cost_table` "
    "- there is no single published row to name"),
"cost_edition": (
    "Which edition's cost rows were read. English wherever the measure has "
    "them; the two editions' cost signatures match exactly, so this changes "
    "no figure, only which rows are counted.",
    "the measure has no cost rows in either edition"),
"cost_latest_estimate": (
    "Value in millions of dollars of the most recent year on the figure row "
    "whose `value_kind` is `estimate`. Projections are excluded.",
    "no year on the figure row is an estimate, or there is no figure row"),
"cost_latest_estimate_year": ("That year.", "as `cost_latest_estimate`"),
"cost_latest_estimate_raw": (
    "The published cell text behind that figure, carried through so Finance's "
    "own notation travels with the number.", "as `cost_latest_estimate`"),
"cost_latest_projection": (
    "Value of the most recent year on the figure row whose `value_kind` is "
    "`projection`. Finance marks projections in the column header - `(P)` in "
    "English, `(proj.)` in French - so this is published, not inferred.",
    "no year on the figure row is a projection, or there is no figure row"),
"cost_latest_projection_year": ("That year.", "as `cost_latest_projection`"),
"cost_latest_projection_raw": ("The published cell text.",
                               "as `cost_latest_projection`"),
"cost_first_estimate": (
    "Value of the earliest year on the figure row whose `value_kind` is "
    "`estimate`, within the report's window of 2020 to 2027.",
    "as `cost_latest_estimate`"),
"cost_first_estimate_year": ("That year.", "as `cost_first_estimate`"),
"cost_first_estimate_raw": ("The published cell text.",
                            "as `cost_first_estimate`"),
"cost_change_abs": (
    "`cost_latest_estimate` minus `cost_first_estimate`, in millions of "
    "dollars. Not adjusted for inflation and not annualised.",
    "either input is null, or the two years are the same year"),
"cost_change_pct": (
    "`cost_change_abs` divided by `cost_first_estimate`, as a ratio rather "
    "than a percentage - 0.5 means half as much again.",
    "either input is null, the years are equal, or `cost_first_estimate` is 0"),
"cost_status": (
    "One of `costed` (a numeric cell in every published year), "
    "`partially_costed` (in some), `not_costed` (in none), `no_cost_table` "
    "(Finance published no cost table at all) or `withheld` (at least one "
    "cell is `X`). Read across every cost row of the measure, not only the "
    "figure row, so a caption row carrying no numbers does not make a costed "
    "measure look partial. Derived from `value_kind` alone, never from the "
    "numbers. `withheld` takes precedence.", "never"),
"cost_withheld_years": (
    "Count of distinct years in which at least one cell is published as `X`, "
    "which Finance's legend defines as withheld for confidentiality. A "
    "withheld cell is not an absence of data and is never a zero.",
    "never; 0 where none"),

"beneficiaries_latest": (
    "The count from `measure_beneficiary_counts`, most recent year first, "
    "only where `method = 'pattern'`.",
    "the published sentence carried no single number-and-year pair a pattern "
    "could read - 172 of 247 measures"),
"beneficiaries_latest_year": ("That year.", "as `beneficiaries_latest`"),
"beneficiaries_raw_en": (
    "Finance's number-of-beneficiaries field as published in English, whether "
    "or not a count was parsed from it.",
    "the English edition has no record for this measure, or left the field "
    "empty"),
"beneficiaries_raw_fr": ("The same field as published in French.",
                         "as `beneficiaries_raw_en`, for French"),
"cost_per_beneficiary": (
    "`cost_latest_estimate` converted to dollars and divided by "
    "`beneficiaries_latest`. Dollars per beneficiary, not millions.",
    "either input is null, the two years differ, or the count is 0"),
"cost_per_beneficiary_note": (
    "`years_differ` where that is why the ratio is null.",
    "the ratio was computed, or an input was missing for some other reason"),

"introduced_year": (
    "The earliest year Finance lists in the implementation and recent history "
    "field. This is the earliest year **in that field**, which is not "
    "necessarily the year the measure was enacted.",
    "no history row carries a year a pattern could read"),
"last_change_year": ("The latest such year.", "as `introduced_year`"),
"years_since_last_change": (
    "`report_year` (2026) minus `last_change_year`.",
    "`last_change_year` is null"),
"history_events": ("Count of history rows Finance lists for the measure.",
                   "never; 0 where none"),

"objective_source_year": (
    "The year in the trailing parenthetical Finance attaches to the objective "
    "field - `(Budget 1998)` gives 1998. Where the parenthetical names "
    "several documents the last year is taken. Nothing is read from the "
    "sentence itself.",
    "the objective has no trailing parenthetical, or none with a year in it"),
"objective_source_raw": (
    "That parenthetical as published, without its brackets.",
    "the objective has no trailing parenthetical"),
"objective_source_method": ("`pattern` where a year was read, else `none`.",
                            "never"),

"category_en": ("Finance's category field, verbatim - structural, "
                "non-structural, or refundable credit.",
                "Finance left the field empty, or the edition has no record"),
"category_fr": ("The same field in French.", "as `category_en`"),
"objective_category_en": ("Finance's objective category field, verbatim. A "
                          "measure may carry several, run together in one "
                          "cell.", "as `category_en`"),
"objective_category_fr": ("The same field in French.", "as `category_en`"),
"subject_en": ("Finance's subject field, verbatim.", "as `category_en`"),
"subject_fr": ("The same field in French.", "as `category_en`"),
"ccofog_code_en": ("Finance's CCOFOG 2014 code, verbatim.", "as `category_en`"),
"ccofog_code_fr": ("The same field in French.", "as `category_en`"),
"type_of_tax_en": ("Finance's tax field, verbatim.", "as `category_en`"),
"type_of_tax_fr": ("The same field in French.", "as `category_en`"),
"type_of_measure_en": ("Finance's type-of-measure field, verbatim.",
                       "as `category_en`"),
"type_of_measure_fr": ("The same field in French.", "as `category_en`"),
"objective_category_internal": (
    "1 where every objective category the measure carries is one Finance's "
    "Part 3 lists under \"Objectives that are internal to the tax system\", "
    "else 0. Finance's own grouping, read from each edition's own markup and "
    "shipped as a fixture.",
    "no category in the measure's cell matched Finance's published "
    "vocabulary - 9 measures, catalogued in "
    "`data/objective_categories_unmatched.csv`"),
"objective_category_mixed": (
    "1 where the measure carries both internal and other categories, so that "
    "an `objective_category_internal` of 0 can be told apart from a measure "
    "with no internal category at all.",
    "as `objective_category_internal`"),
"has_overlapping_program": (
    "1 where Finance's \"other relevant government programs\" field names "
    "something, 0 where it says n/a. Finance's statement that related "
    "spending exists, and nothing more - not a duplication finding.",
    "the field is empty in both editions"),
"overlapping_program_raw_en": ("That field as published in English.",
                               "as `category_en`"),
"overlapping_program_raw_fr": ("The same field in French.", "as `category_en`"),

"provisions_cited": (
    "Count of reference rows Finance lists for the measure, in the edition "
    "named by `measure_figure_basis.reference_lang`.", "never; 0 where none"),
"provisions_resolved": ("Of those, the count with `status = 'resolved'`.",
                        "never; 0"),
"provisions_not_in_consolidation": (
    "Of those, the count with `status = 'not_in_consolidation'` - the gap "
    "between the report's as-of date of 31 December 2025 and the "
    "consolidation's of 18 June 2026.", "never; 0"),
"provisions_repealed_stub": (
    "Of the measure's resolved references, the count pointing at a provision "
    "whose whole text is a repeal tombstone - \"[Repealed, 2001, c. 17, "
    "s. 3(1)]\". The citation path still resolves, but the provision is gone. "
    "Includes references with status `resolved_combined_stub`, where Justice "
    "Laws repealed several subsections in one node labelled \"(2) and "
    "(2.1)\": the cited path has no row of its own, and the node that "
    "repealed it says what happened to it. "
    "Distinct from `provisions_not_in_consolidation`, which is a path the "
    "consolidation never had: this is a path it has, pointing at nothing.",
    "never; 0"),
"sections_touched": (
    "Distinct top-level sections among the resolved paths. The section is the "
    "leading run of the citation path before the first `(`, `\"` or `~`, so "
    "`110(1)(d)` is section 110 and `54\"principal residence\"` is section 54.",
    "never; 0"),
"shared_with_measures": (
    "Count of other measures citing at least one of the same resolved "
    "citation paths. A pure join over `measure_provision_overlap`.",
    "never; 0"),
"amending_acts_count": (
    "Summed over the distinct top-level sections the measure cites: the "
    "number of statute entries in that section's Phase 0 `history_note` after "
    "the first. Entries are semicolon separated after the `[NOTE: ...]` "
    "prefix; the first entry is the enactment that put the section there, so "
    "the rest are amendments. **Double counts by design**: a section cited by "
    "several measures contributes to each, because this is a property of the "
    "measure's legal footprint and not a partition of the Act.",
    "no section the measure cites carries a history note"),
"amending_acts_method": ("`pattern` wherever a count was produced.",
                         "`amending_acts_count` is null"),

"earliest_end_date": (
    "Earliest `end` bound extracted from the text of the provisions the "
    "measure cites. Whether that date has passed is **not** computed: there "
    "is no `is_expired` and no comparison against the build date, because "
    "\"expired\" depends on when you ask and on facts outside this dataset. "
    "**The Act keeps its historical layers, and this column shows them.** The "
    "investment tax credit measures report 1978-11-17, because "
    "127(9)\"specified percentage\" still carries the pre-1978 rate tiers as "
    "text. The value is correct under the rule - that phrase is a real end "
    "bound in a provision Finance cites - and it is not the date the measure "
    "ends. A reader wanting current bounds should filter on the year they "
    "care about rather than read the earliest.",
    "no cited provision has an extracted end bound - every row, until Phase 2 "
    "step 3 fills `provision_temporal_scope`"),
"latest_end_date": ("The latest such bound.", "as `earliest_end_date`"),
"has_step_down": (
    "1 where any cited provision has a `step_down` bound, else 0.",
    "no cited provision has any extracted temporal scope"),
}


# --------------------------------------------------------------------------
# The generated documentation
# --------------------------------------------------------------------------

#: Kept by hand, and the only part of docs/indicator-definitions.md that is.
#: The reasoning behind the definitions is not derivable from the SQL, and
#: regenerating the file must not quietly delete it.
PREAMBLE = """# Indicator definitions

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
"""


def _view_sql(conn, name):
    """The view's SQL as SQLite stored it, which is the formula of record."""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='view' AND name=?",
        (name,)).fetchone()
    return (row[0].strip() + ";") if row else ""


def _columns(conn, name):
    return [r[1] for r in conn.execute('PRAGMA table_info("%s")' % name)]


def generate_definitions(conn):
    """docs/indicator-definitions.md, from the view SQL plus the prose above."""
    out = [PREAMBLE]

    out.append("## Views\n")
    out.append("| view | rows in this build | what it returns |")
    out.append("|---|---|---|")
    for name, prose, _sql in VIEWS:
        n = conn.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0]
        first = " ".join(prose.split()).split(". ")[0].rstrip(".") + "."
        out.append("| `%s` | %d | %s |" % (name, n, first))
    out.append("")

    out.append("---\n")
    out.append("## `indicators`, column by column\n")
    out.append("The formula is the SQL below; this is the meaning and the "
               "null rule beside it.\n")
    out.append("| column | meaning | null when |")
    out.append("|---|---|---|")
    for col in _columns(conn, "indicators"):
        meaning, null_when = COLUMN_NOTES[col]
        out.append("| `%s` | %s | %s |" % (col, meaning, null_when))
    out.append("")

    for name, prose, _sql in VIEWS:
        out.append("---\n")
        out.append("## `%s`\n" % name)
        out.append(prose.strip() + "\n")
        cols = _columns(conn, name)
        out.append("**Columns:** " + ", ".join("`%s`" % c for c in cols) + "\n")
        n = conn.execute('SELECT COUNT(*) FROM "%s"' % name).fetchone()[0]
        out.append("**Rows in this build:** %d\n" % n)
        out.append("```sql")
        out.append(_view_sql(conn, name))
        out.append("```\n")

    return "\n".join(out)


def write_definitions(conn, docs_dir, views_dir):
    """Write the generated doc and the per-view SQL files. Returns the doc text."""
    text = generate_definitions(conn)
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "indicator-definitions.md").write_text(text, encoding="utf-8")

    views_dir.mkdir(parents=True, exist_ok=True)
    for name, prose, _sql in VIEWS:
        header = "\n".join("-- " + line if line else "--"
                           for line in prose.strip().splitlines())
        (views_dir / ("%s.sql" % name)).write_text(
            "-- %s\n--\n%s\n--\n-- Generated by portage/indicators.py. "
            "Do not edit.\n\n%s\n" % (name, header, _view_sql(conn, name)),
            encoding="utf-8")
    return text
