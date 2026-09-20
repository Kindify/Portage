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
