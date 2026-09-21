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
| max_tokens | 16000 |
| transport | Batch API, one request per provision, keyed by `custom_id` |
| prompt sha256 | `cac8c075da7afb4bade5f8a660c0932dc8998789912e81a958adf8778317496d` |

The hash covers the system prompt, the user template, the response
schema, the model and the effort together. Change any one of them and
the hash changes, which is how `meta` says a run was a different run.

## What is checked rather than trusted

Every returned bound is verified in `verify()` before it is written,
and again by the build when the CSV is loaded:

- the phrase must be a verbatim substring of the provision's `text_en`.
  **The model's phrase is used only to locate it.** What is stored is
  the substring taken back out of `text_en` - the published bytes,
  never the model's retyping of them - and `phrase_match` records how
  it was found: `exact` where the model's string was already a literal
  substring, `whitespace_normalized` where it matched only after
  folding exotic space characters.

  The folding is one-for-one, so every offset is preserved and the
  slice is exact. It exists because Justice Laws sets a thin space
  (U+2009) before a currency amount and an en space (U+2002) inside a
  flattened formula: the TFSA dollar limit is published as
  `for 2009 to 2012, $5,000`, and a model that types a plain space
  there has read the provision correctly. Six real bounds were being
  thrown away for that alone. **Only whitespace is folded** - a phrase
  differing in any other character is still rejected.
- `bound_kind` must be one of `start`, `end`, `step_down`;
- `bound_value` must be `YYYY-MM-DD`, `YYYY-MM` or `YYYY`, and **the
  year in it must appear inside the phrase**. The model returns one
  string; the script splits it into the nullable `bound_date` and
  `bound_year` columns plus `bound_precision`, so no nullable union is
  ever sent over the wire.

A `day`-precision bound must also **name its day in the phrase, as
digits**. That is "never invent a day" enforced rather than merely
asked for, the same treatment the year rule gets. 325 of the 997
provisions in scope write dates as "March 31, 2025" and 75 write
"March 2025" with no day; only one or two spell a day out ("the
first day of January"), and those will be rejected into the
catalogue rather than stored. A rejection Matt can see beats an
invented day that looks exact.

`YYYY-MM` exists so that "before March 2025" is not written as
2025-03-01 or 2025-03-31. Supplying a day the Act does not state is
the same error as supplying a year it does not state, and it is the
more dangerous of the two because it looks exact. `bound_precision` -
`day`, `month` or `year` - travels with every row so a reader never
has to infer how precise a date really is. Lexicographic order still
works across all three: `2025` < `2025-03` < `2025-03-01`.

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

## The rerun filter - superseded

**This filter is history, kept for the record.** Three rounds of
widening it fixed less each time, and the last round proved why: the
filter selected exactly the right provisions and the answers did not
change, because the reason they were wrong was missing context rather
than missing selection. The next run is the whole scope under a prompt
that carries context, and there will be no fourth filter.

After round 1's hand checks the prompt gained the `at` kind and the
phase-down rule, and a subset of the corpus was rerun under it rather
than all 814. The subset is defined by four criteria - three textual,
one structural:

| criterion | shape | provisions |
|---|---|---|
| point-in-time | `on <Month> <d>, <year>`, not "on or before/after" | 74 |
| exception-year | `other than ... <year>` | 11 |
| rate | a percent sign, or a decimal coefficient such as `0.35 x A` | 123 |
| **parent-of-rate** | **no rate of its own, but a child carries one** | **27** |

233 provisions after overlaps.

**The structural criterion is there because the textual ones kept
missing the same thing.** ITA 125.6(2) is a four-branch rate schedule:
paragraph (a) covers years beginning before 2023, (b) years ending
before 2027, (c) years straddling 2026 and 2027, (d) years after 2026,
and each points at a formula fragment. The rate is in the fragment and
**the dates are in the paragraph**. Every textual pattern keys on the
rate, so all of them select the fragment and none select the
paragraph - and the paragraph is where the wrong labels were.

That was discovered twice before it was named. The first filter looked
only for a percent sign and missed the decimal coefficient that states
the journalism credit's rates. The second found the fragment and left
its parent behind, so the measure stayed in `v_end_bound_by_year` at
2027 after a rerun that was supposed to remove it. A filter built from
where the rate is will keep missing where the date is, which is what
the structural criterion exists to stop.

It is also limit B below, in the one form that can be detected
mechanically: a condition spanning a parent and its child, where the
child is what gives the parent away.

**No further widening without a hand check first.** Each round so far
has been justified by a sample someone read. A filter widened on
reasoning alone is a guess about what is wrong, and the last two
guesses were both incomplete.

## Known limits

Both were found by hand, in recall sample round 1. Neither is a bug:
each is a thing the design cannot express, counted so the size is
known before anyone decides whether to widen it.

**A. Conditions outside the three-kind taxonomy.** `start`, `end` and
`step_down` cannot express a point-in-time condition - "a business
carried on by the elector ... on February 22, 1994" - or an
exception-year condition - "for years other than 1996 and 2003". The
date qualifies a state of affairs on one day, or excludes years from a
rule, rather than bounding when the provision operates.

| pattern | provisions in scope | of those, produced no bound |
|---|---|---|
| `on <Month> <d>, <year>` (not "on or before/after") | 74 | 8 |
| `other than ... <year>` | 11 | 2 |
| either | 84 | 10 |

A fourth kind would add rows against up to 84 provisions, but only 10
of them are silent today - the rest already carry some other bound.

**B. Conditions that span a parent and its child.** Each unit is sent
alone, so a date in a child whose governing verb is in the parent has
no context. ITA 146.1(12)(a)(i) is the whole of "January 1, 1972,
and"; the parent supplies "before 1976 shall be deemed to have been
registered since the later of".

Counted mechanically as: a provision in scope whose own text names a
year, which produced no bound, and whose parent's text carries a
temporal verb (before, after, beginning, ending, commencing, since,
until, throughout). **12 provisions.**

Sending a parent's text as context would change every request and so
the prompt hash, making it a different run of the whole corpus rather
than a patch. At 12 provisions that is not obviously worth it, which
is the point of counting first.

**This was tested, and selection turned out not to be a substitute for
context.** The parent-of-rate criterion was added precisely to catch
the paragraphs of ITA 125.6(2), and it did: all 27 provisions were
rerun under the revised prompt. They came back 23 `start`, 17 `end`,
3 `at` and **zero `step_down`**. Nothing moved.

The reason is visible in the request. The whole of 125.6(2)(b) is
"if the year begins after 2022 and ends before 2027, an amount
determined by the formula" - there is no rate in it. Rule 4b asks for
every dated component of a rate phase-down to be `step_down`, and the
model cannot tell that this is one, because the rate is in a child
that the request does not contain.

So the filter now selects the right provisions and the answer is
still wrong, which is the cleanest possible demonstration that this
is limit B and not a scope problem. No further widening will fix it;
only context in the request will, and that is a full rerun.

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

Return only the JSON object the schema describes. No explanation.
```

## User message

One per provision. Nothing else is sent - no measure name, no Finance
field, no neighbouring provision, and no instruction that varies by
provision.

```text
Instrument: {instrument}
Citation path: {citation_path}
{parent}
Provision text - THE ONLY TEXT YOU MAY QUOTE FROM:
<provision>
{text}
</provision>
{children}
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
              "step_down",
              "at"
            ]
          },
          "bound_value": {
            "type": "string",
            "description": "The bound at the precision the phrase uses and no finer: YYYY-MM-DD for a full calendar date, YYYY-MM for a month and year with no day, YYYY for a year alone. Never supply a day or a month the phrase does not state."
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
