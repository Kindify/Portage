"""Phase 2 step 3: extract date-bounded conditions from provision text.

The only part of this project that calls an API, and the only extraction that
uses a model. CLAUDE.md's rules are not negotiable and are enforced here rather
than trusted:

- the phrase must be a **verbatim substring** of the provision's text_en. Every
  returned phrase is checked against the source text in this script, before
  anything is written. A phrase that is not found is written to a rejects
  catalogue and never becomes a row.
- the model never infers a date the text does not state. The prompt says so,
  and a bound whose date or year does not appear in the phrase is rejected
  here as well.
- prompt, model name and run date are recorded, and the build copies them into
  `meta`.
- **this is never called from the build.** The build reads the committed CSV.
- a precision sample of 30 rows is written for hand checking.

Run:
    python -m scripts.extract_temporal_scope --dry-run     # costs nothing
    python -m scripts.extract_temporal_scope --scope cited # calls the API

Requires ANTHROPIC_API_KEY, or an `ant auth login` profile. The --dry-run form
needs neither: it builds every request, prints the prompt and the estimate, and
exits before any client is constructed.
"""

import argparse
import csv
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "portage.sqlite"
DATA = ROOT / "data"
SPOT_CHECKS = ROOT / "tests" / "spot_checks"

MODEL = "claude-opus-5"
EFFORT = "high"
MAX_TOKENS = 16000
SAMPLE_SIZE = 30
RECALL_SAMPLE_SIZE = 20

#: One seed per round, and a round is never re-seeded. The Phase 1 reference
#: samples established this: the first sample is the evidence for the first
#: check, and regenerating it would orphan the results that cite it. A new
#: round gets a new seed and its own file.
SAMPLE_SEEDS = {1: 20260920, 2: 20260922, 3: 20260924}
RECALL_SEEDS = {1: 20260921, 2: 20260923, 3: 20260925}
SAMPLE_FILES = {1: "temporal-scope.md", 2: "temporal-scope-round2.md",
                3: "temporal-scope-round3.md"}
RECALL_FILES = {1: "temporal-scope-recall.md",
                2: "temporal-scope-recall-round2.md",
                3: "temporal-scope-recall-round3.md"}

#: Supplementary samples drawn from one bound_kind. A round's main sample is
#: drawn from the whole corpus and therefore reflects its shape: after the
#: context rebuild 'at' held 193 rows of 1,086, so thirty rows contained only
#: a handful. A kind that grew threefold in one run is the least-examined
#: thing in the dataset, and the general sample will not examine it.
KIND_SAMPLE_SIZE = 10
KIND_SAMPLE_SEEDS = {(3, "at"): 20260926}
KIND_SAMPLE_FILES = {(3, "at"): "temporal-scope-round3-at.md"}

#: Published rates, $ per million tokens, for the estimate only. The Batch API
#: is half of these. Update with the model.
RATE_INPUT, RATE_OUTPUT = 5.00, 25.00


# --------------------------------------------------------------------------
# The prompt
# --------------------------------------------------------------------------

SYSTEM_PROMPT = """\
You extract date-bounded conditions from the text of Canadian federal tax law.

You are given one provision of the Income Tax Act or the Income Tax
Regulations, in English, exactly as published. Return every condition in it
that is bounded by a date or a year.

Return three kinds of bound:

- "start": the provision, or something in it, applies only on or after a date
  or year. "acquired after 2024", "for taxation years beginning after
  March 31, 2023".
- "end": it applies only before or until a date or year. "taxation years
  before 2025", "on or before December 31, 2027", "that ends before 2030".
- "step_down": a rate, percentage or amount that changes at a date or year
  without the provision ceasing. "75% for 2024, 50% for 2025", "reduced to
  nil after 2033".
- "at": a condition that holds ON, AS OF, AT THE END OF, or INCLUDING a named
  date, rather than opening or closing a period. "a business carried on by the
  elector on February 22, 1994" - what matters is what was true that day.
  "disposed of at the end of February 22, 1994" - a valuation moment, not a
  boundary. "a taxation year that included September 30, 2006" - the year is
  identified by containing that date, not bounded by it.

Rules, in order of importance:

0. THE CONTEXT BLOCKS ARE FOR MEANING ONLY. The request may show the parent
   provision and the provision's own children. They are there so you can tell
   what the provision is doing - a paragraph reading "if the year begins after
   2022 and ends before 2027, an amount determined by the formula" is a
   component of a rate schedule, and you can only know that by seeing the rate
   in its child. **Never copy a phrase out of a context block.** Every phrase
   you return must come from inside <provision> and nowhere else; a phrase
   taken from context will be rejected.
1. THE PHRASE MUST BE COPIED EXACTLY from the provision text. Character for
   character, including punctuation, capitalisation and spacing. Do not
   paraphrase, do not normalise, do not correct anything, do not join text
   across an ellipsis. If you cannot copy a phrase exactly, do not return it.
2. NEVER INFER A DATE THE TEXT DOES NOT STATE. The date or year you report
   must itself appear inside the phrase you copied. If a provision refers to
   "the coming-into-force date" or "the following year" without naming one,
   return nothing for it. Do not resolve a cross-reference, do not use your
   knowledge of when a measure was enacted, and do not calculate a date.
3. A bound must be a real condition on the provision's operation. Ignore a
   year that merely names a statute, a form, a program, a published document
   or a defined term - "the Budget Implementation Act, 2023", "the 2021
   Census", "Class 43.1". These are labels, not conditions.
3a. A VERSION REFERENCE IS A LABEL, NOT A BOUND. "as it read on March 31,
   1977", "as it read immediately before 1996", "as that section applied to
   the 1994 taxation year", "within the meaning assigned by ... as it read
   on ..." - these identify WHICH TEXT of another provision is meant. They do
   not say when this provision operates. Return nothing for them, including
   no "at".
4. Most provisions contain no date bound at all. Returning an empty list is
   the normal and correct answer. Do not hunt for something to return.
4a. "start" and "end" are for conditions that OPEN or CLOSE a period. A date
   that fixes a state of affairs on one day is "at", not "start". The test is
   the verb, not the preposition: "begins on March 14, 2021" opens a period
   and is "start"; "has, on March 18, 2020, a business number" describes one
   day and is "at". When a date could be read either way, ask whether the
   provision runs FROM that date - if not, it is "at".
4b. EVERY DATED COMPONENT OF A RATE PHASE-DOWN IS "step_down". A rate may be
   written as a percentage ("30%"), a decimal coefficient ("0.35 x A"), a
   money amount in dollars or cents ("66 cents per kilometre", "$5,000"), or
   as "nil" - all of them are rates for this purpose. Where a provision sets
   a rate that differs by period - 30% for one span, 20% for the next, nil
   after - each dated component is
   "step_down", never "end" and never "start", including the last one and
   including the component whose rate is nil. The schedule as a whole may end
   the benefit, but a component of it is a step in that schedule and labelling
   it "end" says the provision expires on that date. Where a component names
   two dates, return one object per date, both "step_down".
5. Report the bound in "bound_value", at exactly the precision the phrase
   uses and no finer:
     - "YYYY-MM-DD" when the phrase names a full calendar date
       ("before March 31, 2025" -> "2025-03-31");
     - "YYYY-MM" when it names a month and a year but no day
       ("before March 2025" -> "2025-03");
     - "YYYY" when it names only a year ("taxation years before 2025" ->
       "2025").
   NEVER INVENT A DAY. If the phrase does not say which day, do not supply
   one - not the first of the month, not the last, not any. The same goes for
   a month the phrase does not name. Reporting a date more precise than the
   text is the same error as inventing one. If the phrase names several
   bounds, return one object per bound.

Return only the JSON object the schema describes. No explanation.\
"""

USER_TEMPLATE = """\
Instrument: {instrument}
Citation path: {citation_path}
{parent}
Provision text - THE ONLY TEXT YOU MAY QUOTE FROM:
<provision>
{text}
</provision>
{children}\
"""

PARENT_TEMPLATE = """
Context, for meaning only - the provision this one sits inside. Do not quote:
<parent path="{path}">
{text}
</parent>
"""

CHILDREN_TEMPLATE = """
Context, for meaning only - this provision's own subdivisions. Do not quote:
<children>
{blocks}</children>
"""

