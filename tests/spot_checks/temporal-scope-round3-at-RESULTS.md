# Temporal scope - round 3 supplementary sample (`at` only): results

Checked by hand by Matt, 2026-09-21, against
`tests/spot_checks/temporal-scope-round3-at.md` (seed 20260926), ten rows
drawn from the 193 whose `bound_kind` is `at`.

**7 correct, 3 wrong.** Rows 1-5, 9 and 10 hold. Rows 6, 7 and 8 do not.

The supplementary sample did what it was drawn to do. The round 3 general
sample was 30/30 on kinds, because it mirrored the corpus and so contained
only a handful of `at`. Sampling one kind on its own found a systematic error
in it at the first attempt.

## Rows 6, 7 and 8 - reference-period designations

| row | citation | phrase | given |
|---|---|---|---|
| 6 | ITA 122.5(4.3) | the month specified in subsection (3.003) is January 2023 | `at` 2023-01 |
| 7 | ITA 122.5(4.5) | July 2030 | `at` 2030-07 |
| 8 | ITA 125.7(1)"current reference period"(c.1) | for the fourth qualifying period, June 2020 | `at` 2020-06 |

None of these is a condition on when a provision operates. Each **names a
period**: which month the GST credit treats as the specified month, which
month is the fourth qualifying period of the wage subsidy. The date is an
identifier - the same species as "the Budget Implementation Act, 2023" or
"Class 43.1", which rule 3 already excludes as labels.

**Prior recall rounds judged this class correctly empty.** Round 2's recall
sample contained several of these - `125.7(1)"prior reference period"(a)(xii)`,
`"(a)(xiii)`, `(a)(xvi)`, `"current reference period"(c.994)` - and all were
read as correctly producing nothing. So the class was understood before the
context rebuild; the rebuild started extracting it as `at`, and the general
sample was too coarse to notice.

That is worth stating plainly: **the context rebuild made this class worse.**
It was empty and correct; it is now populated and wrong. A change that fixed
two error classes introduced a third, and only a kind-specific sample found it.

## How big the class is

Measured over the corpus: **94 of the 193 `at` rows** are in ITA 122.5 or
125.7, across 69 provisions. The phrase test - text naming a specified month,
qualifying period or reference period - selects 59 of those 94, entirely
inside the same two sections. Nearly half of `at` is this one class.

Those 69 provisions also hold 42 `end` and 39 `start` rows, which a rerun
would revisit as well.

## Why it is not being rerun now

`at` contributes no value to any indicator. `earliest_end_date` and
`latest_end_date` read `bound_kind = 'end'`; `has_step_down` reads
`'step_down'`. Its only effect is that two measures whose sole temporal rows
are `at` report `has_step_down = 0` rather than null.

So the wrong rows are visible in `provision_temporal_scope` and in
`v_end_bound_by_year`'s absence, and they move no published indicator. The fix
is in the prompt as version 4 and the rerun is scheduled for the next
consolidation, when the whole corpus is rebuilt anyway. Recorded in `PLAN.md`.
