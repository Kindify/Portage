# Reference resolution rule

How a cross-reference in the source becomes a link to a provision, or honestly
fails to. Written before implementing, as with `docs/citation-path-rule.md`.

This covers **tagged** references only - the ones the source marks up as
elements. Every row produced under this rule carries `method = 'tagged'`.
References that exist only in prose are a separate job with a separate method,
a separate table and its own validation.

---

## The governing principle

**Which definition governs at a given location is a scope question, and this
tool does not answer scope questions.** A term can be defined in several places
in the same instrument, each definition applying to a different Part, section or
purpose. Deciding which one governs a particular sentence is legal
interpretation. CLAUDE.md puts that outside the data, so the rule below never
chooses among candidates. It records all of them and says how many there were.

---

## 1. `DefinitionRef`

A reference to a defined term. The element carries **no attributes at all** -
1,259 of them across both instruments and there is not one `link`, `fid` or
target of any kind. The only information is the term text.

### Matching

1. Normalise the reference's text with `normalise_term` - Unicode NFC, collapsed
   whitespace, case preserved. The **same** normalisation used to build
   definition citation paths, so the two sides cannot drift.
2. Compare for **exact equality** against `defined_term_en` (for an English
   reference) or `defined_term_fr` (for a French one), on definition records
   **in the same instrument**.
3. Nothing looser. No case folding beyond NFC, no stemming, no substring or
   prefix matching, no nearest match. A term either is the defined term or it is
   not.

A definition record counts as a candidate in a language only if it actually
carries text in that language. A record split into `X` and `X~fr` because the
two languages structure it differently is one candidate per language, not two.

### Recording the outcome

Every candidate gets a row in **`definition_ref_candidates` (ref_id,
definition_id)**. The reference itself carries a `resolution`:

| `resolution` | Candidates | `to_citation_path` |
|---|---|---|
| `unique` | exactly 1 | set to that definition |
| `ambiguous` | 2 or more | NULL - all candidates are in `definition_ref_candidates` |
| `unresolved` | 0 | NULL |

`ambiguous` is **not** a failure state. It is the true answer: the term is
defined in several places and the source does not say which one applies here.
A consumer that needs one answer joins `definition_ref_candidates` and applies
its own scope rule, in the open, rather than inheriting a silent guess from us.

### Two classes of candidate, both structural

A term is defined in the source in two structural forms, and both count:

| `candidate_kind` | What it is | Count (English Act) |
|---|---|---|
| `definition_record` | a `<Definition>` element | 2,387 terms |
| `inline_defined_term` | a `DefinedTerm` element in a provision's own `<Text>`, with no `<Definition>` wrapper | 964 |

ITA 10.1(5) is an inline site: *"an eligible derivative, of a taxpayer for a
taxation year, **means** a swap agreement..."*. It defines the term as plainly
as any wrapped definition.

**Inline sites are identified by element nesting, never by prose.** An inline
site is a `DefinedTermEn` / `DefinedTermFr` element with no `<Definition>`
ancestor. Nothing looks for the word "means", or any other wording. The ban on
text heuristics is untouched.

### What adding the inline class did to the numbers

Resolution over the 2,526 `DefinitionRef` rows, by which candidate classes are
in the index:

| Candidate classes | `unique` | | `ambiguous` | `unresolved` |
|---|---|---|---|---|
| `definition_record` only (before) | 1,237 | 49.0% | 801 | 488 |
| `inline_defined_term` only | 341 | 13.5% | 568 | 1,617 |
| **both (in force)** | **950** | **37.6%** | **1,207** | **369** |

Of the 950 unique resolutions, 888 land on a `definition_record` and 62 on an
`inline_defined_term`.

**The unique share fell and that is the right direction.** Unresolved dropped
from 488 to 369 - 119 references that looked as though nothing in the instrument
defined them turned out to have a definition after all. Those did not become
`unique`; most became `ambiguous`, because the term was already defined
elsewhere too. A term defined in both forms has two real definitions, and saying
so is more useful than a higher percentage bought by ignoring one of them.

---

## 1b. Candidates in the other instrument

The Regulations lean heavily on the Act's definitions, and a term a reference
names may be defined only in the other instrument.

Those definitions **are recorded as candidates**, with
`candidate_scope = 'other_instrument'`, so a reader can see them. **They never
change the resolution**, which is computed over `same_instrument` candidates
alone.

