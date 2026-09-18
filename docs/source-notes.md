# Source notes

What the candidate source data actually looks like, written after inspecting
the real files. Nothing here is assumed; every claim was checked against the
bytes on 2026-09-18.

Two candidates were inspected:

1. **A2AJ Canadian Legal Data** (`a2aj/canadian-laws` on HuggingFace) - the
   primary candidate named in CLAUDE.md.
2. **Justice Laws XML** (`laws-lois.justice.gc.ca`) - the fallback named in
   CLAUDE.md.

**Conclusion up front: use the Justice Laws XML.** A2AJ cannot serve Phase 0
because its deepest unit of structure is the section, and everything below
that is Markdown prose. Reasoning in full below.

---

## 1. A2AJ Canadian Legal Data

### Where it is

| | |
|---|---|
| Dataset | `a2aj/canadian-laws` |
| Page | <https://huggingface.co/datasets/a2aj/canadian-laws> |
| Income Tax Act | `LEGISLATION-FED/train.parquet`, 86.3 MB (90,493,725 bytes) |
| Income Tax Regulations | `REGULATIONS-FED/train.parquet`, 99.0 MB (103,909,943 bytes) |
| Dataset last updated | 2026-09-12 |

Downloaded 2026-09-18. SHA-256:

```
8465fe0a01226c487d4164d6b16825fd7e4a32ee7aa6c21d68e88a950c3c837a  LEGISLATION-FED.parquet
3c693cc138c3f5628ecbea3db253585c1afa949bf531685b1fbbb2e85d5f0c18  REGULATIONS-FED.parquet
```

`LEGISLATION-FED` holds 969 rows (one per federal Act); `REGULATIONS-FED`
holds 4,886. **One row is one entire instrument.** There is no way to download
only the Income Tax Act - it is a single row inside the 86 MB file.

### The two rows we care about

| | Income Tax Act | Income Tax Regulations |
|---|---|---|
| Row index | 504 in `LEGISLATION-FED` | 539 in `REGULATIONS-FED` |
| `name_en` | Income Tax Act | Income Tax Regulations |
| `name_fr` | Loi de l'impôt sur le revenu | Règlement de l'impôt sur le revenu |
| `citation_en` | RSC 1985, c 1 (5th Supp) | CRC, c 945 |
| `citation_fr` | LRC 1985, c 1 (5e suppl) | CRC, ch 945 |
| `num_sections_en` / `_fr` | 767 / 767 | 9,762 / 9,762 |
| `unofficial_text_en` | 7,319,300 chars | 2,416,477 chars |
| `unofficial_text_fr` | 7,779,383 chars | 2,546,893 chars |

### Provenance fields

```
Income Tax Act
  source_url_en        https://laws-lois.justice.gc.ca/eng/XML/I-3.3.xml
  source_url_fr        https://laws-lois.justice.gc.ca/fra/XML/I-3.3.xml
  scraped_timestamp_en 2026-09-11 15:45:30+00:00
  scraped_timestamp_fr 2026-09-11 15:45:30+00:00
  document_date_en     1994-03-01

Income Tax Regulations
  source_url_en        https://laws-lois.justice.gc.ca/eng/XML/C.R.C.%2C_c._945.xml
  source_url_fr        https://laws-lois.justice.gc.ca/fra/XML/C.R.C.%2C_ch._945.xml
  scraped_timestamp_en 2026-09-11 15:45:30+00:00
  scraped_timestamp_fr 2026-09-11 15:45:30+00:00
  document_date_en     1979-08-15
```

Note `document_date_*` is the original enactment/registration date, **not** the
consolidation date. It is not a usable snapshot date for our purposes.

Note also that **A2AJ's own `source_url` is the Justice Laws XML.** A2AJ is a
derived, lossy copy of the source we would otherwise use directly.

### `upstream_license`, verbatim

Identical string on both rows (spelling as published, including the typos
"Goverment" and "specificed"):

> See upstream license, including requirements related to attribution,
> non-endorsement, and reproduction of the upstream license. The upstream
> license is the Open Goverment License - Canada, as specificed at Department
> of Justice Github data source: https://perma.cc/B4ER-VTMQ. Details of Open
> Government License - Canada are available here: https://perma.cc/CDW7-A2VN.
> Note: This is an unofficial reproduction of Federal legislation, made without
> endorsement or affiliation by Goverment of Canada. The reproduction contains
> information licensed under the Open Government Licence - Canada.

