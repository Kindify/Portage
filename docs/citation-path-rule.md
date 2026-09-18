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

## 4. Definitions

A `<Definition>` carries no `<Label>`, so it has no label to normalise. It does
carry addressable `Paragraph` children, which means it needs a key of its own -
without one, `248(1)(a)` collides 86 ways.

**The key is the subsection path plus the defined term in quotation marks:**

```
248(1)"active business"        and its paragraphs:  248(1)"active business"(a)
```

This is how these provisions are actually cited, and unlike a document-order
ordinal it is stable across languages.

### Why not an ordinal

Session 2 used a document-order ordinal, `248(1)~d17`. Session 3 checked whether
that could serve as a bilingual join key. **It cannot.** Each language file
alphabetises its definitions in its own language:

| position in 248(1) | English file | French file |
|---|---|---|
| 1 | absorbed capacity | tax shelter / *abri fiscal* |
| 2 | active business | separation agreement / *accord de séparation* |
| 3 | additional voluntary contribution | listed international agreement |
| 4 | adjusted cost base | estate of the bankrupt / *actifs du failli* |

`248(1)~d1` is "absorbed capacity" in English and "tax shelter" in French.
Joining on the ordinal would have mis-paired almost every definition in the Act -
the precise failure this project exists to prevent.

### The rule, in order

1. **Normalise the term:** Unicode NFC, collapse internal whitespace, strip
   leading and trailing whitespace. **Case is preserved as published.** Tested
   against the data: lowercasing and quote-stripping change the join rate by
   zero, so neither is applied - the less a rule does, the less it can do wrong.
2. **Prefer the English term** (`<DefinedTermEn>`), in both language files. This
   is what makes the key language-independent: the French file carries
   `<DefinedTermEn>` on 2,076 of its 2,206 definitions.
3. **Fall back to the French term** (`<DefinedTermFr>`) where no English term is
   present.
4. **Fall back to the ordinal** `~d<n>` only where **neither** term is present -
   2 definitions in the English file, 4 in the French. These get
   `label_anomaly = 1` and a row in `data/definition_key_fallbacks.csv`, which
   the tests diff against a committed fixture.

Fallbacks at step 3 are also catalogued, because a French-term key in the French
file cannot join an English-term key in the English file, and the reader should
be able to see which definitions those are rather than infer them from a gap
count.

### Expected join

2,048 definition keys occur in both files. About 140 occur in one only, mostly
where the French file carries no English term and the key therefore falls back to
French. Those are genuine bilingual gaps: there is no mechanical way to pair
them, and guessing is not an option. They carry `bilingual_gap = 1`.

---

## 4b. Non-addressable fragments

Text that is part of a provision but is not itself citable gets a path built from
its parent plus a suffix that is **deliberately not valid citation syntax**, so
it can never be mistaken for one:

| Kind | Element | Path form | Example |
|---|---|---|---|
| continued text | `Continued*` | `<parent>~c<n>` | `6(1)(f)~c1` |
| loose text | wrapper `<Text>` | `<parent>~t<n>` | `20.2(3)~t1` |
| formula | `FormulaGroup` | `<parent>~f<n>` | `122.61(1)~f1` |
| definition, no term | `Definition` | `<parent>~d<n>` | fallback only |

These rows carry `is_addressable = 0`. Citation lookups and the structure test
filter on `is_addressable = 1`; the round-trip test reads every row.

## 5. Uniqueness

`UNIQUE (act, citation_path)`. Paths are unique within an instrument, not
globally - the Act and the Regulations both have a section 200.