**Why.** Whether a definition in the Act governs a word used in the Regulations -
or the reverse - is a question about how the two instruments relate, and the
answer is usually carried in prose the markup does not encode: *"as defined in
subsection 207.5(1) **of the Act**"*. Deciding it from a term match alone would
be a legal conclusion drawn from a string comparison. The tool does not draw it.

691 references carry other-instrument candidates. 2,384 candidate rows are
scoped `other_instrument`; those references stay `unresolved`, with a reason
that names how many were found and where.

---

## 2. `XRefExternal`

A reference to another instrument. Carries `reference-type`
(`act`, `regulation`, `other`, `standard`) and usually a `link` - the Justice
Laws chapter identifier, such as `I-11` or `C.R.C.,_c._945`.

**Store** the raw text, the `reference-type`, the `link`, and the target
instrument where the link identifies one this dataset holds (`I-3.3` → ITA,
`C.R.C.,_c._945` / `C.R.C.,_ch._945` → ITR).

**Resolve to a `citation_path` only where the target is the ITA or the
Regulations *and* the reference names a provision.**

In this source that second condition is never met. The element's text is always
the instrument's *title* - "Income Tax Act", "Inquiries Act", "Loi de l'impôt
sur le revenu". Of 2,837 `XRefExternal` elements, exactly one contains anything
resembling a provision number, and it is `The Loans Act, 1983(2)` - part of the
Act's own title. 752 point at the ITA or the Regulations, every one of them
naming the instrument as a whole.

So every `XRefExternal` is stored `unresolved`, with its reason:

- `names an instrument, not a provision` - the target is the ITA or ITR
- `refers to an instrument this dataset does not hold`
- `no link attribute - the source names the instrument in text only`

This is a property of the source, not a shortfall in the rule. There is no
provision on the other end to point at.

---

## 3. `XRefInternal`

**There is exactly one, in the French Act, and it is not resolved.**

The English Act, the English Regulations and the French Regulations contain
none. The French Act contains one, in `93(5.2)(a)`, whose text is `51`.

It is stored and left `unresolved`, because resolving it would be wrong. Its
surrounding text reads:

> le contribuable n'a pas fait le choix prévu à l'article **51** de la *Loi de
> 2012 apportant des modifications techniques concernant l'impôt et les taxes*

That is section 51 of a **different Act** - the 2012 technical amendments Act -
not section 51 of the Income Tax Act. An element named `XRefInternal` holding a
bare section number looks exactly like a reference to the current instrument,
and a rule that resolved it on that basis would produce a confidently wrong
link. The one case in the corpus is the counter-example.

It carries the reason `bare section number with no instrument qualifier - the
target instrument is named in prose, not in the markup`.

### Fixture for the Phase 1 reference grammar

**A bare section number with no instrument qualifier never resolves.**

`93(5.2)(a)` in the French Act is the worked case, and it is kept as a test
fixture (`test_bare_section_number_never_resolves`) so the rule survives contact
with the reference grammar Phase 1 has to write for the tax expenditure report.
That grammar will meet the same shape constantly - "section 51", "paragraph
20(1)(ss)" - and the safe default is the one this case forces: without an
instrument qualifier, record the raw text and resolve nothing.

The trap is worth naming precisely. The element is called `XRefInternal`. It sits
in the Income Tax Act. Its content is a bare section number, and section 51 of
the Income Tax Act exists. Every signal available in the markup says "resolve
this to 51". Only the prose says otherwise. A rule that resolved on markup alone
would have produced a link that is wrong, confident, and invisible.

---

## What this rule does not do

- It does not read body text. Every reference here exists because the source
  tagged it as an element.
- It does not choose among candidate definitions.
- It does not resolve across instruments. Other-instrument definitions are
  recorded as candidates and never counted toward resolution.
- It does not infer a target from surrounding prose - the `XRefInternal` case
  above shows why that is not a conservative choice but a dangerous one.

Each of these is a real limitation, and each is visible in the counts rather
than hidden by a higher resolution rate.

---

# Part 2 - references in the tax expenditure report

Everything above governs references **tagged as elements** in the Justice Laws
XML. This part governs the `Legal reference` field of a measure in the Report on
Federal Tax Expenditures, which is prose and must be extracted by pattern.

**Why pattern extraction is allowed here and was not in Part 1.** Failure is
visible. A reference either resolves to a `citation_path` that exists in
`sections` or it does not, and the unresolved list is published. A mis-parsed
*structure* in Phase 0 would have been invisible; a mis-parsed *reference* here
shows up as an unresolved row or as a link a reader can check. Every row carries
`method = 'pattern'` so it can never be confused with Part 1's tagged rows.

