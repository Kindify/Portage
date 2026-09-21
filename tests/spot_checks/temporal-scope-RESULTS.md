# Temporal scope - precision sample, round 1: results

Checked by hand by Matt, 2026-09-20, against
`tests/spot_checks/temporal-scope.md` (seed 20260920). Raw record in
`temporal-scope-round1-checks.csv`.

**Phrases: 30/30. Values: 30/30. Kinds: 26/30.**

Every phrase appears in the source exactly as stored, and every date or year
is the one the phrase states. Nothing was invented and nothing was misread.
The verification rules did what they were built to do.

**The classification is where it fails, and it fails in one direction.** All
four errors are conditions that are not boundaries being labelled as
boundaries. That is a taxonomy problem, not an extraction problem: the model
was asked to choose among `start`, `end` and `step_down`, and for these
provisions none of the three is true.

## The four wrong kinds

**Rows 11, 21 and 30 - point-in-time conditions labelled `start`.**

| row | citation | phrase |
|---|---|---|
| 11 | ITA 127(9)"specified percentage"(a)(iii)(C)(III) | on February 22, 1994 |
| 21 | ITA 153(1.03)"eligible employer"(b) | has, on March 18, 2020, a business number |
| 30 | ITR 2400(8) | taxation year that included September 30, 2006 |

None of these opens a period. Each fixes a state of affairs on a named day:
what was carried on that day, what was held that day, which taxation year
contained it. Read as `start`, all three say the opposite of what the Act
says - that the rule runs from that date onwards, rather than turning on the
position on that date.

This is the same limit the recall sample found from the other side, where a
point-in-time condition produced no row at all. Here it produced a wrong one,
which is worse: an empty cell is visibly empty, and a wrong `start` is not.

**Row 7 - half of a rate phase-down labelled `end`.** ITA 125.6(2)(c)~f1,
"the number of days in the taxation year that are before 2027 during which
the taxpayer is a qualifying journalism organization". The journalism labour
credit steps its rate down and stops; 2027 is one component of that schedule,
not the end of the provision. Labelled `end` it reads as an expiry date, and
a reader filtering `v_end_bound_by_year` for measures ending before 2027
would pick it up as one.

## Two borderline, counted as correct

**Row 8**, ITA 125.7(1)"qualifying period"(c.92), "begins on March 14, 2021"
as `start`. The word "begins" is doing real work: this is a period that opens
on that date. `start` is defensible. It is listed because the surface pattern
- "on <date>" - is identical to the three errors above, so whatever rule is
written has to separate them, and the separator is the verb rather than the
preposition.

**Row 15**, ITA 127.45(1)"specified percentage"(b)(i), "on or after March 28,
2023 and before January 1, 2034, 30%" as `step_down` at 2034-01-01. The kind
is right. What is unresolved is that the phrase carries two dates and one row
reports one of them; the opening bound is not represented. Not an error in
what is stored, but a reason the phase-down rule below says every dated
component, not the last one.

## What changed because of this

Two revisions to the prompt, and a targeted rerun rather than a full one.

1. **A fourth `bound_kind`, `at`**, for a condition that holds on, as of, or
   including a named date. Rows 11, 21 and 30 are `at`.
2. **A rule that every dated component of a rate phase-down is `step_down`**,
   never `end` or `start`. Row 7 is `step_down`.

The rerun covers 196 provisions - the 84 that match a point-in-time or
exception-year pattern, plus 113 that contain both a percentage and a year
token, less one overlap - rather than all 814. Rows carry the
`prompt_sha256` that produced them, so rows from the two prompt versions stay
distinguishable in the same table.

## What this sample does not establish

It says nothing about recall; that is the other sample's job. And 30 rows out
of 971 is a 3% read: it is enough to have found a systematic taxonomy gap,
which it did, and not enough to put a rate on the remaining 941.
