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

---

## 5. How the term-extraction rule evolved (2026-09-18)

Three versions in one session. Each passed its immediate check and each was
wrong in a way the next piece of evidence exposed. Recorded because the pattern -
a plausible rule, a passing check, a silent error - is the one this project is
built to resist.

| Version | Rule | What it produced | Evidence that changed it |
|---|---|---|---|
| **1** | `definition.find('.//DefinedTermEn')` - first English term anywhere in the subtree | Looked right on 248(1). **3 collisions in the English file, 11 in the French.** Keyed "action admissible" to *prorogation de la Commission canadienne du blé*, a phrase quoted in its own body | Path collisions. The descendant search was returning cross-references to *other* definitions, not this one's term. Three definitions in 135.2(1) landed on one path |
| **2** | Own term = first term among **direct children of the opening `<Text>`**; equivalent = last opposite-type term among those same direct children | Collisions gone. But **1,219 French definitions reported "no English term"** against an expected ~130 | The equivalent is published in parentheses at the *end* of the definition, which for a definition with paragraphs is after the last paragraph - not in the opening `<Text>`. Measured: 984 found against 2,078 when the whole subtree is searched |
| **3** (current) | Own term = first term among direct children of the opening `<Text>`. Equivalent = **last** opposite-type term **anywhere in the subtree**, excluding nested `Definition` | 0 collisions both languages, 2,046 joins, 126 French-term fallbacks - matching the independent estimate | Held up under the symmetric-join test: 2,021 of 2,046 symmetric |

**What the symmetric test then added.** Version 3 still joined 25 pairs the two
files disagree about, including 44.1(1) "eligible small business corporation
share" - a term the Act defines twice, where the join had paired one
definition's English text with the other's French. A key that matches is not
proof that two records are the same provision. Those 25 are now unjoined and
catalogued in `data/definition_join_suspects.csv`.

**The generalisable point.** Each version was checked against the thing it was
most likely to get wrong, and each check passed until a *different* measurement
was taken - collisions, then coverage against an independent estimate, then
symmetry. No single check would have caught all three.

---

## 6. The Income Tax Regulations (2026-09-18)

Parsed with the same walker as the Act, with **no changes to the parser**. Both
round trips were exact on the first run. One change was needed to the *label*
rule - see below.

| | ITR en | ITR fr |
|---|---|---|
| records | 11,706 | 11,529 |
| sections (Body) | 499 | 499 |
| subsections | 1,519 | 1,519 |
| paragraphs | 4,008 | 4,009 |
| definitions | 489 | 494 |
| round trip | exact | exact |
| collisions | 0 | 0 |

Root element is `<Regulation>` rather than `<Statute>`; `lims:pit-date` is
2026-06-18, the same consolidation date as the Act. The file has **ten**
`<Schedule>` elements to the Act's three, plus an `<Order>` element before the
Body. As with the Act, only `<Body>` is parsed.

### Vocabulary the Regulations use that the Act does not

The Regulations contain **CALS table markup**, which the Act does not use at all:

| Element | Count (en) |
|---|---|
| `TableGroup` | 5 |
| `table`, `tgroup`, `tbody` | 5 each |
| `thead` | 3 |
| `row` | 157 |
| `entry` | 314 |
| `colspec` | 10 |
| `Caption` | 1 |

**These needed no special handling.** None of them is an addressable level, and
the walker's structural rules already cover them: it descends through the table
wrappers and emits each `<entry>`'s text as an ordered fragment. Table *text* is
preserved exactly and in document order - verified by the round trip and by
checking that specific cell contents ("First Home Savings Account Statement",
"T4FHSA") appear in the rebuilt text. Table *structure* - which cell is in which
row and column - is **not** modelled. That is a real limitation, stated in
README's Known limits.

This is the payoff from the `_is_text_leaf` rule written in session 2: it is a
structural test rather than a list of element names, so an element vocabulary
nobody had seen was captured rather than silently dropped.

### Vocabulary in the Act but not the Regulations

`LeaderRightJustified` (13) and `XRefInternal` (1).

**Correction to an earlier note.** Session 1 recorded zero `XRefInternal`
elements. That count was taken on the English Act only. The **French** Act has
exactly one. It does not change the decision to ship tagged cross-references
only - one tagged internal reference out of thousands is not a usable index - but
the earlier statement was too absolute.

### The one rule change: range labels at section level