Written before implementing, against the 229 English values in the committed
snapshot.

## 1. The shapes that actually occur

Counted across all 229 English `Legal reference` values:

| Shape | Count | Example |
|---|---|---|
| instrument first, then provisions | most | `Income Tax Act, section 153` |
| instrument **last**, after "to the" | 38 | `Part V of Schedule V to the Excise Tax Act` |
| `and` lists | 78 | `subsections 39(1.1) and (2)` |
| `to` ranges | 33 | `sections 110.6 to 110.7` |
| hyphen ranges | some | `Sections 2-5.3 and 9-12 of Part I of Schedule V` |
| Schedule / Class | 29 / 5 | `Class 43.1 of Schedule II` |
| Part in roman numerals | 25 | `Part VI of Schedule V` |
| **two instruments run together, no separator** | 11 | `subsection 66.1(6)Income Tax Regulations, section 1219` |
| missing space after the comma | several | `Excise Tax Act,subsection 259(3)` |
| `Not yet legislated as of December 31, 2025.` | 8 | no reference at all |
| definition reference | some | `section 123(1), definition of "financial service"` |
| **formula variable** | 1 | `the description of L in subsection 1400(3)` |

## 2. The rule

### An instrument qualifier is required

A provision reference resolves **only** when an instrument is named. This is the
same rule that the single `XRefInternal` in Part 1 forced: a bare section number
with no instrument qualifier never resolves, because section 51 of *something*
is not a citation. The fixture for it is
`test_bare_section_number_never_resolves`.

The instrument is carried from the nearest naming, in either direction:

- **Instrument first:** `Income Tax Act, section 153` - the instrument governs
  every provision that follows, until another instrument is named.
- **Instrument last:** `Part V of Schedule V to the Excise Tax Act` - the
  instrument governs the provisions that precede it in that segment.

**Segments are split on instrument names wherever they appear**, including
mid-string with no separator, which the report does 11 times.

### Only the Income Tax Act and the Income Tax Regulations resolve

| Instrument | `instrument` | Resolves? |
|---|---|---|
| Income Tax Act | `ITA` | yes, to a `citation_path` |
| Income Tax Regulations | `ITR` | yes, to a `citation_path` |
| Excise Tax Act | `ETA` | **no** - stored with the instrument name |
| Income Tax Application Rules | `ITAR` | no |
| Canada Pension Plan | `CPP` | no |
| Employment Insurance Act | `EI` | no |
| anything else | as published | no |

Everything other than the ITA and the Regulations is stored **unresolved, with
its instrument name recorded** - it is a real reference to a real provision, in
an instrument this dataset does not hold. That is a gap in coverage, not a
failure of parsing, and the two must not look alike.

*Observed in the 2026 edition:* the Excise Tax Act appears 38 times. The Income
Tax Application Rules, the Canada Pension Plan and the Employment Insurance Act
do **not** appear at all in this edition's English values, though the grammar
recognises them.

### Provision forms that resolve

Against a `citation_path` in `sections`, for the ITA and ITR only:

```
section 153                 -> 153
subsection 39(1.1)          -> 39(1.1)
subsections 39(1.1) and (2) -> 39(1.1), 39(2)      [the section carries across a list]
paragraph 20(1)(ss)         -> 20(1)(ss)
paragraphs 1100(1)(a.3) and (yb)
                            -> 1100(1)(a.3), 1100(1)(yb)
sections 110.6 to 110.7     -> every section in the range that exists
```

A list **inherits the previous item's prefix at matching depth**, not merely
its section number:

```
subsections 39(1.1) and (2)          -> 39(1.1), 39(2)
paragraphs 1100(1)(a.3) and (yb)     -> 1100(1)(a.3), 1100(1)(yb)
paragraphs 110(1)(d), (d.01) and (d.1)
                                     -> 110(1)(d), 110(1)(d.01), 110(1)(d.1)
```

A continuation with one bracketed level replaces the last level of the previous
path; with two, the last two. Inheriting copies levels that are present in the
same field, so it is mechanical and not a guess about meaning. Inheriting only
the *section* would have produced `1100(yb)`, a provision that does not exist.

**Bracketed levels are matched narrowly** - digits with optional dots and up to
two trailing letters, one or two letters with optional dotted suffix, roman
numerals, or up to four capitals. An earlier, looser version accepted any
bracketed word and read `section 258 (rebate)` as the provision `258(rebate)`.

