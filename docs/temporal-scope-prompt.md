# The temporal-scope extraction prompt

**Generated** from `scripts/extract_temporal_scope.py`. A test asserts
this file matches the script. Edit the script, not this file.

This is the whole of what the model is asked and the whole of what it
is allowed to return. It is written down separately because it is the
only place in this project where a judgment is delegated to a model,
and because Matt reads it before the key is supplied.

| | |
|---|---|
| model | `claude-opus-5` |
| effort | `high`, adaptive thinking |
| max_tokens | 4000 |
| transport | Batch API, one request per provision, keyed by `custom_id` |
| prompt sha256 | `441c05df50737ac275155306acbeb38701b95382955d334eb0ee21c5c3ce0bef` |

The hash covers the system prompt, the user template, the response
schema, the model and the effort together. Change any one of them and
the hash changes, which is how `meta` says a run was a different run.

## What is checked rather than trusted

Every returned bound is verified in `verify()` before it is written,
and again by the build when the CSV is loaded:

- the phrase must be a verbatim substring of the provision's `text_en`;
- `bound_kind` must be one of `start`, `end`, `step_down`;
- `bound_value` must be `YYYY-MM-DD` or `YYYY`, and **the year in it
  must appear inside the phrase**. The model returns one string; the
  script splits it into the nullable `bound_date` and `bound_year`
  columns, so no nullable union is ever sent over the wire.

The last rule is the one that enforces "never infer a date the text
does not state". A model that resolved a cross-reference, or used its
own knowledge of when a measure was enacted, produces a date that is
not in the phrase it copied, and the row is rejected into
`data/temporal_scope_rejects.csv` rather than stored.

Rejection is not silent and it is not a failure of the run: the rejects
catalogue is the evidence that the rules were applied.

## Scope, and the year filter

The extraction covers **the provisions Finance cites, plus the
subtree of a cited provision that has no text of its own** (scope
`cited_and_subtree`). Finance cites 271 distinct provisions and 99 of
them are whole sections whose text lives in their subsections; under
the narrower reading, 129 of 247 measures would have had no text in
scope at all, including the reorganization deferral.

That scope is 11,847 provisions with text. It is then **filtered to
provisions whose `text_en` contains a four-digit year token**,
`\b(1[89]\d\d|20\d\d)\b`, which leaves 997.

The filter is safe because of the verification rules, not in spite of
them. A bound is only kept if the year it reports appears inside the
copied phrase, and the phrase is only kept if it is a substring of
`text_en`. So a provision whose text has no year token cannot produce
a bound that survives, and sending it could only ever buy an empty
answer. **The same regular expression does the filtering and the
verifying** - one constant, `_YEAR_IN` - so the filter can never be
narrower than the check it is justified by.

Matt proposed `\b(19|20)\d{2}\b`. The expression used widens that to
18xx so the filter cannot be narrower than the verifier. On this
corpus both select exactly the same 997 provisions, so the widening
costs nothing now and keeps the guarantee if an 1800s date appears.

The provisions dropped are counted per instrument in
`data/temporal_scope_filtered.csv`, written by `--dry-run` too since
it is a property of the corpus rather than of any answer.

**A filter that is wrong is invisible in the output**, which is what
the recall sample is for: twenty provisions that passed the filter and
still produced nothing, for a person to read. It sits beside the
thirty-row precision sample, and the two ask opposite questions - is
what came back right, and is what did not come back really absent.

## System prompt

```text
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

Return only the JSON object the schema describes. No explanation.
```

## User message

One per provision. Nothing else is sent - no measure name, no Finance
field, no neighbouring provision, and no instruction that varies by
provision.

```text
Instrument: {instrument}
Citation path: {citation_path}

Provision text:
<provision>
{text}
</provision>
```

## Response schema

Enforced by `output_config.format`, so the model cannot return prose.

```json
{
  "type": "object",
  "properties": {
    "bounds": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "phrase": {
            "type": "string",
            "description": "Copied exactly from the provision text."
          },
          "bound_kind": {
            "type": "string",
            "enum": [
              "start",
              "end",
              "step_down"
            ]
          },
          "bound_value": {
            "type": "string",
            "description": "YYYY-MM-DD for a full date, YYYY for a year alone."
          }
        },
        "required": [
          "phrase",
          "bound_kind",
          "bound_value"
        ],
        "additionalProperties": false
      }
    }
  },
  "required": [
    "bounds"
  ],
  "additionalProperties": false
}
```