CHILD_BLOCK = """<child path="{path}">
{text}
</child>
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "bounds": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "phrase": {
                        "type": "string",
                        "description": "Copied exactly from the provision text.",
                    },
                    "bound_kind": {
                        "type": "string",
                        "enum": ["start", "end", "step_down", "at"],
                    },
                    # One field, one type. A nullable union on the wire is
                    # a needless risk against strict schema validation, and
                    # the dataset keeps date and year as separate nullable
                    # columns regardless - the split happens in split_bound().
                    "bound_value": {
                        "type": "string",
                        "description": (
                            "The bound at the precision the phrase uses and no "
                            "finer: YYYY-MM-DD for a full calendar date, YYYY-MM "
                            "for a month and year with no day, YYYY for a year "
                            "alone. Never supply a day or a month the phrase "
                            "does not state."
                        ),
                    },
                },
                "required": ["phrase", "bound_kind", "bound_value"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["bounds"],
    "additionalProperties": False,
}


def prompt_sha256():
    """One hash over everything that shapes the answer.

    The system prompt, the user template and the response schema together are
    the prompt of record. A change to any of them is a different run, and the
    hash in `meta` is what says so.
    """
    blob = json.dumps(
        {"system": SYSTEM_PROMPT, "user_template": USER_TEMPLATE,
         "schema": RESPONSE_SCHEMA, "model": MODEL, "effort": EFFORT},
        sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Scope
# --------------------------------------------------------------------------

#: The year token. The SAME expression filters the scope and verifies a
#: returned bound, and that is the point: a bound is only valid if its year
#: appears in the copied phrase, and the phrase is only valid if it is a
#: substring of text_en. So a provision whose text contains no year token
#: cannot yield a valid bound, and sending it would be spending money to be
#: told nothing.
#:
#: Matt proposed \b(19|20)\d{2}\b. This is that, widened to 18xx so that the
#: filter can never be narrower than the verifier - a narrower filter could
#: drop a provision that would have passed. Checked on the corpus: both
#: expressions select exactly the same 997 provisions, so the widening costs
#: nothing today and keeps the guarantee if an 18xx date ever appears.
_YEAR_IN = re.compile(r"\b(1[89]\d\d|20\d\d)\b")

#: Space characters Justice Laws uses that a model reliably types back as a
#: plain space. The thin space before a currency amount is the one that
#: matters - "for 2009 to 2012,\u2009$5,000" is how the TFSA dollar limit is
#: published, and a model returning a normal space there is reading the text
#: correctly and typing it conventionally.
_SPACE_VARIANTS = "\u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005\u2006\u2007\u2008\u2009\u200a\u202f\u205f\u3000\u2060\ufeff"
_SPACE_TABLE = {ord(ch): " " for ch in _SPACE_VARIANTS}


def locate_phrase(phrase, text):  # noqa: D401 - see below
    """(source_substring, match_kind), or (None, None).

    `match_kind` is 'exact' where the model's phrase is already a literal
    substring, and 'whitespace_normalized' where it matched only after
    folding exotic space characters. In both cases the string returned is
    **taken out of `text`**, so what gets stored is the published bytes and
    never the model's retyping of them.
    """
    """The source's own substring matching `phrase`, or None.

    A phrase is compared after folding exotic space characters to a plain
    space - a **one-for-one** substitution, so every offset is preserved and
    the slice taken back out of `text` is the published bytes, not the
    model's retyping of them.

    This does not weaken the verbatim rule; it is what makes the rule
    survivable. What gets stored is always a literal substring of `text_en`,
    and the test that asserts so is untouched. Without it, five real bounds in
    the TFSA dollar limit were being thrown away because Justice Laws sets a
    thin space before a dollar sign.

    Only whitespace is folded. A phrase that differs in any other character is
    still rejected, which is what caught the formula fragment whose words run
    together with no spaces at all.
    """
    if not phrase:
        return None, None
    if phrase in text:
        return phrase, "exact"
    index = text.translate(_SPACE_TABLE).find(phrase.translate(_SPACE_TABLE))
    if index < 0:
        return None, None
    return text[index:index + len(phrase)], "whitespace_normalized"

#: Repeal tombstones are excluded from every scope. The whole of such a
#: provision is "[Repealed, 2001, c. 17, s. 3(1)]": the year cites the
#: repealing statute and conditions nothing, so the prompt's rule 3 already
#: required an empty answer for them. 183 of the 997 provisions in the first
#: run were tombstones - 18% of the calls, spent to be told nothing. The hand
#: recall sample found 11 of its 20 rows were tombstones, which is how this
#: was noticed. Flagged in Phase 0 as sections.is_repealed_stub.
#:
#: What "the cited provisions" means. CLAUDE.md says the extraction covers the
#: provisions Finance cites; it does not say what to do when Finance cites a
#: whole section whose text lives in its subsections, which is 99 of the 271
#: cited provisions. Both readings are implemented; neither is chosen here.
SCOPES = {
    "cited": """
        SELECT DISTINCT s.id, s.id AS cited_id, s.act, s.citation_path, s.text_en
          FROM measure_references r
          JOIN sections s ON s.id = r.section_id
         WHERE r.status = 'resolved'
           AND s.text_en IS NOT NULL AND s.text_en <> ''
           AND s.is_repealed_stub = 0
         ORDER BY s.act, s.id
    """,
    "cited_and_subtree": """
        WITH RECURSIVE
          cited(id) AS (
            SELECT DISTINCT section_id FROM measure_references WHERE status='resolved'),
          empty_cited(id) AS (
            SELECT c.id FROM cited c JOIN sections s ON s.id = c.id
             WHERE s.text_en IS NULL OR s.text_en = ''),
          tree(root, id) AS (
            SELECT id, id FROM empty_cited
            UNION SELECT t.root, s.id FROM sections s JOIN tree t ON s.parent_id = t.id),
          scope(id, cited_id) AS (
            SELECT id, id FROM cited
            UNION SELECT t.id, t.root FROM tree t)
        SELECT s.id, MIN(x.cited_id), s.act, s.citation_path, s.text_en
          FROM scope x JOIN sections s ON s.id = x.id
         WHERE s.text_en IS NOT NULL AND s.text_en <> ''
           AND s.is_repealed_stub = 0
         GROUP BY s.id
         ORDER BY s.act, s.id
    """,
}


_MONTH = (r"(?:January|February|March|April|May|June|July|August|September"
          r"|October|November|December)")
#: A condition that fixes a state of affairs on a named day. "on or before"
#: and "on or after" are boundaries, not points, so they are excluded.
_POINT_IN_TIME = re.compile(r"(?<!or )\bon\s+" + _MONTH + r"\s+\d{1,2},\s*(?:1[89]|20)\d\d")
#: "for years other than 1996 and 2003" - years excluded from a rule.
_EXCEPTION_YEAR = re.compile(r"other than[^.]{0,80}?\b(?:1[89]|20)\d\d\b")
#: A rate, which is what a phase-down is made of.
_PERCENTAGE = re.compile(r"%|\bper\s?cent\b", re.I)
#: A rate written as a coefficient rather than a percentage - "0.35 x A +
#: 0.25 x B". The round-2 rerun missed ITA 125.6(2)(c)~f1, the provision the
#: phase-down rule was written for, because the journalism credit states its
#: rates this way and carries no percent sign at all.
_DECIMAL_RATE = re.compile(r"(?<![\d.])0\.\d+")


def _is_rate(text):
    """A rate, however the Act happens to spell it."""
    return bool(_PERCENTAGE.search(text) or _DECIMAL_RATE.search(text))


def carries_rate_in_a_child(text, child_texts):
    """PARENT-OF-RATE: this provision has no rate, but a child of it does.

    A structural criterion, not a textual one, and the only one in this
    filter. ITA 125.6(2) is a four-branch rate schedule - paragraph (a) covers
    years beginning before 2023, (b) years ending before 2027, (c) years
    straddling 2026 and 2027, (d) years after 2026 - and each paragraph points
    at a formula fragment. **The rate is in the fragment; the dates are in the
    paragraph.**

    Every textual pattern in this filter keys on the rate, so all of them
    select the fragment and none select the paragraph - and the paragraph is
    where the mislabelled rows are. That happened twice before it was named:
    once when the percent-sign pattern missed a decimal coefficient, and again
    when the decimal pattern found the fragment and left its parent behind.

    This is the recall sample's limit B - a condition spanning a parent and
    its child - in the one form where it can be detected mechanically.
    """
    return not _is_rate(text) and any(_is_rate(t) for t in child_texts)


def rerun_taxonomy_filter(text, child_texts=()):
    """Provisions the round-1 precision check showed the taxonomy mishandled.

    Two groups, and both come from evidence rather than from a hunch:

    - a point-in-time or exception-year condition, which had no correct kind
      before `at` existed. 84 provisions; three of the four wrong kinds in the
      precision sample were of this shape, and the recall sample found the
      same limit from the other side.
    - a rate beside a year, which is what a phase-down looks like. A rate is
      a percentage (113 provisions) **or a decimal coefficient** (10 more).
      One row in thirty labelled a phase-down component `end`, which reads as
      an expiry date.

    The decimal half was added after the fact, and the omission is the point.
    The first version of this filter looked only for a percent sign, so it
    missed ITA 125.6(2)(c)~f1 - "0.35 x A + 0.25 x B - C" - which is the exact
    provision the phase-down rule was written for. A filter built from the
    shape of the error rather than from the shape of the text will do that.

    - a provision that carries no rate itself but whose child carries one,
      which is where the dates of a phase-down live when the rates are a
      level down. 27 provisions. See carries_rate_in_a_child.

    233 of the 814 in scope, after overlaps.
    """
    return bool(_POINT_IN_TIME.search(text)
                or _EXCEPTION_YEAR.search(text)
                or _is_rate(text)
                or carries_rate_in_a_child(text, child_texts))


#: Extra predicates applied after a scope's SQL. Filtering here rather than in
#: SQL keeps the pattern that defines a rerun in one place with the reason it
#: exists.
SCOPE_FILTERS = {"rerun_taxonomy": rerun_taxonomy_filter}


def provisions(conn, scope, year_filter=True):
    """(kept, filtered_out) provisions for a scope.

    `year_filter` drops every provision whose text contains no four-digit
    year. See _YEAR_IN: such a provision cannot produce a bound that survives
    verification, so the only thing sending it can buy is an empty answer.
    The provisions dropped are counted and catalogued, never discarded
    silently - the recall sample exists because a filter that is wrong is
    invisible in the output.
    """
    sql = SCOPES.get(scope, SCOPES["cited_and_subtree"])
    rows = [dict(id=r[0], cited_id=r[1], act=r[2], citation_path=r[3], text=r[4])
            for r in conn.execute(sql)]
    # Parent and children travel with every provision: the request shows them
    # as context so a paragraph whose rate lives one level down can be read
    # for what it is. See the context rule in the system prompt.
    text_of = dict(conn.execute("SELECT id, COALESCE(text_en,'') FROM sections"))
    path_of = dict(conn.execute("SELECT id, citation_path FROM sections"))
    parent_of = dict(conn.execute("SELECT id, parent_id FROM sections"))
    children_of = {}
    for kid, par in conn.execute(
            "SELECT id, parent_id FROM sections WHERE parent_id IS NOT NULL "
            "ORDER BY order_index"):
        children_of.setdefault(par, []).append(kid)
    for r in rows:
        par = parent_of.get(r["id"])
        r["parent_path"] = path_of.get(par) if par else None
        r["parent_text"] = (text_of.get(par) or "") if par else ""
        r["children"] = [(path_of.get(k), text_of.get(k) or "")
                         for k in children_of.get(r["id"], [])
                         if (text_of.get(k) or "").strip()]
    extra = SCOPE_FILTERS.get(scope)
    if extra:
        # One criterion is structural, so the filter needs each provision's
        # children as well as its own text.
        children = {}
        for kid, parent in conn.execute(
                "SELECT id, parent_id FROM sections WHERE parent_id IS NOT NULL"):
            children.setdefault(parent, []).append(kid)
        text_of = dict(conn.execute(
            "SELECT id, COALESCE(text_en,'') FROM sections"))
        rows = [r for r in rows
                if extra(r["text"],
                         [text_of.get(k, "") for k in children.get(r["id"], [])])]
    if not year_filter:
        return rows, []
    kept = [r for r in rows if _YEAR_IN.search(r["text"])]
    dropped = [r for r in rows if not _YEAR_IN.search(r["text"])]
    return kept, dropped


def write_filter_catalogue(scope, kept, dropped):
    """data/temporal_scope_filtered.csv - counts, per instrument.

    Written by --dry-run as well as by a real run: it is a property of the
    corpus and the filter, not of anything the API said.
    """
    acts = sorted({p["act"] for p in kept} | {p["act"] for p in dropped})
    rows = [(scope, act,
             sum(1 for p in kept if p["act"] == act)
             + sum(1 for p in dropped if p["act"] == act),
             sum(1 for p in kept if p["act"] == act),
             sum(1 for p in dropped if p["act"] == act))
            for act in acts]
    rows.append((scope, "ALL", len(kept) + len(dropped), len(kept), len(dropped)))
    _write_csv(DATA / "temporal_scope_filtered.csv", rows,
               ["scope", "act", "in_scope", "sent", "filtered_no_year_token"])
    return rows


def context_blocks(prov):
    """(parent_block, children_block, context_used) for one provision."""
    parent = ""
    if prov.get("parent_text", "").strip():
        parent = PARENT_TEMPLATE.format(path=prov["parent_path"],
                                        text=prov["parent_text"])
    children = ""
    if prov.get("children"):
        blocks = "".join(CHILD_BLOCK.format(path=cp, text=ct)
                         for cp, ct in prov["children"])
        children = CHILDREN_TEMPLATE.format(blocks=blocks)
    used = ("parent+children" if parent and children else
            "parent" if parent else "children" if children else "none")
    return parent, children, used


def build_request(prov, max_tokens=MAX_TOKENS):
    """One Batch API request. custom_id carries the provision id back."""
    return {
        "custom_id": "p%d" % prov["id"],
        "params": {
            "model": MODEL,
            "max_tokens": max_tokens,
            "system": SYSTEM_PROMPT,
            "thinking": {"type": "adaptive"},
            "output_config": {
                "effort": EFFORT,
                "format": {"type": "json_schema", "schema": RESPONSE_SCHEMA},
            },
            "messages": [{
                "role": "user",
                "content": USER_TEMPLATE.format(
                    instrument=("Income Tax Act" if prov["act"] == "ITA"
                                else "Income Tax Regulations"),
                    citation_path=prov["citation_path"],
                    parent=context_blocks(prov)[0],
                    children=context_blocks(prov)[1],
                    text=prov["text"]),
            }],
        },
    }


# --------------------------------------------------------------------------
# Verification - run against every returned bound, before anything is stored
# --------------------------------------------------------------------------



def split_bound(value):
    """A returned bound_value -> (bound_date, bound_year, precision).

    Three precisions, because the text has three. A phrase that says "before
    March 2025" states a month, and writing 2025-03-01 or 2025-03-31 would be
    inventing a day the Act does not give - the same error as inventing the
    year. `bound_date` therefore holds either YYYY-MM-DD or YYYY-MM, and
    `bound_precision` says which, so that a consumer never has to guess
    whether a date is exact.

    Lexicographic order still works across all three for the earliest/latest
    indicators: "2025" < "2025-03" < "2025-03-01".
    """
    value = (value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value, None, "day"
    if re.fullmatch(r"\d{4}-\d{2}", value):
        return value, None, "month"
    if re.fullmatch(r"\d{4}", value):
        return None, int(value), "year"
    return None, None, None


def verify(bound, text):
    """(ok, reason). The rules in the prompt, checked rather than trusted."""
    phrase = bound.get("phrase") or ""
    if not phrase.strip():
        return False, "empty phrase"
    located, _kind = locate_phrase(phrase, text)
    if located is None:
        return False, "phrase is not a verbatim substring of text_en"
    phrase = located
    if bound.get("bound_kind") not in ("start", "end", "step_down", "at"):
        return False, "bound_kind is not one of start, end, step_down, at"

    date, year, precision = split_bound(bound.get("bound_value"))
    if precision is None:
        return False, "bound_value is not YYYY-MM-DD, YYYY-MM or YYYY"
    if date is not None:
        month = int(date[5:7])
        if not 1 <= month <= 12:
            return False, "bound_value names month %02d" % month
    if precision == "day":
        # "Never invent a day", checked rather than trusted - the same
        # treatment the year rule gets. A day-precision bound must name its
        # day in the phrase, as digits.
        #
        # This will reject the one or two provisions in scope that spell the
        # day out ("the first day of January 1975"). That is a visible loss in
        # the rejects catalogue, and it is the right way round: a false
        # rejection is a row Matt can see and fix, while a false accept is an
        # invented day that looks exact and is invisible.
        day = int(date[8:10])
        if not 1 <= day <= 31:
            return False, "bound_value names day %02d" % day
        if not re.search(r"(?<!\d)0?%d(?!\d)" % day, phrase):
            return False, ("day %d does not appear in the phrase - the phrase "
                           "may name only a month and year, or spell the day "
                           "out in words" % day)
    # The rule that enforces "never infer a date the text does not state":
    # the year reported must itself be in the phrase the model copied.
    reported = date[:4] if date else str(year)
    if reported not in _YEAR_IN.findall(phrase):
        return False, "the year reported does not appear in the phrase"
    return True, None


# --------------------------------------------------------------------------
# Estimate
# --------------------------------------------------------------------------

def estimate(conn, requests, provs):
    """Token and dollar estimate, counted through the API's own tokeniser
    where a client is available and by character count where it is not."""
    system_tokens = _count(conn, SYSTEM_PROMPT)
    user_tokens = sum(_count(conn, r["params"]["messages"][0]["content"])
                      for r in requests)
    n = len(requests)
    input_tokens = system_tokens * n + user_tokens
    # Output is the dominant term and the least predictable. 600 tokens per
    # call is adaptive thinking plus a short JSON object; most provisions
    # return an empty list and cost less.
    output_tokens = 600 * n
    cost = input_tokens / 1e6 * RATE_INPUT + output_tokens / 1e6 * RATE_OUTPUT
    return {
        "calls": n,
        "provisions": len(provs),
        "chars_of_provision_text": sum(len(p["text"]) for p in provs),
        "system_tokens_per_call": system_tokens,
        "input_tokens": input_tokens,
        "output_tokens_assumed": output_tokens,
        "cost_standard_usd": round(cost, 2),
        "cost_batch_usd": round(cost / 2, 2),
    }


def _count(_conn, text):
    """Tokens, approximated at 3.6 characters per token.

    Deliberately local: an estimate that itself calls the API would make
    --dry-run cost money, which is the one thing it must not do.
    """
    return int(len(text) / 3.6) + 8


# --------------------------------------------------------------------------
# Run
# --------------------------------------------------------------------------

def submit_and_wait(requests, max_tokens, poll_seconds=30):
    """Submit one batch and block until it ends. Returns {custom_id: message}.

    The Batch API is used because this is the textbook case for it - a few
    hundred independent calls, no latency requirement - and it is half the
    price. Results come back in any order, so they are keyed by custom_id and
    never by position.
    """
    import time

    import anthropic

    client = anthropic.Anthropic()
    batch = client.messages.batches.create(requests=requests)
    print("batch %s submitted, %d requests" % (batch.id, len(requests)))
    append_ledger(batch.id, max_tokens, len(requests),
                  dt.datetime.now(dt.timezone.utc).date().isoformat())

    while True:
        batch = client.messages.batches.retrieve(batch.id)
        if batch.processing_status == "ended":
            break
        print("  %s ... %s" % (batch.processing_status, batch.request_counts))
        time.sleep(poll_seconds)

    out, failures = {}, []
    for result in client.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            out[result.custom_id] = result.result.message
        else:
            failures.append((result.custom_id, result.result.type))
    return out, failures, batch.id


BATCH_LEDGER = DATA / "temporal_scope_batches.csv"
LEDGER_HEADER = ["batch_id", "max_tokens", "provisions_submitted",
                 "submitted_date", "source"]


def read_ledger():
    """{batch_id: {...}} - what each batch was actually submitted with.

    A resume cannot ask the API what ceiling a batch ran under, and guessing
    from the current default is how run.json came to claim 16000 for a batch
    submitted at 4000. The ledger is written at submit time so the answer is
    recorded rather than reconstructed; batches that predate it carry
    source='recorded_by_hand'.
    """
    if not BATCH_LEDGER.exists():
        return {}
    with open(BATCH_LEDGER, encoding="utf-8") as fh:
        return {r["batch_id"]: r for r in csv.DictReader(fh)}


def append_ledger(batch_id, max_tokens, n, date):
    ledger = read_ledger()
    ledger[batch_id] = {"batch_id": batch_id, "max_tokens": str(max_tokens),
                        "provisions_submitted": str(n),
                        "submitted_date": date, "source": "submitted"}
    _write_csv(BATCH_LEDGER,
               [tuple(ledger[k][c] for c in LEDGER_HEADER) for k in sorted(ledger)],
               LEDGER_HEADER)


def fetch_results(batch_id):
    """Results for a batch that already ran. Submits nothing, spends nothing.

    A batch that ended server-side is retrievable for days afterwards, so a
    crash in our own writing code is never a reason to pay for the work
    twice.
    """
    import anthropic

    client = anthropic.Anthropic()
    batch = client.messages.batches.retrieve(batch_id)
    print("batch %s: %s %s" % (batch.id, batch.processing_status,
                               batch.request_counts))
    if batch.processing_status != "ended":
        raise SystemExit(
            "batch %s has not ended (%s) - wait and resume again"
            % (batch_id, batch.processing_status))

    out, failures = {}, []
    for result in client.messages.batches.results(batch_id):
        if result.result.type == "succeeded":
            out[result.custom_id] = result.result.message
        else:
            failures.append((result.custom_id, result.result.type))
    return out, failures, batch.id


def parse_message(message):
    """(parsed, stop_reason, text_head, failure) for one response.

    `parsed` is the JSON object, or None. `failure` is None on success and a
    short reason otherwise. Nothing here raises: one response that came back
    truncated or refused must not cost us the other 996, which is exactly
    what happened when this function let json.loads throw.
    """
    stop = getattr(message, "stop_reason", None)
    text = ""
    for block in message.content:
        if block.type == "text":
            text = block.text or ""
            break
    head = " ".join(text.split())[:200]

    if stop == "refusal":
        details = getattr(message, "stop_details", None)
        return None, stop, head, "refusal (%s)" % getattr(details, "category", None)
    if not text:
        return None, stop, head, "no text block in the response"
    try:
        return json.loads(text), stop, head, None
    except ValueError as exc:
        reason = "truncated at max_tokens" if stop == "max_tokens" else "unparseable JSON"
        return None, stop, head, "%s: %s" % (reason, exc)


def write_outputs(provs, messages, failures, scope, batch_id, run_date,
                  merge=False, max_tokens=MAX_TOKENS, resumed=False,
                  sample_round=1, selection=None):
    """The committed data, the catalogues, the run record, the samples.

    `merge` keeps rows for provisions this run did not cover, so that an
    `--only` rerun of a handful of citations repairs those rows instead of
    replacing the whole corpus with them.
    """
    by_id = {p["id"]: p for p in provs}
    rows, rejects, broken = [], [], []
    parsed_ok = set()

    for custom_id, message in sorted(messages.items()):
        pid = int(custom_id[1:])
        prov = by_id.get(pid)
        if prov is None:
            broken.append(("?", "p%d" % pid, "", "",
                           "custom_id not in the current scope - the database "
                           "or the scope changed since the batch was submitted"))
            continue
        parsed, stop, head, failure = parse_message(message)
        if failure is not None:
            broken.append((prov["act"], prov["citation_path"],
                           str(stop), head, failure))
            continue
        parsed_ok.add(pid)
        for bound in parsed.get("bounds", []):
            ok, reason = verify(bound, prov["text"])
            date, year, precision = split_bound(bound.get("bound_value"))
            if ok:
                # The source's own bytes, not the model's retyping of them.
                phrase, match = locate_phrase(bound["phrase"], prov["text"])
                rows.append((pid, prov["cited_id"], prov["act"],
                             prov["citation_path"], phrase,
                             bound["bound_kind"], date or "", year or "",
                             precision, match, batch_id, prompt_sha256(),
                             context_blocks(prov)[2]))
            else:
                rejects.append((prov["act"], prov["citation_path"],
                                bound.get("phrase", ""),
                                bound.get("bound_kind", ""),
                                bound.get("bound_value", ""), reason))

    for custom_id, kind in failures:
        pid = int(custom_id[1:])
        prov = by_id.get(pid)
        broken.append(((prov or {}).get("act", "?"),
                       (prov or {}).get("citation_path", "p%d" % pid),
                       "batch_" + kind, "", "batch request %s" % kind))

    # Only provisions this run read successfully are replaced. A response
    # that failed must never delete rows an earlier batch produced - that is
    # how a re-verify would quietly destroy good data.
    covered = parsed_ok
    rows = _merge(DATA / "provision_temporal_scope.csv", rows, covered,
                  "section_id") if merge else rows
    touched = {by_id[i]["citation_path"] for i in parsed_ok if i in by_id}
    rejects = _merge_simple(DATA / "temporal_scope_rejects.csv", rejects,
                            touched, 1) if merge else rejects
    broken = _merge_simple(DATA / "temporal_scope_failures.csv", broken,
                           touched, 1) if merge else broken

    # A provision that failed in this run but still holds rows from another
    # batch is not an outstanding failure; it was already repaired.
    if merge:
        repaired = {(r[2], r[3]) for r in rows}
        broken = [b for b in broken if (b[0], b[1]) not in repaired]

    rows.sort(key=lambda r: (r[2], r[3], r[4]))
    _write_csv(DATA / "provision_temporal_scope.csv", rows,
               ["section_id", "cited_section_id", "act", "citation_path",
                "phrase", "bound_kind", "bound_date", "bound_year",
                "bound_precision", "phrase_match", "batch_id",
                "prompt_sha256", "context_used"])
    _write_csv(DATA / "temporal_scope_rejects.csv", sorted(rejects),
               ["act", "citation_path", "phrase", "bound_kind", "bound_value",
                "reason"])
    # Responses that produced nothing usable. Kept apart from rejects: a
    # reject is a bound the rules threw out, which is the system working; a
    # failure is a response we could not read at all, which is not.
    _write_csv(DATA / "temporal_scope_failures.csv", sorted(broken),
               ["act", "citation_path", "stop_reason", "text_head_200",
                "reason"])

    truncated = [b for b in broken if b[2] == "max_tokens"]
    prompts = sorted({r[11] for r in rows if len(r) > 11 and r[11]})
    ledger = read_ledger()
    contributing = sorted({r[10] for r in rows if r[10]})
    batches = []
    for bid in contributing:
        entry = ledger.get(bid, {})
        batches.append({
            "batch_id": bid,
            "max_tokens": (int(entry["max_tokens"])
                           if entry.get("max_tokens") else None),
            "provisions_submitted": (int(entry["provisions_submitted"])
                                     if entry.get("provisions_submitted") else None),
            "submitted_date": entry.get("submitted_date"),
            "source": entry.get("source", "unrecorded"),
            "rows_from_this_batch": sum(1 for r in rows if r[10] == bid),
        })
    run = {
        "model": MODEL,
        "effort": EFFORT,
        # Every batch that contributed a row, each with the ceiling it was
        # actually submitted under. A single max_tokens field was a false
        # provenance claim the moment two batches produced one dataset.
        "batches": batches,
        "prompt_sha256": prompt_sha256(),
        # Rows may have been produced by more than one version of the prompt.
        # A single run-level hash would claim this run's prompt for rows a
        # different one wrote, the same way one max_tokens field once claimed
        # 16000 for a batch submitted at 4000.
        "prompt_sha256_in_rows": prompts,
        "run_date": run_date,
        # What was actually asked for, not just the pool it came from. A run
        # that sent 27 named provisions and a run that sent all 814 both had
        # scope "cited_and_subtree", and recording only that made the two
        # indistinguishable in the record.
        "scope": scope,
        "selection": selection or {"how": "full_scope"},
        "batch_id_this_run": batch_id,
        "provisions_sent": len(provs),
        "responses": len(messages),
        "rows_accepted": len(rows),
        "rows_rejected": len(rejects),
        "responses_unreadable": len(broken),
        "responses_truncated_at_max_tokens": len(truncated),
        "truncated_citations": sorted("%s %s" % (b[0], b[1]) for b in truncated),
    }
    (DATA / "temporal_scope_run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_sample(rows, sample_round)
    _write_recall_sample(provs, rows, sample_round)
    return run


def year_windows(text, radius=220, cap=2000):
    """The neighbourhood of every year token, not the first N characters.

    A recall sample asks whether a bound was missed, so the checker has to see
    the years. Truncating at a fixed length answered a different question:
    round 3 handed back two provisions whose year tokens were past the cut,
    and neither could be checked at all.

    Windows around each match are merged where they overlap and joined with a
    marker, so the checker sees what surrounds every year and can tell that
    text was elided rather than absent.
    """
    flat = " ".join((text or "").split())
    spans = [(max(0, m.start() - radius), min(len(flat), m.end() + radius))
             for m in _YEAR_IN.finditer(flat)]
    if not spans:
        return flat[:cap]

    merged = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])

    parts, total = [], 0
    for i, (start, end) in enumerate(merged):
        piece = ("... " if start > 0 else "") + flat[start:end] + (" ..." if end < len(flat) else "")
        if total + len(piece) > cap and parts:
            parts.append("**[%d further year mention(s) not shown - read the "
                         "provision in full]**" % (len(merged) - i))
            break
        parts.append(piece)
        total += len(piece)
    return "\n>\n> ".join(parts)


def _write_recall_sample(provs, rows, round_number=1):
    """Twenty provisions that contain a year and produced nothing.

    The precision sample asks "is what came back right". This asks the
    question precision cannot: "is what did not come back really absent".
    Every provision here passed the year filter, so the filter is not the
    reason it is empty - either the provision genuinely has no date-bounded
    condition, or the extraction missed one. Only a person reading the text
    can tell those apart, and a miss is invisible in every automated test in
    this project.
    """
    import random

    out = SPOT_CHECKS / RECALL_FILES[round_number]
    if _sample_is_frozen(out):
        return
    seed = RECALL_SEEDS[round_number]
    produced = {r[0] for r in rows}
    empty = sorted((p for p in provs if p["id"] not in produced),
                   key=lambda p: (p["act"], p["citation_path"]))
    if not empty:
        return
    sample = random.Random(seed).sample(
        empty, min(RECALL_SAMPLE_SIZE, len(empty)))
    sample.sort(key=lambda p: (p["act"], p["citation_path"]))

    lines = [
        "# Temporal scope - recall sample, round %d" % round_number,
        "",
        "Twenty provisions that **contain a four-digit year and produced no",
        "bound**, drawn with seed %d." % seed,
        "",
        "The precision sample checks that what came back is right. This checks",
        "the other direction, which no automated test in this project can: that",
        "what did not come back is really absent. Every provision below passed",
        "the year filter, so the filter is not why it is empty.",
        "",
        "For each: read the text and decide whether it states a date-bounded",
        "condition - a start, an end, or a step-down - that the extraction",
        "should have returned. A year that merely names a statute, a form, a",
        "class or a document is **not** a bound, and an empty answer is correct",
        "for it.",
        "",
        "Record results in `%s`. Do not"
        % RECALL_FILES[round_number].replace(".md", "-RESULTS.md"),
        "regenerate this file.",
        "",
    ]
    for i, prov in enumerate(sample, 1):
        years = sorted(set(_YEAR_IN.findall(prov["text"])))
        flat = " ".join(prov["text"].split())
        lines += ["## %d. %s %s" % (i, prov["act"], prov["citation_path"]), "",
                  "years present: %s" % ", ".join(years),
                  "full length: %d characters%s"
                  % (len(flat), "" if len(flat) <= 2000 else
                     " - shown as windows around each year"),
                  "",
                  "> %s" % year_windows(prov["text"]),
                  "",
                  "- [ ] correctly empty   - [ ] a bound was missed: ______", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def _sample_is_frozen(out):
    """True where a sample has been hand-checked and must not be regenerated.

    The rule is the RESULTS file, not the sample file. A sample whose results
    a person has recorded is evidence, and regenerating it would orphan the
    results that cite it - that is the Phase 1 protocol and it stands. But a
    sample with no results beside it is a draft: a trial run's sample, or one
    drawn before a fix. Keying the guard on the sample's own existence froze
    those too, which is how a 25-provision trial nearly became the hand-check
    sample for a 997-provision run.
    """
    results = out.with_name(out.stem + "-RESULTS.md")
    if results.exists():
        print("  %s exists - %s not regenerated" % (results.name, out.name))
        return True
    if out.exists():
        print("  %s regenerated (no %s yet)" % (out.name, results.name))
    return False


def _merge(path, new_rows, covered_ids, id_field):
    """Existing rows for provisions this run did not cover, plus the new ones."""
    if not path.exists():
        return new_rows
    kept = []
    with open(path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            if int(row[0]) not in covered_ids:
                kept.append((int(row[0]), int(row[1])) + tuple(row[2:]))
                while len(kept[-1]) < 13:   # a CSV written before these columns
                    kept[-1] = kept[-1] + ("",)
    return kept + new_rows


def _merge_simple(path, new_rows, covered_paths, path_col):
    """Same, for the catalogues, which are keyed by citation path."""
    if not path.exists():
        return new_rows
    kept = []
    with open(path, encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader, None)
        for row in reader:
            if len(row) > path_col and row[path_col] not in covered_paths:
                kept.append(tuple(row))
    return kept + new_rows


def _write_kind_sample(rows, round_number, kind):
    """A supplementary sample drawn from one bound_kind only."""
    import random

    key = (round_number, kind)
    if key not in KIND_SAMPLE_FILES:
        raise SystemExit("no kind sample defined for round %d, kind %r"
                         % (round_number, kind))
    out = SPOT_CHECKS / KIND_SAMPLE_FILES[key]
    if _sample_is_frozen(out):
        return
    seed = KIND_SAMPLE_SEEDS[key]
    pool = [r for r in rows if r[5] == kind
            and len(r) > 11 and r[11] == prompt_sha256()]
    if not pool:
        print("  no %r rows on the current prompt - not written" % kind)
        return
    sample = sorted(random.Random(seed).sample(
        pool, min(KIND_SAMPLE_SIZE, len(pool))))

    lines = [
        "# Temporal scope - round %d supplementary sample: `%s` only"
        % (round_number, kind),
        "",
        "Ten bounds drawn with seed %d from the %d rows whose `bound_kind` is"
        % (seed, len(pool)),
        "`%s`. The round %d sample was drawn from the whole corpus and so"
        % (kind, round_number),
        "reflected its shape; this one deliberately does not.",
        "",
        "`%s` grew from 64 rows to 193 in the context rebuild, which makes it"
        % kind,
        "the least-examined category in the dataset and the one most likely to",
        "carry a systematic error nobody has looked for yet.",
        "",
        "For each: read the provision at laws-lois.justice.gc.ca and confirm",
        "that the phrase appears as shown, that the date is the one the phrase",
        "states, and **that the condition really holds on or as of that date**",
        "rather than opening or closing a period. A row that should have been",
        "`start`, `end` or `step_down` is the failure this sample exists to",
        "find.",
        "",
        "Record results in `%s`. Do not regenerate this file."
        % KIND_SAMPLE_FILES[key].replace(".md", "-RESULTS.md"),
        "",
    ]
    for i, row in enumerate(sample, 1):
        act, path, phrase = row[2], row[3], row[4]
        date, year, prec, ctx = row[6], row[7], row[8], row[12] if len(row) > 12 else ""
        lines += ["## %d. %s %s" % (i, act, path), "",
                  "> %s" % phrase, "",
                  "- date: `%s`  year: `%s`  precision: `%s`"
                  % (date or "-", year or "-", prec),
                  "- context sent with the request: `%s`" % (ctx or "-"),
                  "- [ ] phrase verbatim   - [ ] `%s` is the right kind, not "
                  "start/end/step_down: ______" % kind, ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")
    print("  %s written (%d of %d %r rows)"
          % (out.name, len(sample), len(pool), kind))


def _write_csv(path, rows, header):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _write_sample(rows, round_number=1):
    """Thirty rows for Matt, seeded, and never overwritten once results exist.

    Same protocol as the Phase 1 reference samples: once results have been
    recorded beside it, regenerating the sample would orphan them. Until then
    it is a draft and is rewritten on every run - see _sample_is_frozen.
    """
    import random

    out = SPOT_CHECKS / SAMPLE_FILES[round_number]
    if _sample_is_frozen(out):
        return
    seed = SAMPLE_SEEDS[round_number]
    # Round 2 reads only rows the revised prompt wrote. A sample mixing the
    # two versions would not tell us whether the revision worked.
    pool = rows if round_number == 1 else [
        r for r in rows if len(r) > 11 and r[11] == prompt_sha256()]
    if not pool:
        print("  no rows for sample round %d - not written" % round_number)
        return
    if round_number > 1 and len(pool) < len(rows):
        # Drawing 30 rows from the fraction of the corpus that happens to be
        # on the current prompt makes a sample of a migration, not of the
        # dataset. Round 2 was drawn that way deliberately, to read a rerun;
        # a later round should be drawn after the corpus is on one prompt.
        print("  NOTE: %d of %d rows are on the current prompt - sample round "
              "%d covers only those" % (len(pool), len(rows), round_number))
    sample = sorted(random.Random(seed).sample(pool, min(SAMPLE_SIZE, len(pool))))
    lines = [
        "# Temporal scope - precision sample, round %d" % round_number,
        "",
        "Thirty extracted bounds, drawn with seed %d. For each: read the" % seed,
        "provision at laws-lois.justice.gc.ca and confirm that the phrase appears",
        "as shown and that the bound is what the phrase says. A phrase that is",
        "accurate but is not really a condition on the provision's operation is a",
        "failure, and is the kind this sample exists to find.",
        "",
        "Record results in `%s`. Do not regenerate this file."
        % SAMPLE_FILES[round_number].replace(".md", "-RESULTS.md"),
        "",
    ]
    # Indexed, not unpacked: a row gains a column now and then, and a sample
    # writer that breaks on that is a sample not written.
    for i, row in enumerate(sample, 1):
        act, path, phrase, kind = row[2], row[3], row[4], row[5]
        date, year, prec, match = row[6], row[7], row[8], row[9]
        lines += ["## %d. %s %s" % (i, act, path), "",
                  "> %s" % phrase, "",
                  "- bound_kind: `%s`" % kind,
                  "- date: `%s`  year: `%s`  precision: `%s`  match: `%s`"
                  % (date or "-", year or "-", prec, match),
                  "- [ ] phrase appears verbatim   - [ ] bound is correct", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def write_samples_offline(conn, round_number, kind=None):
    """Regenerate the hand-check samples from the committed CSV. No API call.

    The samples are drawn from what was extracted, not from what the API
    would say now, so producing them needs nothing but the CSV and the
    database. Kept in the script rather than in a notebook so the seed, the
    pool and the wording travel with the extraction that produced them.
    """
    path = DATA / "provision_temporal_scope.csv"
    rows = []
    with open(path, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            rows.append((int(r["section_id"]), int(r["cited_section_id"]),
                         r["act"], r["citation_path"], r["phrase"],
                         r["bound_kind"], r["bound_date"], r["bound_year"],
                         r["bound_precision"], r["phrase_match"],
                         r["batch_id"], r["prompt_sha256"],
                         r.get("context_used", "")))
    provs, _filtered = provisions(conn, "cited_and_subtree")
    if kind:
        _write_kind_sample(rows, round_number, kind)
    else:
        _write_sample(rows, round_number)
        _write_recall_sample(provs, rows, round_number)
    return len(rows)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scope",
                    choices=sorted(set(SCOPES) | set(SCOPE_FILTERS)),
                    default="cited_and_subtree")
    ap.add_argument("--no-year-filter", action="store_true",
                    help="send provisions with no year token too; they "
                         "cannot yield a valid bound, so this only "
                         "exists to re-measure the filter")
    ap.add_argument("--dry-run", action="store_true",
                    help="build every request, print the prompt and the "
                         "estimate, call nothing, and exit")
    ap.add_argument("--limit", type=int,
                    help="send only the first N provisions, for a trial run")
    ap.add_argument("--resume", metavar="BATCH_ID",
                    help="fetch the results of a batch that already ran and "
                         "redo verification and the writes. Submits nothing.")
    ap.add_argument("--only", metavar="CITATIONS",
                    help="comma-separated citation paths to rerun, e.g. "
                         "'18(3.4),127(9)' or 'ITR 1100(1)'. Implies merge: "
                         "rows for every other provision are kept.")
    ap.add_argument("--submitted-max-tokens", type=int,
                    help="with --resume, the ceiling that batch was actually "
                         "submitted under, for a batch predating the ledger")
    ap.add_argument("--max-tokens", type=int, default=MAX_TOKENS,
                    help="output ceiling per call (default %d). A ceiling, "
                         "not a reservation - raising it costs nothing for "
                         "responses that do not need it." % MAX_TOKENS)
    ap.add_argument("--samples", type=int, metavar="ROUND",
                    choices=sorted(SAMPLE_FILES),
                    help="regenerate the hand-check samples for a round from "
                         "the committed CSV and exit. Calls nothing.")
    ap.add_argument("--sample-kind", metavar="KIND",
                    help="with --samples, write the supplementary sample for "
                         "that bound_kind instead of the round's two samples")
    ap.add_argument("--show-prompt", action="store_true")
    args = ap.parse_args(argv)

    if not DB_PATH.exists():
        sys.exit("portage.sqlite not found - run python -m portage.build first")
    conn = sqlite3.connect(DB_PATH)

    if args.samples:
        n = write_samples_offline(conn, args.samples, args.sample_kind)
        print("samples round %d written from %d rows. Nothing was called."
              % (args.samples, n))
        return 0

    provs, filtered = provisions(conn, args.scope,
                                 year_filter=not args.no_year_filter)
    write_filter_catalogue(args.scope, provs, filtered)

    if args.only:
        wanted = {w.strip() for w in args.only.split(",") if w.strip()}
        chosen = [p for p in provs
                  if p["citation_path"] in wanted
                  or "%s %s" % (p["act"], p["citation_path"]) in wanted]
        found = {p["citation_path"] for p in chosen} | {
            "%s %s" % (p["act"], p["citation_path"]) for p in chosen}
        missing = sorted(wanted - found)
        if missing:
            sys.exit("--only named provisions that are not in scope: %s"
                     % ", ".join(missing))
        provs = chosen
        print("--only: %d provision(s); rows for the rest are kept" % len(provs))
    if args.limit:
        provs = provs[:args.limit]
    requests = [build_request(p, args.max_tokens) for p in provs]
    est = estimate(conn, requests, provs)
    est["filtered_no_year_token"] = len(filtered)

    if args.show_prompt or args.dry_run:
        print("=" * 72)
        print("SYSTEM PROMPT  (sha256 of prompt+schema+model: %s)" % prompt_sha256())
        print("=" * 72)
        print(SYSTEM_PROMPT)
        print()
        print("=" * 72)
        print("USER MESSAGE - first provision of %d" % len(provs))
        print("=" * 72)
        print(requests[0]["params"]["messages"][0]["content"] if requests else "(none)")
        print()
        print("=" * 72)
        print("RESPONSE SCHEMA")
        print("=" * 72)
        print(json.dumps(RESPONSE_SCHEMA, indent=2))
        print()

    print("=" * 72)
    print("ESTIMATE  scope=%s  model=%s  effort=%s" % (args.scope, MODEL, EFFORT))
    print("=" * 72)
    for k, v in est.items():
        print("  %-26s %s" % (k, v))
    print()

    if args.dry_run:
        print("--dry-run: nothing was sent. No client was constructed.")
        return 0

    if args.resume:
        print("--resume %s: fetching an existing batch. Nothing is submitted."
              % args.resume)

    if not (os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or (pathlib.Path.home() / ".config" / "anthropic").exists()):
        sys.exit("No credentials found. Set ANTHROPIC_API_KEY or run `ant auth login`.")

    # Merge unless this run covers the whole default scope. A partial run that
    # replaced the file would delete every provision it did not cover, which
    # is exactly what a targeted rerun is: 196 provisions standing in for 814.
    merging = bool(args.only or args.resume or args.limit
                   or args.scope in SCOPE_FILTERS)
    print("write mode: %s" % ("merge - rows for provisions outside this run "
                              "are kept" if merging else
                              "REPLACE - the file is rewritten from this run alone"))

    run_date = dt.datetime.now(dt.timezone.utc).date().isoformat()
    if args.resume:
        if args.submitted_max_tokens and args.resume not in read_ledger():
            append_ledger(args.resume, args.submitted_max_tokens, 0,
                          "unknown")
        messages, failures, batch_id = fetch_results(args.resume)
    else:
        messages, failures, batch_id = submit_and_wait(requests, args.max_tokens)
    selection = {
        "how": ("only" if args.only else
                "limit" if args.limit else
                "scope_filter" if args.scope in SCOPE_FILTERS else "full_scope"),
        "base_scope": args.scope,
        "scope_filter": args.scope if args.scope in SCOPE_FILTERS else None,
        "year_token_filter": not args.no_year_filter,
        "repealed_stubs_excluded": True,
        "provisions_selected": len(provs),
        "named": sorted("%s %s" % (p["act"], p["citation_path"])
                        for p in provs) if args.only else None,
        "limit": args.limit,
        "resumed_batch": args.resume,
    }
    run = write_outputs(provs, messages, failures, args.scope, batch_id,
                        run_date, merge=merging,
                        max_tokens=args.max_tokens, resumed=bool(args.resume),
                        selection=selection)
    run["filtered_no_year_token"] = len(filtered)
    run["resumed"] = bool(args.resume)
    print(json.dumps(run, indent=2, sort_keys=True))
    print("\nWrote data/provision_temporal_scope.csv - commit it, then rebuild.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def prompt_doc():
    """docs/temporal-scope-prompt.md, generated so it cannot drift."""
    return "\n".join([
        "# The temporal-scope extraction prompt",
        "",
        "**Generated** from `scripts/extract_temporal_scope.py`. A test asserts",
        "this file matches the script. Edit the script, not this file.",
        "",
        "This is the whole of what the model is asked and the whole of what it",
        "is allowed to return. It is written down separately because it is the",
        "only place in this project where a judgment is delegated to a model,",
        "and because Matt reads it before the key is supplied.",
        "",
        "| | |",
        "|---|---|",
        "| model | `%s` |" % MODEL,
        "| effort | `%s`, adaptive thinking |" % EFFORT,
        "| max_tokens | %d |" % MAX_TOKENS,
        "| transport | Batch API, one request per provision, keyed by `custom_id` |",
        "| prompt sha256 | `%s` |" % prompt_sha256(),
        "",
        "The hash covers the system prompt, the user template, the response",
        "schema, the model and the effort together. Change any one of them and",
        "the hash changes, which is how `meta` says a run was a different run.",
        "",
        "## What is checked rather than trusted",
        "",
        "Every returned bound is verified in `verify()` before it is written,",
        "and again by the build when the CSV is loaded:",
        "",
        "- the phrase must be a verbatim substring of the provision's `text_en`.",
        "  **The model's phrase is used only to locate it.** What is stored is",
        "  the substring taken back out of `text_en` - the published bytes,",
        "  never the model's retyping of them - and `phrase_match` records how",
        "  it was found: `exact` where the model's string was already a literal",
        "  substring, `whitespace_normalized` where it matched only after",
        "  folding exotic space characters.",
        "",
        "  The folding is one-for-one, so every offset is preserved and the",
        "  slice is exact. It exists because Justice Laws sets a thin space",
        "  (U+2009) before a currency amount and an en space (U+2002) inside a",
        "  flattened formula: the TFSA dollar limit is published as",
        "  `for 2009 to 2012,\u2009$5,000`, and a model that types a plain space",
        "  there has read the provision correctly. Six real bounds were being",
        "  thrown away for that alone. **Only whitespace is folded** - a phrase",
        "  differing in any other character is still rejected.",
        "- `bound_kind` must be one of `start`, `end`, `step_down`;",
        "- `bound_value` must be `YYYY-MM-DD`, `YYYY-MM` or `YYYY`, and **the",
        "  year in it must appear inside the phrase**. The model returns one",
        "  string; the script splits it into the nullable `bound_date` and",
        "  `bound_year` columns plus `bound_precision`, so no nullable union is",
        "  ever sent over the wire.",
        "",
        "A `day`-precision bound must also **name its day in the phrase, as",
        "digits**. That is \"never invent a day\" enforced rather than merely",
        "asked for, the same treatment the year rule gets. 325 of the 997",
        "provisions in scope write dates as \"March 31, 2025\" and 75 write",
        "\"March 2025\" with no day; only one or two spell a day out (\"the",
        "first day of January\"), and those will be rejected into the",
        "catalogue rather than stored. A rejection Matt can see beats an",
        "invented day that looks exact.",
        "",
        "`YYYY-MM` exists so that \"before March 2025\" is not written as",
        "2025-03-01 or 2025-03-31. Supplying a day the Act does not state is",
        "the same error as supplying a year it does not state, and it is the",
        "more dangerous of the two because it looks exact. `bound_precision` -",
        "`day`, `month` or `year` - travels with every row so a reader never",
        "has to infer how precise a date really is. Lexicographic order still",
        "works across all three: `2025` < `2025-03` < `2025-03-01`.",
        "",
        "The last rule is the one that enforces \"never infer a date the text",
        "does not state\". A model that resolved a cross-reference, or used its",
        "own knowledge of when a measure was enacted, produces a date that is",
        "not in the phrase it copied, and the row is rejected into",
        "`data/temporal_scope_rejects.csv` rather than stored.",
        "",
        "Rejection is not silent and it is not a failure of the run: the rejects",
        "catalogue is the evidence that the rules were applied.",
        "",
        "## Scope, and the year filter",
        "",
        "The extraction covers **the provisions Finance cites, plus the",
        "subtree of a cited provision that has no text of its own** (scope",
        "`cited_and_subtree`). Finance cites 271 distinct provisions and 99 of",
        "them are whole sections whose text lives in their subsections; under",
        "the narrower reading, 129 of 247 measures would have had no text in",
        "scope at all, including the reorganization deferral.",
        "",
        "That scope is 11,847 provisions with text. It is then **filtered to",
        "provisions whose `text_en` contains a four-digit year token**,",
        "`\\b(1[89]\\d\\d|20\\d\\d)\\b`, which leaves 997.",
        "",
        "The filter is safe because of the verification rules, not in spite of",
        "them. A bound is only kept if the year it reports appears inside the",
        "copied phrase, and the phrase is only kept if it is a substring of",
        "`text_en`. So a provision whose text has no year token cannot produce",
        "a bound that survives, and sending it could only ever buy an empty",
        "answer. **The same regular expression does the filtering and the",
        "verifying** - one constant, `_YEAR_IN` - so the filter can never be",
        "narrower than the check it is justified by.",
        "",
        "Matt proposed `\\b(19|20)\\d{2}\\b`. The expression used widens that to",
        "18xx so the filter cannot be narrower than the verifier. On this",
        "corpus both select exactly the same 997 provisions, so the widening",
        "costs nothing now and keeps the guarantee if an 1800s date appears.",
        "",
        "The provisions dropped are counted per instrument in",
        "`data/temporal_scope_filtered.csv`, written by `--dry-run` too since",
        "it is a property of the corpus rather than of any answer.",
        "",
        "**A filter that is wrong is invisible in the output**, which is what",
        "the recall sample is for: twenty provisions that passed the filter and",
        "still produced nothing, for a person to read. It sits beside the",
        "thirty-row precision sample, and the two ask opposite questions - is",
        "what came back right, and is what did not come back really absent.",
        "",
        "## The rerun filter - superseded",
        "",
        "**This filter is history, kept for the record.** Three rounds of",
        "widening it fixed less each time, and the last round proved why: the",
        "filter selected exactly the right provisions and the answers did not",
        "change, because the reason they were wrong was missing context rather",
        "than missing selection. The next run is the whole scope under a prompt",
        "that carries context, and there will be no fourth filter.",
        "",
        "After round 1's hand checks the prompt gained the `at` kind and the",
        "phase-down rule, and a subset of the corpus was rerun under it rather",
        "than all 814. The subset is defined by four criteria - three textual,",
        "one structural:",
        "",
        "| criterion | shape | provisions |",
        "|---|---|---|",
        "| point-in-time | `on <Month> <d>, <year>`, not \"on or before/after\" | 74 |",
        "| exception-year | `other than ... <year>` | 11 |",
        "| rate | a percent sign, or a decimal coefficient such as `0.35 x A` | 123 |",
        "| **parent-of-rate** | **no rate of its own, but a child carries one** | **27** |",
        "",
        "233 provisions after overlaps.",
        "",
        "**The structural criterion is there because the textual ones kept",
        "missing the same thing.** ITA 125.6(2) is a four-branch rate schedule:",
        "paragraph (a) covers years beginning before 2023, (b) years ending",
        "before 2027, (c) years straddling 2026 and 2027, (d) years after 2026,",
        "and each points at a formula fragment. The rate is in the fragment and",
        "**the dates are in the paragraph**. Every textual pattern keys on the",
        "rate, so all of them select the fragment and none select the",
        "paragraph - and the paragraph is where the wrong labels were.",
        "",
        "That was discovered twice before it was named. The first filter looked",
        "only for a percent sign and missed the decimal coefficient that states",
        "the journalism credit's rates. The second found the fragment and left",
        "its parent behind, so the measure stayed in `v_end_bound_by_year` at",
        "2027 after a rerun that was supposed to remove it. A filter built from",
        "where the rate is will keep missing where the date is, which is what",
        "the structural criterion exists to stop.",
        "",
        "It is also limit B below, in the one form that can be detected",
        "mechanically: a condition spanning a parent and its child, where the",
        "child is what gives the parent away.",
        "",
        "**No further widening without a hand check first.** Each round so far",
        "has been justified by a sample someone read. A filter widened on",
        "reasoning alone is a guess about what is wrong, and the last two",
        "guesses were both incomplete.",
        "",
        "## Known limits",
        "",
        "Both were found by hand, in recall sample round 1. Neither is a bug:",
        "each is a thing the design cannot express, counted so the size is",
        "known before anyone decides whether to widen it.",
        "",
        "**A. Conditions outside the three-kind taxonomy.** `start`, `end` and",
        "`step_down` cannot express a point-in-time condition - \"a business",
        "carried on by the elector ... on February 22, 1994\" - or an",
        "exception-year condition - \"for years other than 1996 and 2003\". The",
        "date qualifies a state of affairs on one day, or excludes years from a",
        "rule, rather than bounding when the provision operates.",
        "",
        "| pattern | provisions in scope | of those, produced no bound |",
        "|---|---|---|",
        "| `on <Month> <d>, <year>` (not \"on or before/after\") | 74 | 8 |",
        "| `other than ... <year>` | 11 | 2 |",
        "| either | 84 | 10 |",
        "",
        "A fourth kind would add rows against up to 84 provisions, but only 10",
        "of them are silent today - the rest already carry some other bound.",
        "",
        "**B. Conditions that span a parent and its child.** Each unit is sent",
        "alone, so a date in a child whose governing verb is in the parent has",
        "no context. ITA 146.1(12)(a)(i) is the whole of \"January 1, 1972,",
        "and\"; the parent supplies \"before 1976 shall be deemed to have been",
        "registered since the later of\".",
        "",
        "Counted mechanically as: a provision in scope whose own text names a",
        "year, which produced no bound, and whose parent's text carries a",
        "temporal verb (before, after, beginning, ending, commencing, since,",
        "until, throughout). **12 provisions.**",
        "",
        "Sending a parent's text as context would change every request and so",
        "the prompt hash, making it a different run of the whole corpus rather",
        "than a patch. At 12 provisions that is not obviously worth it, which",
        "is the point of counting first.",
        "",
        "**This was tested, and selection turned out not to be a substitute for",
        "context.** The parent-of-rate criterion was added precisely to catch",
        "the paragraphs of ITA 125.6(2), and it did: all 27 provisions were",
        "rerun under the revised prompt. They came back 23 `start`, 17 `end`,",
        "3 `at` and **zero `step_down`**. Nothing moved.",
        "",
        "The reason is visible in the request. The whole of 125.6(2)(b) is",
        "\"if the year begins after 2022 and ends before 2027, an amount",
        "determined by the formula\" - there is no rate in it. Rule 4b asks for",
        "every dated component of a rate phase-down to be `step_down`, and the",
        "model cannot tell that this is one, because the rate is in a child",
        "that the request does not contain.",
        "",
        "So the filter now selects the right provisions and the answer is",
        "still wrong, which is the cleanest possible demonstration that this",
        "is limit B and not a scope problem. No further widening will fix it;",
        "only context in the request will, and that is a full rerun.",
        "",
        "## System prompt",
        "",
        "```text",
        SYSTEM_PROMPT,
        "```",
        "",
        "## User message",
        "",
        "One per provision. Nothing else is sent - no measure name, no Finance",
        "field, no neighbouring provision, and no instruction that varies by",
        "provision.",
        "",
        "```text",
        USER_TEMPLATE,
        "```",
        "",
        "## Response schema",
        "",
        "Enforced by `output_config.format`, so the model cannot return prose.",
        "",
        "```json",
        json.dumps(RESPONSE_SCHEMA, indent=2),
        "```",
        "",
    ])


def write_prompt_doc():
    out = ROOT / "docs" / "temporal-scope-prompt.md"
    out.write_text(prompt_doc(), encoding="utf-8")
    return out
