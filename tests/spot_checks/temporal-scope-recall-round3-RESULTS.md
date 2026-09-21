# Temporal scope - recall sample, round 3: results

Checked by hand by Matt, 2026-09-21, against
`tests/spot_checks/temporal-scope-recall-round3.md` (seed 20260925).

**17 correctly empty, 1 borderline, 2 not checkable as first rendered.**

No clear misses. No tombstones, as in round 2.

## Row 12 - borderline, a deemed acquisition date

ITA 87(2)(d.1). The provision deems property to have been acquired at a
particular time for the purposes of capital cost allowance. The date is real
and the provision turns on it, but it fixes **when something is treated as
having happened**, not when the provision operates - closer to a deeming rule
than to a condition on the rule's own application.

Left empty, and defensible. It is a third shape beside the two already parked
in `data/extraction_notes.csv`: a deemed date is neither a boundary, nor a
state of affairs on a day, nor a step in a schedule.

## Rows 2 and 18 - a defect in the sample, not the data

Neither could be checked. The recall sample showed the first 1,200 characters
of a provision, and in both cases every year token was past that cut:

| row | provision | length | years |
|---|---|---|---|
| 2 | ITA 122.5(3.001)~f1 | 1,426 chars | 2019, 2020 |
| 18 | ITR 5907(1)"taxable surplus"~f1 | 3,171 chars | 1994, 2011 |

A recall sample asks whether a bound was missed, so the checker has to see the
years. Truncating at a fixed length answered a different question, and handed
back two rows that could not be read at all.

**Fixed.** The generator now shows a window of about 220 characters around
every year token, merging overlapping windows and marking elisions, rather
than the opening of the provision. Row 2 goes from 1,426 characters to 272
with both years visible; row 18 shows windows around 1994 and 2011.

The sample was regenerated with the **same seed**, so it holds the same twenty
provisions in the same order and the seventeen results above still stand. Only
the rendering changed. Rows 2 and 18 remain to be read.

This is the second time a sample has been changed rather than the data: the
Phase 0 spot checks were once regenerated to exclude rows too short to search
for. Both times the defect was that the sample asked the checker for something
it had not shown them.