(The Regulations row is word-identical except "Federal regulations" for
"Federal legislation".)

A2AJ's own code and collection methods are MIT.

### Structure: the disqualifying finding

`unofficial_sections_en` is a JSON object mapping a section number to a string.
Checked directly:

```
keys containing parentheses (i.e. subsection-level):  0
'87' present?      True
'87(4)' present?   False
'55(3)' present?   False
'55(3)(b)' present? False
```

All 767 keys are bare section numbers (`'1'`, `'2'`, ... `'10.1'`, `'12.1'` ...).
The entire contents of section 87 - subsections (1), (1.1), (2), (4) and so on,
with all their paragraphs and subparagraphs - is **one flat string**. Its first
1,400 characters begin:

```
'(1) In this section, an amalgamation means a merger of two or more
corporations each of which was, immediately before the merger, a taxable
Canadian corporation ... \n\n(a) all of the property (except amounts
receivable from any predecessor corporation ...) ... \n\n(b) all of the
liabilities ... \n\n(c) all of the shareholders ... \n\n(1.1) For the pu'
```

So the answers to the questions Phase 0 asks of a source are:

| Question | A2AJ answer |
|---|---|
| Is the hierarchy preserved as structure? | **No.** Section is the deepest unit. Below that it is Markdown prose. |
| Are English and French present? | Yes - `unofficial_text_fr`, `unofficial_sections_fr`, both populated. |
| Are they aligned? | At the section level only (767 = 767). Nothing below to align. |
| Are history notes present? | **No.** Searched the full text for amending-statute markers: `NOTE` 0 hits, `R.S., 1985` 0 hits, `[NOTE:` 0 hits. They have been stripped. |
| Are headings separate from body text? | **No.** Marginal notes survive only as `**Bold**` inside the Markdown, e.g. `**Amalgamations**\n\n**87** (1) In this section...`. The sections JSON value is body text with no heading field. |

### Why this cannot serve Phase 0

To get `87(4)` out of A2AJ we would have to split a Markdown blob on patterns
like `\n\n(4) ` - inferring structure from line breaks and number patterns, and
recovering headings from bold text. CLAUDE.md bans exactly this, and names it
as the cause of three attribution bugs during scoping. There is no second way
in: the structure is not merely hidden, it has been discarded.

History notes and headings-as-data are gone too, and Phase 0's `sections` table
has columns for both.

---

## 2. Justice Laws XML (recommended source)

### Where it is

All four files retrieved 2026-09-18, HTTP 200:

| Instrument | Lang | URL | Size |
|---|---|---|---|
| Income Tax Act | EN | `https://laws-lois.justice.gc.ca/eng/XML/I-3.3.xml` | 13.4 MB (14,082,767 B) |
| Income Tax Act | FR | `https://laws-lois.justice.gc.ca/fra/XML/I-3.3.xml` | 14.1 MB (14,877,853 B) |
| Income Tax Regulations | EN | `https://laws-lois.justice.gc.ca/eng/XML/C.R.C.,_c._945.xml` | 5.4 MB (5,696,292 B) |
| Income Tax Regulations | FR | `https://laws-lois.justice.gc.ca/fra/XML/C.R.C.,_ch._945.xml` | 5.7 MB (5,995,473 B) |

38.6 MB for all four - less than the A2AJ parquet alone.
All four `Last-Modified: Thu, 20 Aug 2026`.

### Consolidation date, from inside the file

The root element carries the dates directly, so the snapshot date is a recorded
fact rather than a download timestamp. Identical across all four files:

```
lims:pit-date         = 2026-06-18    (point-in-time date of the consolidation)
lims:lastAmendedDate  = 2026-06-18
lims:current-date     = 2026-06-21    (currency date)
```

The Act's `<Identification>` also carries a consolidation stage date of
2026-06-22, the chapter number `I-3.3`, and `AnnualStatuteNumber` `1 (5th Supp.)`
with year `1985` - i.e. the citation is machine-readable, not parsed from a string.