A range enumerates only the paths that **exist** in `sections`. It never invents
one, and a range whose endpoints do not exist stays unresolved.

### Paragraphs of a definition

The report cites a paragraph inside a defined term:

```
subsection 127(9), paragraph (a.3) of definition of "investment tax credit"
```

This resolves to **`127(9)"investment tax credit"(a.3)`** - the key Phase 0
already built for definition paragraphs, so the target exists and nothing is
invented. Resolving it as `127(a.3)`, which an earlier version did, pointed at
a provision that does not exist.

The shape is: a subsection, a paragraph label, and a defined term, in any order
within the segment. All three must be present. A definition reference with no
paragraph resolves to the definition itself, `127(9)"investment tax credit"`.

**In French references the term must be translated before it can be a key.**
Phase 0 keys every definition by its **English** term, so a French reference
naming *crédit d'impôt à l'investissement* has to reach the English key. The
only mechanical route is Phase 0's own bilingual join: look the French term up
in `defined_term_fr` and take the `defined_term_en` from the same record.

That join is only trustworthy where Phase 0 established it symmetrically - both
files agreeing about both terms. Where the term does not join, the reference is
**unresolved with the reason `term_not_joined`**, never guessed. This is the
`definition_join_suspects` machinery from Part 1 doing a second job: a term we
declined to pair across languages is a term we must decline to resolve across
languages.

### Formula variables resolve to their subsection

`the description of L in subsection 1400(3)` resolves to **`1400(3)`**, with the
whole phrase kept in `raw_text`. The variable is part of the provision's text,
not a separately addressable unit - Phase 0 stores formula content as
non-addressable fragments - so the subsection is the correct and honest target.
The reader keeps the variable because `raw_text` keeps it.

### Schedules, Classes and Parts do not resolve

`Class 43.1 of Schedule II`, `Part VI of Schedule V`, `Part I` - Phase 0 parses
only the enacted `<Body>` of each instrument and holds no Schedule records, so
there is nothing to resolve to. These are stored unresolved with the raw text
and the instrument, and they are a known coverage gap already stated in README.

### Nothing else resolves

`Not yet legislated as of December 31, 2025.` produces **no reference rows at
all** - it is a statement that no provision exists yet, not an unresolved
reference, and recording it as one would overstate the failure rate.

Anything the grammar does not recognise is stored as a single unresolved row
with the whole field as `raw_text`. Never dropped, never guessed.

## 3. What is reported

`resolution_rate` is reported, never asserted. Unresolved rows go to
`data/unresolved_references.csv` against a committed fixture. **A build that
resolved 100% would be evidence of a bug**, because the Excise Tax Act
references and the Schedule references cannot resolve by construction.

---

## 4. Two things the open data CSV cannot settle

### It cannot pair measures across languages

The open data release publishes the cost tables in both languages, and if the
two files listed measures in the same order that order would be a pairing
supplied by Finance itself - better evidence than any signature we compute.

**It does not.** Checked directly against the committed snapshot: of 523 data
rows in each file, only **208 (39.8%)** carry the same eight year-values at the
same position, and the first row is *10% Temporary Wage Subsidy for Employers*
in English against *Abattement d'impôt du Québec* in French. Each file is
alphabetical **in its own language** - the same phenomenon as the definitions in
Phase 0, the part pagination in section 7 of the source notes, and the measure
order in the pages themselves.

So there is no `join_method = 'ogl_csv_order'`. Every pair is joined by content -
reference set plus cost values - and the 36 measures that do not join uniquely
stay in `data/measure_join_gaps.csv` as singles.

### Number of beneficiaries is prose, and is read as prose

The field is a sentence: *"About 328,000 employers claimed this subsidy in
2020."* There is no markup separating the count from the year from the
commentary, so a year and a count can only be read by pattern.

The rule is deliberately narrow. A row is populated **only** where the field
contains exactly one `<number> … in <year>` pair. Two pairs, or none, leaves
`year` and `count` NULL. `raw_value` always holds the published sentence, and
every row carries `method`: `'pattern'` where a count was read, `'none'` where
it was not.

**75 of 458 rows are populated.** The other 383 say things like *"No data is
available."* or *"The number of corporations affected by this measure is not
published in order to preserve taxpayer confidentiality."* - sentences with no
count in them at all. Extracted rows are catalogued in
`data/beneficiary_counts_extracted.csv` against a fixture, so any change in what
the pattern reads is visible.

This field is the weakest thing in Phase 1 and is marked as such. Unlike a
reference, a wrong count does not announce itself by failing to resolve.
