# Portage (working title)

A bilingual, open dataset that makes Canada's federal **Income Tax Act**
(RSC 1985, c 1 (5th Supp)) and the **Income Tax Regulations** (CRC, c 945)
navigable at the subsection level.

> This dataset makes provisions navigable. It does not interpret them and is
> not legal advice.

## Status

**Phase 0, session 1: setup and source inspection.** No data has been built
yet. There is no `portage.sqlite` in this repository.

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

**Data:** the Income Tax Act and Income Tax Regulations are reproduced under the
Department of Justice Canada
[Terms and Conditions](https://www.justice.gc.ca/eng/terms-avis/index.html),
which provide that anyone may reproduce enactments and consolidations of
enactments of the Government of Canada without charge or request for permission,
provided due diligence is exercised in ensuring accuracy and the reproduction is
not represented as an official version. The full terms are quoted verbatim in
`docs/source-notes.md`.

Accordingly:

- This is an **unofficial** reproduction. It is **not** an official version of
  the Income Tax Act or the Income Tax Regulations.
- It has **not** been produced in affiliation with, or with the endorsement of,
  the Government of Canada.
- The underlying works are the *Income Tax Act* (RSC 1985, c 1 (5th Supp)) and
  the *Income Tax Regulations* (CRC, c 945), published by the Department of
  Justice Canada.
- For the official consolidation, see <https://laws-lois.justice.gc.ca>.

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