**`lims:pit-date` (2026-06-18) is the value to record as `snapshot_date`.**

Root element is `<Statute>` for the Act and `<Regulation>` for the Regulations.

### Structure: every level we need is a real element

Element counts, both instruments, both languages:

| Element | ITA en | ITA fr | ITR en | ITR fr |
|---|---|---|---|---|
| `Section` | 785 | 785 | 520 | 520 |
| `Subsection` | 5,351 | 5,351 | 1,521 | 1,521 |
| `Paragraph` | 13,215 | 12,933 | 4,053 | 4,054 |
| `Subparagraph` | 8,468 | 8,219 | 2,614 | 2,607 |
| `Clause` | 2,878 | 2,813 | 786 | 788 |
| `MarginalNote` | 5,799 | 5,799 | 61 | 61 |
| `HistoricalNote` | 762 | 762 | 597 | 597 |

Also present: `Subclause` (773), `Subsubclause` (150), `Definition` (2,199),
`DefinedTermEn` (3,359), `ContinuedParagraph` (649),
`ContinuedSectionSubsection` (628), `Repealed` (548), `Formula*` families.

`Section`, `Subsection` and `MarginalNote` counts match **exactly** between
English and French. Paragraph-level counts differ slightly - see open questions.

### Raw record 1: Income Tax Act, subsection 87(4)

Nesting is real. `<Label>` carries the number; `<MarginalNote>` carries the
heading; `<Paragraph>` and `<Subparagraph>` are nested children, not text.

```xml
<Subsection lims:inforce-start-date="2019-01-01" lims:fid="291636" lims:id="291636">
  <MarginalNote>Shares of predecessor corporation</MarginalNote>
  <Label>(4)</Label>
  <Text>Where there has been an amalgamation of two or more corporations after
        May 6, 1974, each shareholder (except any predecessor corporation) who,
        immediately before the amalgamation, owned shares of the capital stock of a
        predecessor corporation (in this subsection referred to as the "old shares")
        ... shall be deemed</Text>
  <Paragraph lims:fid="291638">
    <Label>(a)</Label>
    <Text>to have disposed of the old shares for proceeds equal to the total of the
          adjusted cost bases to the shareholder of those shares immediately before
          the amalgamation, and</Text>
  </Paragraph>
  <Paragraph lims:fid="291639">
    <Label>(b)</Label>
    <Text>to have acquired the new shares of any particular class ... equal to that
          proportion of the proceeds described in paragraph 87(4)(a) that</Text>
    <Subparagraph lims:fid="291640">
      <Label>(i)</Label>
      <Text>the fair market value, immediately after the amalgamation, of all new
            shares of that particular class so acquired by the shareholder,</Text>
    </Subparagraph>
    <ContinuedParagraph lims:fid="291641">
      <Text>is of</Text>
    </ContinuedParagraph>
    <Subparagraph lims:fid="291642">
      <Label>(ii)</Label>
      <Text>the fair market value, immediately after the amalgamation, of all new
            shares so acquired by the shareholder,</Text>
    </Subparagraph>
  </Paragraph>
  <ContinuedSectionSubsection lims:fid="291643">
    <Text>except that, where the fair market value of the old shares immediately
          before the amalgamation exceeds ... the following rules apply:</Text>
  </ContinuedSectionSubsection>
  <Paragraph lims:fid="291644">
    <Label>(c)</Label>
    ...
  </Paragraph>
</Subsection>
```

This satisfies acceptance test 3 ("87(4) exists as its own record under 87")
structurally, not by pattern matching.

### Raw record 2: Income Tax Act, paragraph 55(3)(b)

Four levels deep - Section > Subsection > Paragraph > Subparagraph > Clause -
all real elements.

