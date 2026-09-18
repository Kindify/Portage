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

### The rule, in order — term extraction

Reading a term is a structural operation: `<DefinedTermEn>` and
`<DefinedTermFr>` are elements. But *which* element is the definition's own term
is not obvious, and getting it wrong produces plausible, silently wrong keys.
The rule below is the third version this session; the earlier two and what broke
them are tabulated in `docs/source-notes.md` section 5.

1. **Find the definition's opening `<Text>`** - its first direct `<Text>` child.
   A definition with no such child has no term.
2. **The own term is the first `DefinedTermEn` or `DefinedTermFr` among the
   direct children of that `<Text>`.** Direct children only. A descendant search
   returns the first term *anywhere* in the body, which is normally a
   cross-reference to a different definition - it keyed "action admissible" to a
   phrase quoted in its own text and collapsed three definitions in 135.2(1)
   onto one path.
3. **The other language's equivalent is the LAST element of the opposite type
   anywhere in the definition's subtree**, excluding any nested `Definition`.
   It is published in parentheses at the end, which for a definition with
   paragraphs is after the last paragraph, not in the opening `<Text>`.
   Restricting this step to the opening `<Text>` loses the equivalent on more
   than half of them - 984 of 2,202 in the French file against 2,078 across the
   subtree. Taking the *last* match rather than the first avoids the
   cross-references, which occur mid-body.
4. **Normalise each term:** Unicode NFC, collapse internal whitespace, strip
   ends. Nothing else. Lowercasing and quote-stripping were measured against the
   real files and changed the join rate by exactly zero.

### Building the key

1. **English term** where present - this is what makes the key
   language-independent, since the French file carries `<DefinedTermEn>` on
   2,078 of its 2,206 definitions.
2. **French term** where no English term exists.
3. **Ordinal** `~d<n>` where neither exists.

Steps 2 and 3 set `label_anomaly = 1` and are listed in
`data/definition_key_fallbacks.csv`.

### The join must be symmetric

A shared key is necessary but not sufficient. A definition in the English file
is joined to one in the French file **only if both files agree about both
terms**:

```
english_file.own_english_term    == french_file.extracted_english_term
english_file.extracted_french_term == french_file.own_french_term
```

If the two files disagree about what the other language calls this definition,
the shared key is not evidence that they are the same provision. Those pairs are
**not joined**: the French record becomes its own row at `<path>~fr`, both halves
carry `bilingual_gap = 1`, and the case is listed in
`data/definition_join_suspects.csv`.

**2,021 of 2,046 joins are symmetric (98.8%). 25 are not.** All 25 fail on the
French term while agreeing on the English one. Eight are orthographic variance
between the files - `œ` against `oe`, a missing accent. The rest are real
disagreements, most of them typos in the English file's parenthetical
(`compe` for `compte`, `jurisdiction` for `juridiction`, `platforme` for
`plateforme`), but some substantive: the English file gives the French term for
248(1) "business" as *commerce* where the French file's own term is *affaires*.

The test earns its place on 44.1(1) "eligible small business corporation share",
which the Act defines **twice**. The symmetric check caught that the join had
paired the English text of one definition with the French text of the other.

### Duplicate keys

The Act does define the same term twice in one provision, and the published XML
does repeat a label - the French 142.6(8)b) numbers two subparagraphs `(iv)`
where the English has `(iv)` and `(v)`. A second occurrence gets a `#2` suffix,
`label_anomaly = 1` and a catalogue row. Nothing is dropped, and the source text
is never altered.

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

---

## 6. Divergent provisions: the `alignment_unverified` criterion

Joining English to French on `citation_path` is not by itself enough to honour
"never force alignment". Two records can share a path and not correspond.

### The criterion, exactly

For each parent path present in **both** language files, compare the **ordered
tuple of its children's citation paths**, computed separately for addressable
children and for non-addressable fragments:

```
children(parent, addressable) = tuple of child citation_paths,
                                in document order,
                                restricted to that addressability
```

If `children_en(parent, k) != children_fr(parent, k)` for a given parent and
addressability `k`, then every child path in
`set(children_en) ∩ set(children_fr)` for that parent and `k` is **divergent**.

The test is entirely structural. It compares paths, never text, and makes no
judgment about whether two provisions correspond - it identifies where a shared
label is not *evidence* that they do.

The two addressability classes are computed separately because they are
independent: a subsection whose continued-text fragments differ in number says
nothing about whether its paragraphs correspond.

### What happens to a divergent path

| | Addressable children | Non-addressable fragments |
|---|---|---|
| Count (ITA) | 333 | 2,408 |
| Resolution | **split** | **flagged** |
| English record | keeps the path | keeps the path |
| French record | moves to `<path>~fr` | joined onto the same row |
| `bilingual_gap` | 1 on both halves | 0 |
| `alignment_unverified` | 0 | **1** |
| `same_path_counterpart` | points at the other half | NULL |

Addressable rows are split because they are the rows a person cites, and a
citation returning two unrelated texts is the failure this project exists to
prevent. Fragments are continued text and formulas - not citable, and each
language round-trips in its own order - so the flag is proportionate there.

Both classes are listed in `data/alignment_unverified.csv`, with a `resolution`
column saying which treatment each received, diffed against a committed fixture.

### The worked case: ITA 51(1)

```
EN 51(1) paragraphs:  (a) (b) (c) (d) (d.1) (d.2) (e) (f)
FR 51(1) paragraphs:  a)  b)  b.1) b.2) c)   d)
```

The tuples differ, so `(a) (b) (c) (d)` - the four paths present in both - are
divergent and are split. `(d.1) (d.2) (e) (f)` and `b.1) b.2)` were already gaps.
The result is that **no row under 51(1) carries both `text_en` and `text_fr`**,
which is asserted by a test. English `51(1)(a)` is one of the opening conditions;
French `51(1)a)` is one of the rules. They share a label and nothing else.

Note that `51(1)` *itself* remains joined. The subsection genuinely corresponds
in both languages; only its internal division differs.