The Regulations number sections `3000 to 3002` and `7302 and 7303` in English,
`3000 à 3002` and `7302 et 7303` in French. The Act has no section-level ranges,
so the label rule translated range connectors only *below* section level. The
result was two sections that looked French-only.

Caught by the section-count test, which expected 499 and found 501. Fixed by
applying the connector rule at section level too, with a pattern that recognises
a numeric range. `1100A` - a section label with a trailing letter, also new in
the Regulations - was already handled.

---

## 7. Report on Federal Tax Expenditures 2026 (Phase 1, step 2)

Inspection only. No parser has been written. Everything below was checked
against the live pages on **2026-09-19**, not assumed.

**Format: clean HTML, not PDF.** Each measure is a single `<table>` with one row
per field. This is the good case - the whole phase is a table walk, not a PDF
extraction job.

### Where it is

| Part | English | French |
|---|---|---|
| 3 (index) | `.../federal-tax-expenditures/2026/part-3.html` | `.../depenses-fiscales/2026/partie-3.html` |
| 4 | `.../2026/part-4.html` | `.../2026/partie-4.html` |
| 5 | `.../2026/part-5.html` | `.../2026/partie-5.html` |
| 6 | `.../2026/part-6.html` | `.../2026/partie-6.html` |
| 7 | `.../2026/part-7.html` | `.../2026/partie-7.html` |

English base: `https://www.canada.ca/en/department-finance/services/publications/federal-tax-expenditures/2026/`
French base: `https://www.canada.ca/fr/ministere-finances/services/publications/depenses-fiscales/2026/`

The French URLs come from the language toggle on each page, not from guesswork.

- `dcterms.issued` = `2026-02-26`, `dcterms.modified` = `2026-02-26` on both editions.
- **Retrieved: 2026-09-19.**

**Note on fetching.** `curl` cannot retrieve these pages: canada.ca closes the
HTTP/2 stream with `INTERNAL_ERROR`, and forcing HTTP/1.1 hangs. `HEAD` works,
`GET` does not. The pages were read through a real browser instead. Whatever the
build eventually uses will have to cope with that; the open data CSVs below
download with `curl` without complaint.

### The same data is on open.canada.ca, under the OGL

**Dataset:** Report on Federal Tax Expenditures - Concepts, Estimates and
Evaluations 2026
<https://open.canada.ca/data/en/dataset/0849a2c8-e65f-4874-a978-952029f39c11>
Published 2026-02-26, metadata modified 2026-06-01.
**Licence: Open Government Licence - Canada**, stated explicitly on the record.

Ten resources: the two HTML editions, plus **Data tables** and **Data tables -
metadata** as both XLSX and CSV in each language.

**But the CSV is not a substitute for the HTML.** Its own metadata names it
`REPORT ON FEDERAL TAX EXPENDITURES - SUMMARY OF COST INFORMATION`, and its
columns are:

```
MESURE / MEASURE, GROUP, SUBJECT, CATEGORY, TAX, DETAILS, 2020 … 2027
```

That is the **cost table and five classification fields**. It does **not**
contain the description, the objective, the implementation history, the
estimation or projection method, the number of beneficiaries - or, decisively,
**the legal reference**. The field Phase 1 exists to use is only in the HTML.

So: parse the HTML for measures and references; use the CSV as an **independent
check on the cost figures**, which is worth more than it sounds, because it was
produced by Finance rather than by us. Both CSVs have 524 rows.

### Licence terms, verbatim

**Department of Finance Canada, Terms and conditions**
<https://www.canada.ca/en/department-finance/corporate/terms-conditions.html>
(retrieved 2026-09-19).

Non-commercial reproduction:

> Unless otherwise specified you may reproduce the materials in whole or in
> part for non-commercial purposes, and in any format, without charge or further
> permission, provided you do the following:
>
> - exercise due diligence in ensuring the accuracy of the materials reproduced;
> - indicate both the complete title of the materials reproduced, as well as the
>   author (where available)
> - indicate that the reproduction is a copy of the version available at [URL
>   where original document is available]

Commercial reproduction:

> Unless otherwise specified, you may not reproduce materials on this site, in
> whole or in part, for the purposes of commercial redistribution without prior
> written permission from the copyright administrator.

Data licence - the clause that governs the open data release:

> All distributed data are subject to the Open Government Licence – Canada.