```xml
<Paragraph lims:inforce-start-date="2016-06-22" lims:fid="285923" lims:id="285923">
  <Label>(b)</Label>
  <Text>if the dividend was received</Text>
  <Subparagraph lims:fid="285924">
    <Label>(i)</Label>
    <Text>in the course of a reorganization in which</Text>
    <Clause lims:fid="285925">
      <Label>(A)</Label>
      <Text>a distributing corporation made a distribution to one or more
            transferee corporations, and</Text>
    </Clause>
    <Clause lims:fid="285926">
      <Label>(B)</Label>
      <Text>the distributing corporation was wound up or all of the shares of its
            capital stock owned by each transferee corporation immediately before
            the distribution were redeemed or cancelled otherwise than on an
            exchange to which subsection 51(1), 85(1) or 86(1) applies, and</Text>
    </Clause>
  </Subparagraph>
  <Subparagraph lims:fid="285927">
    <Label>(ii)</Label>
    <Text>on a permitted redemption in relation to the distribution or on the
          winding-up of the distributing corporation.</Text>
  </Subparagraph>
</Paragraph>
```

### Raw record 3: French 87(4), showing bilingual alignment

Same `lims:inforce-start-date`, same `<Label>(4)</Label>`, heading in
`<MarginalNote>`, identical nesting:

```xml
<Subsection lims:inforce-start-date="2019-01-01" lims:fid="284329" lims:id="284329">
  <MarginalNote>Actions d'une société remplacée</MarginalNote>
  <Label>(4)</Label>
  <Text>En cas de fusion de plusieurs sociétés après le 6 mai 1974, chaque
        actionnaire (à l'exclusion d'une société remplacée) qui était propriétaire,
        immédiatement avant la fusion, d'actions du capital-actions de l'une des
        sociétés remplacées (appelées les « anciennes actions » au présent
        paragraphe) ... est réputé :</Text>
  <Paragraph lims:fid="284331">
    <Label>a)</Label>
    <Text>avoir disposé des anciennes actions pour un produit égal au total des
          prix de base rajustés, pour lui, de ces actions immédiatement avant la
          fusion;</Text>
  </Paragraph>
  <Paragraph lims:fid="284332">
    <Label>b)</Label>
    <Text>avoir acquis les nouvelles actions d'une catégorie donnée du
          capital-actions de la nouvelle société à un coût égal à la fraction du
          produit visé ...</Text>
  </Paragraph>
</Subsection>
```

**Note the label convention differs by language:** English paragraphs are
`(a)`, `(b)`; French paragraphs are `a)`, `b)`. Subsection labels are `(4)` in
both. Citation paths will need a documented normalisation rule - see open
questions.

The `lims:fid` / `lims:id` attributes are stable per-element identifiers, but
they differ between the English and French files (291636 vs 284329 for the same
subsection), so **they cannot be used to join the two languages**. The join key
must be the citation path built from `<Label>` nesting.

### History notes are present and structured

```xml
<HistoricalNote>
  <HistoricalNoteSubItem>[NOTE: Application provisions are not included in the
    consolidated text; see relevant amending Acts and regulations.] </HistoricalNoteSubItem>
  <HistoricalNoteSubItem lims:inforce-start-date="2016-06-22" lims:fid="286071">
    R.S., 1985, c. 1 (5th Supp.), s. 55; 1994, c. 21, s. 24; 1995, c. 3, s. 16;
    1998, c. 19, s. 96; 2001, c. 17, s. 38; 2013, c. 34, ss. 62, 193, c. 40, s. 24;
    2016, c. 7, s. 5</HistoricalNoteSubItem>
  <HistoricalNoteSubItem lims:inforce-start-date="2021-06-29" lims:enacted-date="2021-06-29"
    lims:fid="1309808" lims:enactId="1305581">2021, c. 21, s. 1</HistoricalNoteSubItem>
  <HistoricalNoteSubItem lims:inforce-start-date="2026-03-26" lims:enacted-date="2026-03-26"
    lims:fid="1568383" lims:enactId="1561848">2026, c. 3, s. 10</HistoricalNoteSubItem>
</HistoricalNote>
```

There are 762 `HistoricalNote` elements against 785 `Section` elements, so they
attach at section level, not to every subsection. The `history_note` column
should reflect that rather than pretend to subsection granularity.

### Cross-references: partially structured, and this is a problem

| Element | Count (ITA en) | What it marks |
|---|---|---|
| `XRefExternal` | 1,112 | references to **other Acts**, with a `link` attribute |
| `DefinitionRef` | 1,158 | references to defined terms |
| `XRefInternal` | **0** | - |

