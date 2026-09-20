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
MAX_TOKENS = 4000
SAMPLE_SIZE = 30
RECALL_SAMPLE_SIZE = 20
SAMPLE_SEED = 20260920
RECALL_SAMPLE_SEED = 20260921

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

Rules, in order of importance:

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
4. Most provisions contain no date bound at all. Returning an empty list is
   the normal and correct answer. Do not hunt for something to return.
5. Report the bound in "bound_value": "YYYY-MM-DD" when the phrase names a
   full calendar date, "YYYY" when it names only a year. Nothing else. If the
   phrase names several bounds, return one object per bound.

Return only the JSON object the schema describes. No explanation.\
"""

USER_TEMPLATE = """\
Instrument: {instrument}
Citation path: {citation_path}

Provision text:
<provision>
{text}
</provision>\
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
                        "enum": ["start", "end", "step_down"],
                    },
                    # One field, one type. A nullable union on the wire is
                    # a needless risk against strict schema validation, and
                    # the dataset keeps date and year as separate nullable
                    # columns regardless - the split happens in split_bound().
                    "bound_value": {
                        "type": "string",
                        "description": "YYYY-MM-DD for a full date, YYYY for a year alone.",
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
         GROUP BY s.id
         ORDER BY s.act, s.id
    """,
}


def provisions(conn, scope, year_filter=True):
    """(kept, filtered_out) provisions for a scope.

    `year_filter` drops every provision whose text contains no four-digit
    year. See _YEAR_IN: such a provision cannot produce a bound that survives
    verification, so the only thing sending it can buy is an empty answer.
    The provisions dropped are counted and catalogued, never discarded
    silently - the recall sample exists because a filter that is wrong is
    invisible in the output.
    """
    rows = [dict(id=r[0], cited_id=r[1], act=r[2], citation_path=r[3], text=r[4])
            for r in conn.execute(SCOPES[scope])]
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


def build_request(prov):
    """One Batch API request. custom_id carries the provision id back."""
    return {
        "custom_id": "p%d" % prov["id"],
        "params": {
            "model": MODEL,
            "max_tokens": MAX_TOKENS,
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
                    text=prov["text"]),
            }],
        },
    }


# --------------------------------------------------------------------------
# Verification - run against every returned bound, before anything is stored
# --------------------------------------------------------------------------



def split_bound(value):
    """"2025-03-31" -> ("2025-03-31", None); "2025" -> (None, 2025)."""
    value = (value or "").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value, None
    if re.fullmatch(r"\d{4}", value):
        return None, int(value)
    return None, None


def verify(bound, text):
    """(ok, reason). The rules in the prompt, checked rather than trusted."""
    phrase = bound.get("phrase") or ""
    if not phrase.strip():
        return False, "empty phrase"
    if phrase not in text:
        return False, "phrase is not a verbatim substring of text_en"
    if bound.get("bound_kind") not in ("start", "end", "step_down"):
        return False, "bound_kind is not one of start, end, step_down"

    date, year = split_bound(bound.get("bound_value"))
    if date is None and year is None:
        return False, "bound_value is not YYYY-MM-DD or YYYY"
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

def submit_and_wait(requests, poll_seconds=30):
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


def parse_message(message):
    """The JSON object out of a response, or None if the model refused."""
    if getattr(message, "stop_reason", None) == "refusal":
        return None
    for block in message.content:
        if block.type == "text":
            return json.loads(block.text)
    return None


def write_outputs(provs, messages, failures, scope, batch_id, run_date):
    """The committed data, the rejects catalogue, the run record, the sample."""
    by_id = {p["id"]: p for p in provs}
    rows, rejects = [], []

    for custom_id, message in sorted(messages.items()):
        pid = int(custom_id[1:])
        prov = by_id[pid]
        parsed = parse_message(message)
        if parsed is None:
            rejects.append((prov["act"], prov["citation_path"], "",
                            "", "", "model returned no parseable object"))
            continue
        for bound in parsed.get("bounds", []):
            ok, reason = verify(bound, prov["text"])
            date, year = split_bound(bound.get("bound_value"))
            if ok:
                rows.append((pid, prov["cited_id"], prov["act"],
                             prov["citation_path"], bound["phrase"],
                             bound["bound_kind"], date or "", year or ""))
            else:
                rejects.append((prov["act"], prov["citation_path"],
                                bound.get("phrase", ""),
                                bound.get("bound_kind", ""),
                                bound.get("bound_value", ""), reason))

    for custom_id, kind in failures:
        pid = int(custom_id[1:])
        prov = by_id[pid]
        rejects.append((prov["act"], prov["citation_path"], "", "", "",
                        "batch request %s" % kind))

    rows.sort(key=lambda r: (r[2], r[3], r[4]))
    _write_csv(DATA / "provision_temporal_scope.csv", rows,
               ["section_id", "cited_section_id", "act", "citation_path",
                "phrase", "bound_kind", "bound_date", "bound_year"])
    _write_csv(DATA / "temporal_scope_rejects.csv", sorted(rejects),
               ["act", "citation_path", "phrase", "bound_kind", "bound_value",
                "reason"])

    run = {
        "model": MODEL,
        "effort": EFFORT,
        "prompt_sha256": prompt_sha256(),
        "run_date": run_date,
        "scope": scope,
        "batch_id": batch_id,
        "provisions_sent": len(provs),
        "responses": len(messages),
        "rows_accepted": len(rows),
        "rows_rejected": len(rejects),
    }
    (DATA / "temporal_scope_run.json").write_text(
        json.dumps(run, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    _write_sample(rows)
    _write_recall_sample(provs, rows)
    return run


def _write_recall_sample(provs, rows):
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

    out = SPOT_CHECKS / "temporal-scope-recall.md"
    if out.exists():
        print("  %s exists - not regenerated" % out.name)
        return
    produced = {r[0] for r in rows}
    empty = sorted((p for p in provs if p["id"] not in produced),
                   key=lambda p: (p["act"], p["citation_path"]))
    if not empty:
        return
    sample = random.Random(RECALL_SAMPLE_SEED).sample(
        empty, min(RECALL_SAMPLE_SIZE, len(empty)))
    sample.sort(key=lambda p: (p["act"], p["citation_path"]))

    lines = [
        "# Temporal scope - recall sample, round 1",
        "",
        "Twenty provisions that **contain a four-digit year and produced no",
        "bound**, drawn with seed %d." % RECALL_SAMPLE_SEED,
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
        "Record results in `temporal-scope-recall-RESULTS.md`. Do not",
        "regenerate this file.",
        "",
    ]
    for i, prov in enumerate(sample, 1):
        years = sorted(set(_YEAR_IN.findall(prov["text"])))
        text = " ".join(prov["text"].split())
        lines += ["## %d. %s %s" % (i, prov["act"], prov["citation_path"]), "",
                  "years present: %s" % ", ".join(years), "",
                  "> %s" % (text if len(text) <= 1200 else text[:1200] + " [...]"),
                  "",
                  "- [ ] correctly empty   - [ ] a bound was missed: ______", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


def _write_csv(path, rows, header):
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def _write_sample(rows):
    """Thirty rows for Matt, seeded, and never overwritten once results exist.

    Same protocol as the Phase 1 reference samples: regenerating a sample
    would orphan the results that cite it.
    """
    import random

    out = SPOT_CHECKS / "temporal-scope.md"
    if out.exists():
        print("  %s exists - not regenerated" % out.name)
        return
    sample = sorted(random.Random(SAMPLE_SEED).sample(rows, min(SAMPLE_SIZE, len(rows))))
    lines = [
        "# Temporal scope - precision sample, round 1",
        "",
        "Thirty extracted bounds, drawn with seed %d. For each: read the" % SAMPLE_SEED,
        "provision at laws-lois.justice.gc.ca and confirm that the phrase appears",
        "as shown and that the bound is what the phrase says. A phrase that is",
        "accurate but is not really a condition on the provision's operation is a",
        "failure, and is the kind this sample exists to find.",
        "",
        "Record results in `temporal-scope-RESULTS.md`. Do not regenerate this file.",
        "",
    ]
    for i, (_sid, _cid, act, path, phrase, kind, date, year) in enumerate(sample, 1):
        lines += ["## %d. %s %s" % (i, act, path), "",
                  "> %s" % phrase, "",
                  "- bound_kind: `%s`" % kind,
                  "- date: `%s`  year: `%s`" % (date or "-", year or "-"),
                  "- [ ] phrase appears verbatim   - [ ] bound is correct", ""]
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--scope", choices=sorted(SCOPES),
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
    ap.add_argument("--show-prompt", action="store_true")
    args = ap.parse_args(argv)

    if not DB_PATH.exists():
        sys.exit("portage.sqlite not found - run python -m portage.build first")
    conn = sqlite3.connect(DB_PATH)
    provs, filtered = provisions(conn, args.scope,
                                 year_filter=not args.no_year_filter)
    write_filter_catalogue(args.scope, provs, filtered)
    if args.limit:
        provs = provs[:args.limit]
    requests = [build_request(p) for p in provs]
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

    if not (os.environ.get("ANTHROPIC_API_KEY")
            or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or (pathlib.Path.home() / ".config" / "anthropic").exists()):
        sys.exit("No credentials found. Set ANTHROPIC_API_KEY or run `ant auth login`.")

    run_date = dt.datetime.now(dt.timezone.utc).date().isoformat()
    messages, failures, batch_id = submit_and_wait(requests)
    run = write_outputs(provs, messages, failures, args.scope, batch_id, run_date)
    run["filtered_no_year_token"] = len(filtered)
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
        "- the phrase must be a verbatim substring of the provision's `text_en`;",
        "- `bound_kind` must be one of `start`, `end`, `step_down`;",
        "- `bound_value` must be `YYYY-MM-DD` or `YYYY`, and **the year in it",
        "  must appear inside the phrase**. The model returns one string; the",
        "  script splits it into the nullable `bound_date` and `bound_year`",
        "  columns, so no nullable union is ever sent over the wire.",
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
