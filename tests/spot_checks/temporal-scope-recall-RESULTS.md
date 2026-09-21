# Temporal scope - recall sample, round 1: results

Checked by hand by Matt, 2026-09-20, against
`tests/spot_checks/temporal-scope-recall.md` (seed 20260921).

**16 correctly empty, 4 unsure, 0 clear misses.**

No provision in the sample states a date-bounded condition that the
extraction should have returned and did not. That is the result the sample
existed to test, and it held. But the sample was not uninformative: the
reasons the 20 rows were empty split three ways, and two of those are
findings about the extraction rather than about the Act.

## 11 of 20 were repeal tombstones

Rows 1, 2, 4, 5, 11, 12, 14, 15, 17, 18 and 19. The whole of each provision is
`[Repealed, 2014, c. 39, s. 30]`, sometimes preceded by the defined term whose
slot it occupies. **These were never extractable.** The year in them cites the
repealing statute; it conditions nothing. The prompt's rule 3 - a year that
merely names a statute is not a bound - already required an empty answer, and
the model gave one every time.

Correctly empty, but they should not have been asked. Measured across the
whole run: **183 of the 997 provisions sent were tombstones**, 18% of the
calls, spent to be told nothing. They are now flagged in Phase 0 as
`sections.is_repealed_stub` (760 across both instruments, catalogued in
`data/repealed_stubs.csv`) and excluded from every extraction scope. A rerun
would send 814 provisions rather than 997, at $7.89 rather than $9.64.

Two measures cite a repealed provision directly, now visible as
`indicators.provisions_repealed_stub`. That is a different statement from
`provisions_not_in_consolidation`: this is a citation path the consolidation
still has, pointing at a provision that is gone.

## 4 unsure - and all four are the same two limits

None is a miss. Each names a real temporal condition that the three-kind
taxonomy cannot express, or that is not visible in the unit that was sent.

**Row 3, ITA 110.6(19)(b)** - "a business carried on by the elector ... **on
February 22, 1994**". A point-in-time condition: not a start, not an end, not
a step-down. The date qualifies a state of affairs on one day.

**Row 13, ITA 146(1)"RRSP dollar limit"(a)** - "**for years other than 1996
and 2003**, the money purchase limit for the preceding year". An exception-year
condition. The years are excluded from a rule, not a boundary on it.

**Row 16, ITA 146.1(12)(a)(i)** - the text is "**January 1, 1972, and**". The
date is here; the condition is in the parent, which reads "before 1976 shall be
deemed to have been registered since the later of". Each unit is sent alone, so
nothing in this request said what the date was doing.

**Row 20, ITR 1100(2.011)(b)~f1** - a blended CCA factor where A is the factor
for 2026 and C the factor for 2027. Borderline: the factor does change between
two years, but this fragment defines a weighted average for a straddling
taxation year rather than a step down, and the condition that triggers it -
"if a taxation year begins in 2026 and ends in 2027" - is in the parent.
Recorded in `data/extraction_notes.csv`.

## What this does and does not license

It does not license trusting the extraction's recall generally. Twenty
provisions is twenty provisions, and 11 of them turned out to be a category
that could not have produced anything, so the sample effectively tested nine.
A second recall round drawn from the post-tombstone scope would be worth more
than this one was.

It does establish that the three-kind taxonomy and the one-unit-per-request
design have specific, countable gaps rather than diffuse unreliability. The
counts are in `docs/temporal-scope-prompt.md` under Known limits: 84
provisions match a point-in-time or exception-year pattern, of which 10
produced no bound at all, and 12 have a condition that appears to span a
parent and its child. Neither is large enough to justify a rerun on its own.