```xml
<XRefExternal reference-type="act" link="I-11">Inquiries Act</XRefExternal>
```

But a reference from one provision to another **within** the same Act is plain,
untagged text:

```xml
<Text>Notwithstanding subsections 152(4) to (5), the Minister may make such
      assessments ... to give effect to subsection (1) for any taxation year.</Text>
```

There is no element around `subsections 152(4) to (5)`. Phase 0's
`cross_references` table is mostly about exactly these internal references.
Flagged as an open question in `PLAN.md` - this needs a decision from Matt, not
a guess from me.

### Reproduction terms, Justice Canada, verbatim

From the Department of Justice Canada Terms and Conditions,
<https://www.justice.gc.ca/eng/terms-avis/index.html> (retrieved 2026-09-18).

**Reproduction of federal law** - the provision that covers the Act and
Regulations themselves:

> Anyone may, without charge or request for permission, reproduce enactments
> and consolidations of enactments of the Government of Canada, and decisions
> and reasons for decisions of federally constituted courts and administrative
> tribunals, provided due diligence is exercised in ensuring the accuracy of
> the materials reproduced and the reproduction is not represented as an
> official version.

**Non-commercial reproduction** - covers website material generally:

> Information on this Web site has been posted with the intent that it be
> readily available for personal or public non-commercial use and may be
> reproduced, in part or in whole, and by any means, without charge or further
> permission, unless otherwise specified.

with the requirements to exercise due diligence in ensuring accuracy, to
identify the complete title of the materials reproduced and the author
organization, and to state

> the reproduction is a copy of an official work that is published by the
> Government of Canada and that the reproduction has not been produced in
> affiliation with, or with the endorsement of the Government of Canada

**Commercial reproduction:**

> Reproduction of multiple copies of materials on this site, in whole or in
> part, for the purposes of commercial redistribution is prohibited except with
> written permission from the Department of Justice Canada.

**What this means for us.** The first clause is a standing permission specific
to enactments and consolidations, and it is not conditioned on non-commercial
use. Our obligations under it are concrete and we can meet all three:

1. Exercise due diligence on accuracy - this is what the acceptance tests in
   CLAUDE.md are for, particularly the round-trip test.
2. Do not represent the reproduction as an official version - the README says
   so, and `meta` records the source URL and `pit-date` so anyone can check
   against the official consolidation.
3. Attribute the complete title and the author organization, and state
   non-endorsement.

How the third clause (commercial redistribution of "materials on this site")
interacts with the first for a downstream user of our SQLite file is a question
for Matt, not for me. Recorded as an open question in `PLAN.md`.

---

## Summary table

| Phase 0 needs | A2AJ | Justice Laws XML |
|---|---|---|
| Section as structure | yes | yes |
| Subsection as structure | **no** | yes (`<Subsection>`) |
| Paragraph / subparagraph / clause | **no** | yes (`<Paragraph>`, `<Subparagraph>`, `<Clause>`) |
| Headings as data | **no** (bold in Markdown) | yes (`<MarginalNote>`) |
| History notes | **no** (stripped) | yes (`<HistoricalNote>`) |
| French, aligned | section level only | yes, element-for-element |
| Consolidation date in file | no | yes (`lims:pit-date`) |
| Internal cross-references | no | **no** (untagged text) - open question |
| Download size for our two instruments | 185 MB | 38.6 MB |

---

## 3. Bilingual paragraph divergence - investigation (2026-09-18)

Session 1 flagged that paragraph-level element counts differ between the English
and French files (13,215 vs 12,933 `Paragraph` elements in the Act). This is the
result of a timeboxed investigation into why.

**Conclusion: the divergence is real bilingual drafting, not a parsing bug and
not missing content. Alignment must never be forced.**

### Method

Built a citation path for every addressable element in both files by walking
`<Label>` nesting only - no text heuristics. Normalised French labels to English
form (`a)` -> `(a)`) and French range connectors to English (`et` -> `and`,
`à` -> `to`), per decision 6. Compared the two sets of paths.

### Results

