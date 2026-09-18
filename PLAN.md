# Plan

## Where things stand

**Phase 0, session 3 (2026-09-18): the Income Tax Act is built in both
languages.** 29 tests pass. Both round trips reproduce their source files
character-for-character with no normalisation.

Still to come: the Income Tax Regulations, and the `cross_references` table.

---

## Done in session 3

**Definitions re-keyed by defined term.** The ordinal could not be a bilingual
key: each file alphabetises definitions in its own language, so `248(1)~d1` is
"absorbed capacity" in English and "tax shelter" in French. Now
`248(1)"active business"`, with French-term and ordinal fallbacks catalogued.

**French parsed and joined.** Same walker, no language-specific code beyond the
label rule. Both round trips exact.

**`alignment_unverified` added** - see the open question below, which is the
main thing I need from you.

| | |
|---|---|
| rows | 36,778 |
| addressable | 31,766 |
| rows with both languages | 34,296 |
| **verified bilingual pairs** | **31,888** |
| `alignment_unverified` | 2,408 |
| `bilingual_gap` | 2,482 |
| label anomalies | 55 |
| definition key fallbacks | 140 |
| round trip EN / FR | **exact, zero normalisation** |

Four catalogues are written by the build and diffed against committed fixtures:
`label_anomalies.csv`, `definition_key_fallbacks.csv`, `bilingual_gaps.csv`,
`alignment_unverified.csv`.

---

## The open question - `alignment_unverified`

**You asked me to confirm the 51(1) case lands as gaps rather than misaligned
pairs. It did not.** Joining on `citation_path` produced four *paired* rows for
51(1)(a) to (d), and they are not translations of each other:

```
51(1)(a)  EN  "a capital property of the taxpayer that is another share..."
          FR  "sauf pour l'application des paragraphes 20(21) et 44.1(6)..."
```

English breaks the opening conditions into lettered paragraphs; French leaves
them in the subsection text and letters only the rules. Same label, different
provision. The gaps - (d.1), (d.2), (e), (f) against b.1), b.2) - came out right;
the joined four were silently wrong.

I have marked them rather than decided for you. Where a parent's set of children
differs between the files, the children sharing a path keep one row but carry
`alignment_unverified = 1`. That asserts nothing; it records that we do not know.
It is a structural test - it compares child label sets and makes no judgment
about the texts.

**What I need from you.** Three options:

- **(a) Keep the flag, as built.** One row per path, both texts present, the
  uncertainty visible and filterable. Nothing is asserted and nothing is lost.
  Risk: a consumer who ignores the flag sees a wrong pair.
- **(b) Split them into single-language rows**, like gaps. Safest reading of
  "never force alignment" - we stop putting the two texts on one row at all.
  Cost: ~2,400 rows become two rows each, and the many cases where the pairing
  is in fact correct lose their join.
- **(c) Keep the flag for fragments, split the addressable ones.** The 333
  addressable rows are the ones a person would actually cite and be misled by;
  the ~2,075 fragment rows are non-citable continued text where the risk is
  lower.

I lean to **(c)**, because the harm is concentrated in the rows someone can cite,
and 51(1)(a) returning two unrelated texts on one row is the specific failure
mode you have been guarding against all along. But **(a)** is defensible if you
would rather keep the data shape simple and rely on the flag.

---

## Session 4 - scope

1. Settle `alignment_unverified` (above), and apply it.
2. The Income Tax Regulations, both languages. The parser should need no
   changes - the root element is `<Regulation>` rather than `<Statute>`, which
   `parse()` already handles. Expect new label shapes and a fresh anomaly
   catalogue.
3. The tagged `cross_references` table: `XRefExternal` (1,112 in the Act) and
   `DefinitionRef` (1,158), every row `method = 'tagged'`. Internal references
   stay deferred to Phase 1.

---

## Open questions for Matt

**1. `alignment_unverified` - see above.** The one that matters.

**2. Fragments join by ordinal across languages.** `2(3)~c1` in English is paired
with `2(3)~c1` in French purely by position within the provision. That is the
same positional-key reasoning I rejected for definitions. It is less dangerous -
fragments are not citable and each language round-trips in its own order - but it
is the same species of assumption. Where the counts differ the rows are now
flagged; where the counts match they are paired on trust. Worth a decision.

**3. "Listed Corporations" schedule still not captured.** Part of the Act,
contains no `Section` elements, so nothing in the current model holds it.

**4. `history_note` is section-level only.** 762 notes against 763 sections.
Stated in README under Known limits.

---

## Carried forward

- **Commercial redistribution** remains an open legal question. Not a blocker.
- **`tests/spot_checks.md`** needs a pass by hand against the Justice Laws site.
  Twenty rows, seeded so they stay stable between builds.

---

## Not in Phase 0

Embeddings, a web front end, an MCP server, the Finance Canada tax expenditure
linkage, indicator publishing. Later phases.
