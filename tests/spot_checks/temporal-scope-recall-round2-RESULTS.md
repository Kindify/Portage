# Temporal scope - recall sample, round 2: results

Checked by hand by Matt, 2026-09-21, against
`tests/spot_checks/temporal-scope-recall-round2.md` (seed 20260923), drawn
from the post-tombstone scope.

**16 correctly empty, 4 findings, 0 clear misses.**

The tombstone exclusion worked: no row in this sample was a repealed
provision, against 11 of 20 in round 1. The sample therefore tested twenty
provisions rather than nine.

## Rows 2 and 3 - `at` conditions the filter never selected

| row | citation | phrase in the text |
|---|---|---|
| 2 | ITA 110.6(19)(c)(ii) | disposed of at the end of February 22, 1994 |
| 3 | ITA 110.6(20)(a)(ii) | its fair market value at the end of February 22, 1994 |

Both are `at` conditions in the sense round 1 established - a valuation moment
on a named day. Both are still on the round-1 prompt, because "at the end of
<date>" matches no pattern in the rerun filter: it is not "on <Month> <d>,
<year>", it carries no rate, and its child carries none either.

So the `at` kind exists and these provisions were never given the chance to
use it. That is the third distinct way a filter has missed what it was aimed
at, and the reason the next run is a full one.

## Rows 18 and 19 - limit B again

| row | citation | text |
|---|---|---|
| 18 | ITR 5907(2.6)(a) | June 30, 1986, and |
| 19 | ITR 7305(1)(f) | the 2001 calendar year are |

Both are fragments whose governing sentence is in the parent. 5907(2.6)(a) is
one limb of a list the parent introduces; 7305(1)(f) is a year heading whose
content - the prescribed regions - is in its own children.

**One correction.** These were read as limit B, which is right, but not
because "7305's schedule is in cents". ITR 7305 is *prescribed drought
regions*: year-labelled lists of municipalities, with no rate of any kind. The
cents schedule is **ITR 7306**, the prescribed automobile amount - 66 cents
per kilometre - and it is **not in the extraction scope**, because no measure
cites it.

Measured across the whole scope: **no provision in scope contains a cents
amount at all.** Fifteen contain "nil". The revised prompt treats cents as a
rate anyway, since it costs nothing and the next edition may cite 7306, but
the rule earns its place on "nil" - as in ITA 127.4(6)(c), "nil, where the
individual dies after December 5, 1996" - not on cents.