> Canada grants to the licensee a non-exclusive, fully paid, royalty-free right
> and licence to exercise all intellectual property rights in the data. This
> includes the right to use, incorporate, sublicense (with further right of
> sublicensing), modify, improve, further develop, and distribute the Data; and
> to manufacture or distribute derivative products.

> Please use the following attribution statement: Contains information licensed
> under the Open Government Licence – Canada.

**Reading of the two.** The open.canada.ca release is explicitly OGL, and the
Finance terms say distributed data are OGL. The webpage text carries the
narrower non-commercial terms. We take the cost data under the OGL and the page
text under the site terms, attribute both, and stay non-commercial - the same
position as Phase 0. Not a blocker; recorded so the distinction is visible.

### Measure counts

Cross-checked two ways: counting measure tables on each page, and counting the
links in the Part 3 index. **They agree, in both languages.**

| Part | English measures | French measures |
|---|---|---|
| 4 | 49 | **99** |
| 5 | 70 | **28** |
| 6 | 52 | 48 |
| 7 | 58 | 54 |
| **total** | **229** | **229** |

**The two editions paginate completely differently.** Part 4 holds 49 measures
in English and 99 in French. Measures are alphabetical *within each language*,
so the page boundaries fall at different points - the same phenomenon as
definitions in Phase 0, one level up. **The part number is not a join key and is
not even comparable across editions.** It should be stored as provenance, never
used for matching.

### How to tell a measure table from the others

A measure table has a `<caption>` carrying an `id` (a slug, e.g.
`10-temporary-wage-subsidy-employers`). A cost table has a caption with **no**
`id` reading "Cost Information: Millions of dollars" / "Renseignements sur les
coûts : Millions de dollars".

**That rule is not quite enough**, and the exception was found by counting:
Part 7 carries an appendix table, *Additional Information on Relevant Government
Programs by Subject*. In **English** it has a caption with no id; in **French**
the same table **does** have a caption id, and 17 body rows - so it passes both
the "has an id" and the "17 fields" tests and looks exactly like a measure.

**The reliable rule is the Part 3 index:** a measure is a table whose caption id
is linked from the Part 3 list. That gives 229 in both languages and excludes the
appendix. Anything on a part page that the index does not link is not a measure.

### The field set: 17 fields, every measure, both languages

Confirmed on all 229 measures in each language - the row count per measure table
is exactly 17 everywhere, with no exceptions.

| # | English label | French label(s) as published |
|---|---|---|
| 0 | Description | Description |
| 1 | Tax | Impôt ou taxe (96); **Direction de la politique de l'impôt** (2); Impôt (1) |
| 2 | Beneficiaries | Bénéficiaires |
| 3 | Type of measure | Type de mesure |
| 4 | Legal reference | Référence juridique |
| 5 | Implementation and recent history | Mise en œuvre et évolution récente |
| 6 | Objective – category | Objectif – catégorie (94); Objectif – Catégorie (5) |
| 7 | Objective | Objectif |
| 8 | Category | Catégorie |
| 9 | Reason why this measure is not part of benchmark tax system | Raison pour laquelle **la mesure** ne fait pas partie du **régime** fiscal de référence (92); Raison pour laquelle **cette mesure** ne fait pas partie du **système** fiscal de référence (7) |
| 10 | Subject | Thème (97); **Objet** (2) |
| 11 | CCOFOG 2014 code | Code de la CCFAP 2014 (97); **Code CCOFOG 2014** (2) |
| 12 | Other relevant government programs | Autres programmes pertinents du gouvernement (97); Autres programmes gouvernementaux pertinents (2) |
| 13 | Source of data | Source des données (92); Source **de** données (7) |
| 14 | Estimation method | Méthode d'estimation |
| 15 | Projection method | Méthode de projection |
| 16 | Number of beneficiaries | Nombre de bénéficiaires |

Counts above are from Part 4 French (99 measures); the same pattern holds on the
other parts.

Against CLAUDE.md's expected list: "type of tax" is published as **Tax**, and
there are **three** separate fields where CLAUDE.md listed "objective (with the
budget or document that stated it)" and "category" - the report has
`Objective – category`, `Objective` and `Category` as distinct rows.

### The field whose structure varies: the French labels

**English labels are perfectly stable** - 17 distinct labels, each appearing once
per measure, on every part.

