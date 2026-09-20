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

A fresh seeded sample of 30, drawn from the build **after** the fix.
Not yet checked.

| | |
|---|---|
| Checked on | _(date)_ |
| Pass | |
| Fail | |

Record results below, one line per failure.
