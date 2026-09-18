# Portage (working title)

A bilingual, open dataset that makes Canada's federal **Income Tax Act**
(RSC 1985, c 1 (5th Supp)) and the **Income Tax Regulations** (CRC, c 945)
navigable at the subsection level.

> This dataset makes provisions navigable. It does not interpret them and is
> not legal advice.

## Status

**Phase 0, session 2.** The parser works on the **English Income Tax Act**.
`python -m portage.build` produces `portage.sqlite` - 36,277 rows, 31,501
addressable provisions, 763 sections - and the test suite passes, including a
byte-exact round trip against the source with no normalisation applied.

Not yet done: French text, the Income Tax Regulations, and the
`cross_references` table. See `PLAN.md`.

## What this is

One SQLite file with one row per addressable unit of the two instruments -
section, subsection, paragraph, subparagraph, clause - each carrying:

- its full citation path (for example `110.6(2.1)(a)(ii)`)
- the English and French text exactly as published
- the heading, if the source gives one
- the history note (amending-statute reference), if the source gives one
- the source URL and the snapshot date it was taken from

Plus a table of cross-references between provisions, full-text search indexes
over the English and French text, and a `meta` table recording exactly which
source and snapshot the file was built from.

## What this is not

- It is not an interpretation of the Act. It reproduces text and structure.
- It is not legal or tax advice, and it makes no recommendations.
- It is not a consolidation service. It is a snapshot, dated in `meta`.
- It is not authoritative. For anything that matters, check the official
  consolidation at <https://laws-lois.justice.gc.ca>.

## Source

**Justice Laws Website, Department of Justice Canada** - the official XML
consolidations. Chosen over the A2AJ dataset because A2AJ's records stop at the
section level; the reasoning is in `docs/source-notes.md` and `docs/decisions.md`.

| Instrument | Language | URL |
|---|---|---|
| Income Tax Act, RSC 1985, c 1 (5th Supp) | EN | <https://laws-lois.justice.gc.ca/eng/XML/I-3.3.xml> |
| Income Tax Act | FR | <https://laws-lois.justice.gc.ca/fra/XML/I-3.3.xml> |
| Income Tax Regulations, CRC c 945 | EN | <https://laws-lois.justice.gc.ca/eng/XML/C.R.C.,_c._945.xml> |
| Income Tax Regulations | FR | <https://laws-lois.justice.gc.ca/fra/XML/C.R.C.,_ch._945.xml> |

**Consolidation date: 2026-06-18** (`lims:pit-date`, as stamped in the source
files themselves). Every build writes the source URLs and this date into the
`meta` table, and every record carries its own `source_url` and `snapshot_date`.

## Licence

**Code:** MIT. See `LICENSE`.

**Project status: non-commercial.** This dataset is published for public-interest
and non-commercial use.

### Justice Canada reproduction terms

The Income Tax Act and Income Tax Regulations are reproduced under the Department
of Justice Canada [Terms and Conditions](https://www.justice.gc.ca/eng/terms-avis/index.html).
The governing clause for enactments, quoted in full:

> Anyone may, without charge or request for permission, reproduce enactments and
> consolidations of enactments of the Government of Canada, and decisions and
> reasons for decisions of federally constituted courts and administrative
> tribunals, provided due diligence is exercised in ensuring the accuracy of the
> materials reproduced and the reproduction is not represented as an official
> version.

The non-commercial reproduction clause, which requires reproductions to state:

> the reproduction is a copy of an official work that is published by the
> Government of Canada and that the reproduction has not been produced in
> affiliation with, or with the endorsement of the Government of Canada

and the commercial clause:

> Reproduction of multiple copies of materials on this site, in whole or in part,
> for the purposes of commercial redistribution is prohibited except with written
> permission from the Department of Justice Canada.

### Open Government Licence - Canada

The source data is published under the
[Open Government Licence - Canada](https://open.canada.ca/en/open-government-licence-canada).
Under it you are free to:

> Copy, modify, publish, translate, adapt, distribute or otherwise use the
> Information in any medium, mode or format for any lawful purpose.

subject to the attribution condition:

> Acknowledge the source of the Information by including any attribution
> statement specified by the Information Provider(s) and, where possible, provide
> a link to this licence.

and the no-warranty clause:

> The Information is licensed "as is", and the Information Provider excludes all
> representations, warranties, obligations, and liabilities, whether express or
> implied, to the maximum extent permitted by law.

**Contains information licensed under the Open Government Licence – Canada.**

### Our statements under those terms

- This is an **unofficial** reproduction. It is **not** an official version of
  the *Income Tax Act* or the *Income Tax Regulations*.
- It has **not** been produced in affiliation with, or with the endorsement of,
  the Government of Canada.
- The works reproduced are the *Income Tax Act* (RSC 1985, c 1 (5th Supp)) and
  the *Income Tax Regulations* (CRC, c 945), published by the Department of
  Justice Canada.
- Due diligence on accuracy is exercised through the acceptance tests described
  in `CLAUDE.md`, which must pass before any build is published.
- For the official consolidation, see <https://laws-lois.justice.gc.ca>.

**Open legal question, not a blocker.** Justice Canada's standing permission to
reproduce enactments is not conditioned on non-commercial use, while a separate
clause restricts commercial redistribution of site materials generally. How those
interact for a downstream *commercial* user of this dataset has not been
determined and is not something this project takes a position on. The project
itself is non-commercial. Both clauses are quoted above and in
`docs/source-notes.md` so anyone can read them directly.

## Known limits

- **Cross-references are incomplete in Phase 0 by design.** The source XML tags
  references to other statutes (`XRefExternal`) and to defined terms
  (`DefinitionRef`), but contains no markup at all for references from one
  provision to another inside the same instrument. Phase 0 ships only the tagged
  references, each marked `method = 'tagged'`. Internal references
  ("Notwithstanding subsections 152(4) to (5)") are **not present** and are
  deferred to Phase 1 as a separate table. Do not read the `cross_references`
  table as a complete reference graph.
- **About 3.3% of records have text in only one language.** English and French
  genuinely structure some provisions differently - English section 51(1) has
  eight lettered paragraphs where French has six, with offset contents. Those
  records carry `bilingual_gap = 1` and a NULL on one side. This reflects the
  law as published; alignment is never forced. See `docs/source-notes.md`.
- **This is a dated snapshot, not a consolidation service.** `meta` records
  `consolidation_date` and `retrieved_date` separately.

## Setup

The project pins Python 3.12 and uses [uv](https://docs.astral.sh/uv/) to manage
both the interpreter and the dependencies. uv installs its own copy of Python,
so the system Python that ships with macOS is never touched.

From a clean checkout, on macOS or Linux:

```sh
# 1. Install uv (once per machine)
curl -LsSf https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"          # or restart your shell

# 2. Install the pinned Python and create the virtual environment
uv python install 3.12
uv venv --python 3.12

# 3. Install the dependencies into it
uv pip install -r requirements.txt
```

That creates `.venv/` in the project directory. It is gitignored - everyone
builds their own. To use it:

```sh
source .venv/bin/activate
python -m portage.build
pytest
```

Or without activating, prefix commands with `uv run`, e.g. `uv run pytest`.

## Build

```
pip install -r requirements.txt
python -m portage.build
pytest
```

(Not wired up yet - see `PLAN.md`.)
