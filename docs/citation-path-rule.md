# The citation path rule

Written before the parser was implemented, so the rule is a specification rather
than a description of whatever the code happens to do.

A citation path is the key that identifies a provision and joins the English and
French versions of it. **It is derived from `<Label>` elements and element
nesting, and from nothing else.** Not body text, not position, not indentation,
not a number pattern.

---

## 1. Where the path comes from

Walk the XML from `<Body>` in document order. Seven element types are
**addressable levels**, in this nesting order:

| Element | Level name | English label form |
|---|---|---|
| `Section` | `section` | `87`, `110.6` |
| `Subsection` | `subsection` | `(4)`, `(2.1)` |
| `Paragraph` | `paragraph` | `(a)`, `(d.1)` |
| `Subparagraph` | `subparagraph` | `(i)`, `(iii.1)` |
| `Clause` | `clause` | `(A)`, `(B)` |
| `Subclause` | `subclause` | `(I)`, `(IV)` |
| `Subsubclause` | `subsubclause` | `1`, `2` |

The path of a unit is the normalised label of every addressable ancestor,
concatenated in nesting order, with no separators:

```
Section 110.6  >  Subsection (2.1)  >  Paragraph (a)  >  Subparagraph (ii)
    ->  110.6(2.1)(a)(ii)
```

Nesting is read from the XML tree. A `Paragraph` is a child of `55(3)` because
the XML nests it there, never because its text begins with "(b)".

---

## 2. Normalising a label

Applied in this order. Input is the `<Label>` text only. Full reasoning is in
`docs/decisions.md`.

1. **Collapse whitespace**, including the non-breaking spaces in the French
   file. Strip leading and trailing whitespace.
2. **Section level: bare.** `87` -> `87`. Strip one trailing period.
2b. **Subsubclause level: a bare numeral is the published form.** The XML labels
   these `1`, `2`, `3` without brackets, and that is correct. Flagging them
   would have buried 150 real anomalies under noise - the first run of this rule
   produced 176 "anomalies", of which 150 were this.
3. **Strip stray quotation marks** (`"` `"` `«` `»`) at either end, and any
   space left behind. → `label_anomaly = 1`
3b. **Remove whitespace inside brackets:** the published `(b )` becomes `(b)`,
   rather than falling apart into two tokens. → `label_anomaly = 1`
4. **Range connectors:** ` et ` -> ` and `, ` à ` -> ` to `.
5. **Bracket bare labels:** a token ending `)` without a leading `(` gets one.
   `a)` -> `(a)`. Applied per token inside ranges.
6. **Repair an unmatched opening bracket:** `(b` -> `(b)`. → `label_anomaly = 1`
7. **Anything still unrecognisable** is kept verbatim in the path,
   → `label_anomaly = 1`, and listed in `data/label_anomalies.csv`.

`label_raw` always holds the label exactly as published. Normalisation produces
the *key*; it never edits the source.

---

## 3. Worked examples

### Ordinary, both languages

| Source | EN label | FR label | Path |
|---|---|---|---|
| ITA s. 87, subsec. (4) | `(4)` | `(4)` | `87(4)` |
| ITA 87(4), para. (a) | `(a)` | `a)` | `87(4)(a)` |
| ITA 55(3)(b)(i)(A) | `(A)` | `A)` | `55(3)(b)(i)(A)` |

French `a)` becomes `(a)` by rule 5, so both languages land on the same key.
`label_raw` keeps `a)` for French and `(a)` for English.

### Range labels

| Source | EN label | FR label | Path |
|---|---|---|---|
| ITA 104, subsec. | `(10) and (11)` | `(10) et (11)` | `104(10) and (11)` |
| ITA 104, subsec. | `(14.01) to (14.1)` | `(14.01) à (14.1)` | `104(14.01) to (14.1)` |

Rule 4 maps the French connector to the English one. The label genuinely covers
several provisions at once; it is not split, because splitting would invent
records the source does not have.

### The malformed labels

Each gets `label_anomaly = 1` and a row in `data/label_anomalies.csv`, which the
test suite diffs against `tests/fixtures/label_anomalies.csv`. The English Act
yields **26**; the full list is the fixture, not a number quoted here.

The shapes that occur:

| Where | Raw label | Rule | Path |
|---|---|---|---|
| ITA 12.4 (EN) | `(b` | 6 - unmatched bracket | `12.4(b)` |
| ITA 12.4 (FR) | `b)` | 5 - bare label | `12.4(b)` |
| ITA 181.7 (EN) | `“(a)` | 3 - stray quote | `181.7(a)` |
| ITA 181.7 (FR) | `« a)` | 3 then 5 | `181.7(a)` |
| ITA 190.21 (EN) | `“(a)` | 3 | `190.21(a)` |
| ITA 190.21 (FR) | `« a)` | 3 then 5 | `190.21(a)` |
| ITA 142.7(3) (EN) | `“85` | 3 | `142.7(3)85` |
| ITA 142.7(3) (FR) | `« 85` | 3 | `142.7(3)85` |
| ITA 191(1) (FR) | `i` | 7 - no bracket to add | `191(1)i` |
| ITA 147.1(1) (EN) | `(b )` | 3b - space in brackets | `(b)` |
| ITA 70(1)(b) (EN) | `“12(1)(t)` | 3 then 7 - a quoted cross-reference used as a label | `12(1)(t)` |

Note that 12.4, 181.7 and 190.21 **converge on the same path in both languages**
once normalised. Before the rule they were counted as bilingual gaps; they are
not gaps, they are source typos.

---

## 4. Non-addressable fragments

Text that is part of a provision but is not itself citable gets a path built from
its parent plus a suffix that is **deliberately not valid citation syntax**, so
it can never be mistaken for one:

| Kind | Element | Path form | Example |
|---|---|---|---|
| continued text | `Continued*` | `<parent>~c<n>` | `6(1)(f)~c1` |
| definition | `Definition` (no label) | `<parent>~d<n>` | `248(1)~d17` |
| formula | `FormulaGroup` | `<parent>~f<n>` | `122.61(1)~f1` |

These rows carry `is_addressable = 0`. Citation lookups and the structure test
filter on `is_addressable = 1`; the round-trip test reads every row.

---

## 5. Uniqueness

`UNIQUE (act, citation_path)`. Paths are unique within an instrument, not
globally - the Act and the Regulations both have a section 200.