| | |
|---|---|
| EN paths | 28,089 |
| FR paths | 27,548 |
| Paths present in **both** | 27,348 (96.67% of the union) |
| EN-only (French text will be null) | 741 |
| FR-only (English text will be null) | 200 |
| Union - i.e. expected `sections` rows for the Act | **28,289** |
| Rows carrying `bilingual_gap = 1` | **941 (3.33%)** |
| Sections with any divergence | 157 of 785 (20%) |
| Sections fully aligned | 628 of 785 (80%) |

### Cause 1: range labels (resolved by normalisation)

Some `<Subsection>` labels are ranges covering several provisions at once, and
the connector word is language-specific:

```
EN <Label>(10) and (11)</Label>      FR <Label>(10) et (11)</Label>
EN <Label>(14.01) to (14.1)</Label>  FR <Label>(14.01) à (14.1)</Label>
```

Normalising `et` -> `and` and `à` -> `to` resolved **41 of the 42** subsection
mismatches. This is an artifact of language, not a structural difference, and
the normalisation rule belongs in the parser.

### Cause 2: malformed labels in the source XML (13 cases, all catalogued)

A small number of `<Label>` elements in the published XML are not clean labels.
These are quirks of the source, and they are listed in full so the parser can
handle them explicitly rather than silently:

| Path | EN raw label | FR raw label | What it is |
|---|---|---|---|
| `12.4` | `(b` | `b)` | missing closing bracket in the English source |
| `142.7(3)` | `“85` | `« 85` | an opening quotation mark used as a label |
| `181.7` | `“(a)` | `« a)` | quotation mark prefixed to the label |
| `190.21` | `“(a)` | `« a)` | same |
| `191(1)` | - | `i` | bare, unbracketed French label |
| `163.1(c)`, `51.1(c)`, `67.3(c)`, `67.3(d)` | `(c)` / `(d)` | - | English paragraphs with no French counterpart at that path |

These need a decision in session 2 or later, but they are 13 cases out of
28,289 and none of them is ambiguous once looked at directly.

### Cause 3: genuine bilingual drafting divergence (the large majority)

The remaining ~900 paths are cases where English and French express the same law
with **different paragraph structure**. This is not a defect. Section 51(1) is
the clearest example:

```
EN 51(1) direct paragraphs:  (a) (b) (c) (d) (d.1) (d.2) (e) (f)     [8]
FR 51(1) direct paragraphs:  a)  b)  b.1) b.2) c)   d)               [6]
```

and the content is offset, not merely relettered:

```
EN (a): "a capital property of the taxpayer that is another share of the
         corporation (in this section referred to as a "convertible property"), or"

FR a):  "sauf pour l'application des paragraphes 20(21) et 44.1(6) et (7) et de
         l'alinéa 94(2)m), l'échange est réputé ne pas constituer une disposition
         du bien..."
```

English breaks the opening *conditions* out into lettered paragraphs (a)-(c) and
then states the *rules* in (d) onward. French keeps the conditions in the
subsection's opening `<Text>` and letters only the rules. Same law, different
architecture. English `51(1)(a)` and French `51(1)a)` are **not** translations of
each other, and a parser that paired them by position would produce exactly the
kind of mis-attribution CLAUDE.md exists to prevent.

Section 7 shows the same thing one level down: paragraph counts match (40 = 40)
and `7(1)(a)`-`(e)` align perfectly, but subparagraph counts are 36 against 20.

### What this means for the build

The rule recorded in `docs/decisions.md` - join on `citation_path`, keep the
record with the other language null, set `bilingual_gap = 1`, never force
alignment - is the right one, and this investigation is the evidence for it.
Expect roughly **941 rows (3.3%) with `bilingual_gap = 1`** in the Act, spread
across 157 sections. Those rows are a feature of the law, not a failure of the
build, and the acceptance tests should assert the count rather than drive it
to zero.

---

## 4. XML vocabulary map - English Income Tax Act (2026-09-18)

Completed before writing the parser, per PLAN.md step 1. Counts are for
`data/ITA-eng.xml` under `<Body>`.

### The seven addressable levels

`Section` 763 (under Body), `Subsection` 5,309, `Paragraph` 13,165,
`Subparagraph` 8,465, `Clause` 2,876, `Subclause` 773, `Subsubclause` 150.

Two invariants were checked against the file rather than assumed, and the parser
depends on both:

