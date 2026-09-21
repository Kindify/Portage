# Temporal scope - precision sample, round 2: results

Checked by hand by Matt, 2026-09-21, against
`tests/spot_checks/temporal-scope-round2.md` (seed 20260922), drawn only from
rows written by the revised prompt.

**Phrases: 30/30. Values: 30/30. Kinds: 25/30.**

Phrases and values held again, as in round 1. The kinds improved on the
category round 1 found - point-in-time conditions now come back as `at` - and
the five remaining errors are two causes, one of them already named.

## Rows 9, 10, 11 - limit B, the rate is in the child

| row | citation | phrase | kind given |
|---|---|---|---|
| 9 | ITA 125.6(2)(a) | begins before 2023 | `end` |
| 10 | ITA 125.6(2.1)(c) | if the fiscal period begins before 2027 | `end` |
| 11 | ITA 125.6(2.1)(d) | if the fiscal period begins after 2026 | `start` |

These are components of the journalism credit's four-branch rate schedule.
They were reran under the revised prompt and came back unchanged, because the
whole of 125.6(2)(a) is "if the year begins before 2023 and ends after 2022,
an amount determined by the formula" - no rate is in it. The model cannot know
it is looking at a phase-down component when the rate lives in a child the
request does not contain. Selection could not fix this and did not; only
context in the request can.

## Rows 4 and 19 - version references over-extracted as `at`

| row | citation | phrase |
|---|---|---|
| 4 | ITA 88(1)(d)(i.1)(A) | as it read on March 31, 1977 |
| 19 | ITA 147(14)(c)(i) | as it read on January 1, 1972 |

Both identify **which text** of another provision is meant, not when this one
operates. The `at` kind was added for conditions holding on a named date, and
a version reference has the surface shape of one without being one. Rule 3
already excluded years that merely name a statute or a form; a version
reference is the same species and was not listed.

This is a cost of the round-1 fix: before `at` existed these produced `start`,
which was also wrong. The kind is new enough that its first output was worth
reading, which is what the sample was for.

## Rows 7, 8 and 14 - checked, and the partners are there

Matt asked whether the two-date phrases had their partner rows. **All three
do.** Each phrase produced two rows, one per date:

| citation | phrase | rows |
|---|---|---|
| ITA 125.2(2)~f1 | 0.0375, if the taxation year begins after 2032 and before 2034 | 2032, 2034 |
| ITA 125.2(2)~f1 | 0.045, if the taxation year begins after 2021 and before 2032 | 2021, 2032 |
| ITA 127(9)"specified percentage"(a.1)(iii)(A) | in 2014 and 2015, 5% | 2014, 2015 |

Rule 4b's closing sentence - one object per date - is working. The sample
showed one row of each pair because it sampled rows, not phrases, which is
worth knowing when reading any future sample: a row that looks incomplete may
have a partner the sample did not draw.
