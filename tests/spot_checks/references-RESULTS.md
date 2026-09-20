# Precision sample results - measure references

Hand verification of the reference grammar against the published text.

This is the second check in the project that does not compare our own output
with itself. Every automated test reads the same grammar, so if the grammar is
wrong in a way that is internally consistent, only a person reading the citation
can tell.

**This file is never overwritten by the build.**

---

## Round 1 - `references.md`

**Checked by Matt on 20 September 2026.**

| | |
|---|---|
| Pass | **28** |
| Fail | **2** |
| Total | 30 |

### The two failures

Both are the same bug, and both are French references where a paragraph label
was written without its opening bracket:

| # | Citation stored | As published | What went wrong |
|---|---|---|---|
| 13 | `ITA 6` | `... et d) à d.6)` | `d.6)` read as section **6** |
| 16 | `ITA 4` | `... c.1) [-c.4)]` | `c.4)` read as section **4** |

English writes `paragraphs 149(1)(c) and (d) to (d.6)`; French writes
`alinéas 149(1)(c) et d) à d.6)`. The normaliser at the time keyed on the word
"alinéa" and on a preceding `)`, so it rewrote a label that followed a bracket
but missed one that followed `et` or `à`. The section pattern then matched the
digits inside `d.6`.

### What the fix changed, corpus-wide

The bug was not confined to the sample. Re-running resolution across all 792
references:

- **6 false resolutions removed** - `ITA 6`, `ITA 4`, `ITA 1`, `ITA 2`,
  `ITA 27`, `ITR 2a` - none of which was ever cited.
- **22 correct paths recovered**, including `149(1)(d.6)`, `81(1)(c.4)`,
  `110(1)(d.1)`, `20(1)(bb)`, `81(1)(e)`, `81(1)(g.2)`, `149(1)(d.4)` and
  `1100(1)(c)(i)`.
- **8 more measures joined across languages** (`content` 193 -> 201), because
  the two editions had been producing different reference sets.

Two further faults surfaced while fixing it, neither in the sample:

- `alinéa 38a.2)` - French writes the section number inside the bare label,
  where English writes `paragraph 38(a.2)`. This produced `38a` and `2`.
- `section 2 and paragraph 3(a) of Schedules V and VI` - a provision named
  *before* its Schedule qualifier was resolving as ITR section 2.

The normaliser was rewritten to work by **bracket matching** rather than by
recognising the word in front of the label: a `)` with no unclosed `(` to its
left cannot be closing anything, so the token before it is a bare label. That
rule covers the variants that had not been thought of.

### Tests added

- Both failing strings as regression fixtures.
- The normaliser's contract over every French reference in the corpus: after
  normalisation, **no unmatched `)` may remain**. This is what caught `38a.2)`
  after the first fix was already in.
- A corpus-level check that no path resolves from French that never resolves
  from English.

---

## Round 2 - `references-2.md`

**Checked by Matt on 20 September 2026.**

| | |
|---|---|
| Pass | **30** |
| Fail | **0** |
| Total | 30 |

**No false resolutions.** The bracket-matching normaliser holds across a fresh
sample drawn after the fix.

Two observations from the check, both acted on:

### A definition reference was citing its host as well

Rows 6 and 9 both showed `248(1)"eligible relocation"` alongside a bare
`248(1)`, from `section 62 and the definition "eligible relocation" in
subsection 248(1)`. Finance cited the definition; the subsection is where it
lives, not a second citation. Row 19's French equivalent, `paragraphe 248(1),
définition « ... »`, did the same.

The bare host row is now suppressed wherever a definition path is produced from
the same segment. **18 reference rows removed**, 792 to 774. The host row goes whether or not the
definition itself resolved: an unmapped French term does not turn the host into
something Finance cited, and leaving it in made the French edition resolve
`127(9)` and `66.2(5)` where the English resolved the definition.

**Checking that turned up a second, worse fault.** The host was being taken as
the *first* provision in the segment rather than the one the definition sits in,
so `paragraph 40(2)(b), definition of "principal residence" in section 54`
produced `40(2)(b)"principal residence"` - a path that does not exist. The same
fault mis-hosted `"death benefit"` onto `56(1)(a)(iii)` and `"employee benefit
plan"` onto `6(1)(g)`. The host is now the provision nearest the definition
phrase, preferring one introduced by "in" / "du" / "au" after the term.

`not_in_consolidation` falls from 26 to 19; every definition path now resolves
except `127(9)"flow-through mining expenditure"(a.2)`, which genuinely is not in
the 18 June 2026 consolidation.

### Finance calls a paragraph a subsection

The English edition writes `subsections 110.1(1), 118.1(1) and 38(a.2)`.
38(a.2) is a **paragraph**; the French edition says `alinéa 38(a.2)`. Resolved
correctly either way, because the grammar reads the shape of a citation rather
than the word introducing it. Recorded in `data/source_oddities.csv`, which now
catalogues seven such things.

### Net effect on resolution

| | before round 2 | after |
|---|---|---|
| reference rows | 792 | 774 |
| `resolved` | 611 | 600 |
| `not_in_consolidation` | 26 | 19 |
| paths resolved from French but not English | 2 | **0** |

Fewer resolved rows, and that is the improvement: 18 of them were citations
Finance never made.