- **An addressable unit has at most one direct `<Text>` child.** Zero units have
  more.
- **That `<Text>` never follows a structural child.** Zero violations. Opening
  text always comes first.

### Continued text - the thing that makes round-tripping hard

`ContinuedParagraph` 649, `ContinuedSectionSubsection` 628 (607 under Subsection,
21 under Section), `ContinuedSubparagraph` 201, `ContinuedDefinition` 148,
`ContinuedClause` 36, `ContinuedSubclause` 6, `ContinuedFormulaParagraph` 84.

1,337 units contain at least one. **802 of those have it interleaved between
structural children, not trailing.** 1,184 units have one fragment, 131 have two,
21 have three, one has five.

ITA 6(1)(f) is the clearest case - child sequence `SSSSCSCS`:

```
<Text>          the total of all amounts received by the taxpayer in the year ...
<Subparagraph>  (i)   a sickness or accident insurance plan,
<Subparagraph>  (ii)  a disability insurance plan,
<Subparagraph>  (iii) an income maintenance insurance plan, or
<Subparagraph>  (iii.1) a plan described in any of subparagraphs (i) to (iii) ...
<ContinuedParagraph>   to or under which the taxpayer's employer has made a contribution ...
<Subparagraph>  (iv)  the total of all such amounts received by the taxpayer ...
<ContinuedParagraph>   exceeds
<Subparagraph>  (v)   the total of the contributions made by the taxpayer ...
```

The fragments are connective tissue in the middle of a list. This is why
continued text is a row and not a column - see `docs/decisions.md`.

### Definitions

`Definition` 2,191. **None carries a `<Label>`**, but they contain 6,853
addressable descendants (3,602 `Paragraph`, 2,239 `Subparagraph`). Treating them
as transparent - letting their paragraphs attach straight to the parent
subsection - produces **1,068 colliding citation paths**: `248(1)(a)` occurs 86
times, `248(1)(b)` 86 times, `95(1)(a)` 27 times. 3,412 rows would be lost to the
uniqueness constraint. Hence the `~d<n>` ordinal.

`DefinedTermEn` 3,347 and `DefinedTermFr` 2,111 appear inside definition text.
Both language files carry both terms, but not universally - the English file has
an English term on 2,189 of 2,191 definitions and a French term on 2,072. So the
defined term is **not** a reliable universal key. It is stored in
`defined_term_en` / `defined_term_fr` so the option stays open.

### Formulas

`FormulaGroup` 754, of which **123 are nested inside another FormulaGroup**.
`FormulaDefinition` 2,236, `FormulaTerm` 2,236, `FormulaParagraph` 1,849,
`Formula` 754, `FormulaText` 754, `FormulaConnector` 744.

A `FormulaGroup` contains **no addressable descendants**, so it is captured whole.
But a `FormulaDefinition` can sit directly under a `Subsection` outside any
FormulaGroup, and then its variable name lives in a `<FormulaTerm>` or a
`<Label>` - which is body text, not metadata. Missing this cost 93 characters and
a round-trip test that passed while wrong. See `docs/decisions.md`.

### Everything else

- `Repealed` 548 - **inline inside `<Text>`**, so it needs no special handling.
  Carried through untouched, e.g. `[Repealed, 1996, c. 21, s. 2(1)]`.
- `Heading` 174 - direct children of `<Body>`, structural headings above section
  level (`PART I`, `DIVISION A`). Captured as non-addressable fragments.
- `HistoricalNote` 762 against 763 sections, attaching at section level only -
  so `history_note` is a section-level column in practice.
- `MarginalNote` 5,772 - the heading of a unit, stored in `heading_en`.
- Wrappers with no identity of their own: `SectionPiece`, `BodyPiece`,
  `Provision` (39), `ReadAsText`. The parser descends without emitting.

### Outside the Body

`<Statute>` has three `<Schedule>` children and a `<RecentAmendments>`.
The schedules hold the 22 `Section` elements that make up the difference between
785 in the file and 763 in the Body: "RELATED PROVISIONS" (16) and "AMENDMENTS
NOT IN FORCE" (6). A third, "Listed Corporations", holds no Section elements and
is currently not captured - flagged in PLAN.md.
