# Temporal scope - precision sample, round 3: results

Checked by hand by Matt, 2026-09-21, against
`tests/spot_checks/temporal-scope-round3.md` (seed 20260924), drawn from the
full corpus after the context rebuild, all on one prompt hash.

**Phrases: 30/30. Values: 30/30. Kinds: 30/30.**

The first sample with no kind errors. Round 1 found four, round 2 found five,
and both were the same species - conditions that are not boundaries labelled
as boundaries. Context in the request and the `at` kind between them closed
that class.

## What this does and does not establish

It does not establish an error rate, and none is reported. Thirty rows of
1,086 is a 3% read, and the honest statement is that no error was found in
thirty rows, not that the corpus is correct.

It does establish that the failure mode the first two rounds found is gone
from a sample the same size that previously caught it twice. That is a
meaningful negative: the same instrument that detected the problem no longer
detects it.

**The least-examined part of the dataset is now `at` itself.** It grew from 64
rows to 193 in the rebuild, and this sample of thirty contained only a handful
of them. A supplementary ten-row sample drawn from `at` alone is in
`temporal-scope-round3-at.md`.

## Two rows noted as taxonomy edges, not errors

Both were read as correct. They are recorded because the boundary they sit on
is one the taxonomy has not had to state, and a future round may want it
stated.

**Row 9, ITA 125.6(1)"low threshold qualifying labour expenditure"(b)~f1** -
"the number of days in the taxation year that are before 2023 during which the
taxpayer is a qualifying journalism organization", returned as `end`.

This is right on the face of it: 2023 closes the period the days are counted
in. What makes it an edge is that the low-threshold definition exists to
support a rate tier of the journalism credit, and the sibling provisions in
125.6(2) that select rates are `step_down`. So the same schedule carries both
kinds - `end` where a definition bounds a day-count, `step_down` where a
paragraph selects a rate - and whether that is a distinction worth drawing or
an inconsistency depends on what a reader wants from the column.

It sits beside the `207.01(1)"TFSA dollar limit"(d)` question already in
`data/extraction_notes.csv`: whether the last, open-ended branch of a
phase-down is `start` or `step_down`. Both are the same underlying question -
where a rate schedule's edges stop being part of the schedule.

**Row 11, ITA 125.7(1)"qualifying period"(c.97)** - "begins on August 1,
2021", returned as `start`.

Correct, and the clearest case of the class rule 4a was written for: the verb
"begins" separates a period opening from a state of affairs on a day. This is
a **period definition** - a provision whose whole job is to name the bounds of
a defined period, of which 125.7(1)"qualifying period" has dozens. They are
the one place where `start` and `end` are unambiguous, and worth knowing as a
class because they will dominate any future sample drawn from those kinds.