**French labels are not.** Part 4 alone has **25 distinct normalised labels for
17 fields**. Three kinds of variation, and they need different handling:

1. **Non-breaking spaces and capitalisation.** `Objectif – catégorie` vs
   `Objectif – Catégorie`; `Code de la CCFAP 2014` with and without U+00A0.
   Normalisable.
2. **Genuinely different wording for the same field.** `Thème` / `Objet`,
   `Source des données` / `Source de données`, `régime fiscal` / `système
   fiscal`, `Autres programmes pertinents du gouvernement` / `Autres programmes
   gouvernementaux pertinents`, `Code de la CCFAP 2014` / `Code CCOFOG 2014`
   (the English acronym, in the French edition). A mapping table, not a
   normalisation.
3. **An outright error.** Two French measures label the *Tax* field
   **`Direction de la politique de l'impôt`** - "Tax Policy Branch". That is not
   a field name at all.

**The saving structure: every variant sits at a fixed row position.** Checked
directly - each label, however spelled, appears only at its own slot (0-16) and
never at another. So the parser can key on position, with the label recorded and
variants mapped, and must **not** key on label text alone. Keying on the French
label strings would silently lose seven measures' `Source of data`, two
measures' `Subject`, and both mislabelled `Tax` fields.

### Cost tables

A measure has **zero, one or two** cost tables following it. On Part 6: 13
measures with none, 36 with one, **3 with two** (the donations-of-cultural-
property, ecologically-sensitive-land and publicly-listed-securities measures,
which split personal from trust donations). 13 + 36 + 6 = 42, which matches the
table count.

Measures with no cost table are the "no estimate available" cases. One of them
is *Deferral for asset transfers to a corporation and corporate reorganizations*
- the fixture named in CLAUDE.md acceptance test 4, which independently confirms
both the fixture and the reading.

Header is a single row: an empty corner cell, then eight year columns
`2020 2021 2022 2023 2024 (P) 2025 (P) 2026 (P) 2027 (P)`. **`(P)` marks a
projection**, which is where `value_kind` 'projection' comes from - it is in the
column header, not inferred from the year.

Row labels vary widely between measures - 31 distinct labels on Part 4 alone,
from `Personal income tax` and `Total` to
`Quarterly payments for families with young children entitled to the Canada
Child Benefit (2021) – Children's Benefits`. The row label is data, not a fixed
schema, and belongs in a column.

### Cost cell tokens, with the published legend

The symbols are **documented by Finance**, in the metadata CSV on
open.canada.ca. This is an authority, not our inference:

| EN | FR | Meaning, verbatim from the metadata |
|---|---|---|
| `n.a.` | `n.d.` | "No data available to support a meaningful estimate or projection" |
| `–` | `–` | "Tax expenditure not in effect" |
| `X` | `X` | "Not published for confidentiality reasons" |
| `S` | `F` | Under $500,000. NOTE 3: "Amounts under $500,000 are reported as "S" ("small")…" |

Tokens actually observed in the HTML cells, beyond numbers:

- `–` U+2013 en dash, and **`-` U+002D hyphen as well** - two different
  characters, both present, on parts 4 and 7. Do not assume one dash.
- `n.a.` (EN) / `n.d.` (FR), **and `n.d` without the final period** - 16
  occurrences on Part 4 French.
- `X`, `S` (EN) / `F` (FR)
- **empty cells**, in quantity.

`X` and the bare `-` were not anticipated in CLAUDE.md's list, and neither was
the empty cell. All of them must be classified in `data/cost_tokens.csv` before
a build passes.

**Number formatting differs by language and by medium.** The English HTML uses
`1,770`; the French HTML uses `5 515` with a non-breaking space as the thousands
separator; the French CSV uses `5,515`. Three formats for the same number.

### Encoding

The open data CSVs are **Windows-1252, with CRLF line endings**, not UTF-8 -
`file` reports "Non-ISO extended-ASCII text", and the en dash arrives as a
replacement character if read as UTF-8. They must be decoded as cp1252.

### Open questions for step 3

1. **Does the legal reference field ever cite something other than the ITA and
   the Regulations?** Not yet examined field-by-field; it decides how much the
   grammar has to cover.
2. **What is the `Objective – category` field** as distinct from `Objective` and
   `Category`? All three exist; CLAUDE.md anticipated two.
3. **Does the appendix table belong in the data at all?** It is not a measure.
   Current reading: exclude it, and say so.
