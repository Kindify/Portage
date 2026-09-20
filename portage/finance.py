"""Parse the Report on Federal Tax Expenditures from the committed snapshot.

Reads only `data/finance/2026/`. It never fetches canada.ca - see
docs/decisions.md, 2026-09-19.

Structural rules, all established by inspection in docs/source-notes.md
section 7 and none of them inferred from prose:

- A measure is a table whose caption id is linked from the Part 3 index. The
  "caption has an id" test is not enough: the Part 7 appendix has a caption id
  in French, with 17 body rows, and would pass every shape test.
- Fields are keyed by **row position**, not by label. The French labels vary 25
  ways for 17 fields, including two measures that label the Tax field
  "Direction de la politique de l'impôt". Every variant sits at a fixed slot,
  so position is the key and the label is catalogued.
- Cost tables are the tables captioned "Cost Information" / "Renseignements sur
  les coûts" that follow a measure, and a measure may have zero, one or two.
"""

import pathlib
import re
import unicodedata

from lxml import html as LH

ROOT = pathlib.Path(__file__).resolve().parent.parent
SNAPSHOT = ROOT / "data" / "finance" / "2026"
REPORT_YEAR = 2026

PAGES = {
    ("en", n): ("part-%d-en.html" % n,
                "https://www.canada.ca/en/department-finance/services/"
                "publications/federal-tax-expenditures/2026/part-%d.html" % n)
    for n in range(3, 8)
}
PAGES.update({
    ("fr", n): ("partie-%d-fr.html" % n,
                "https://www.canada.ca/fr/ministere-finances/services/"
                "publications/depenses-fiscales/2026/partie-%d.html" % n)
    for n in range(3, 8)
})

#: The 17 fields, in the fixed order they appear in every measure table.
#: Position is the key; see the module docstring.
FIELD_SLOTS = [
    "description",
    "tax",
    "beneficiaries",
    "type_of_measure",
    "legal_reference",
    "implementation_and_recent_history",
    "objective_category",
    "objective",
    "category",
    "reason_not_benchmark",
    "subject",
    "ccofog_2014_code",
    "other_relevant_government_programs",
    "source_of_data",
    "estimation_method",
    "projection_method",
    "number_of_beneficiaries",
]

COST_CAPTION = re.compile(r"^(Cost Information|Renseignements sur les co)", re.I)

#: Cost cell tokens. The first four meanings are Finance's own, quoted from the
#: metadata CSV published with the open data release; `small` is NOTE 3 in the
#: same file. `empty` and the two undocumented variants are ours, and are marked
#: as such in data/cost_tokens.csv.
COST_TOKENS = {
    "n.a.": "not_available",
    "n.d.": "not_available",
    "n.d": "not_available",          # undocumented: missing final period
    "–": "not_in_effect",        # en dash, the published symbol
    "-": "not_in_effect",             # undocumented: hyphen-minus used instead
    "X": "withheld_confidential",
    "S": "small",
    "F": "small",
    "": "empty",
}

#: Column-header markers meaning the figure is a projection, not an estimate.
#: English publishes "(P)", French "(proj.)" - checked, not assumed.
PROJECTION_MARKERS = ("(P)", "(proj.)")

#: Characters used as thousands separators: comma, space, non-breaking space,
#: narrow non-breaking space. The same number is published as "1,770" in the
#: English pages and "5 515" in the French.
_SEPARATORS = ",   "


def text_of(el):
    """Visible text, whitespace collapsed, non-breaking spaces preserved as spaces."""
    s = "".join(el.itertext())
    s = s.replace(" ", " ").replace(" ", " ")
    return " ".join(s.split())


def normalise_label(s):
    """A field label for cataloguing: NFC, non-breaking spaces folded, trimmed."""
    s = unicodedata.normalize("NFC", s or "")
    s = s.replace(" ", " ").replace(" ", " ")
    return " ".join(s.split())


def parse_amount(raw):
    """A published cost cell -> (value_millions, value_kind).

    Returns (None, kind) for every non-numeric token. No token is ever stored
    as zero - "not in effect", "withheld" and "small" are not zero, and a build
    that flattened them to 0 would read as a costed measure.
    """
    token = raw.strip()
    if token in COST_TOKENS:
        return None, COST_TOKENS[token]
    cleaned = token
    for ch in _SEPARATORS:
        cleaned = cleaned.replace(ch, "")
    # Hyphen-minus is the published sign on a negative amount; 194 cells use it.
    if re.fullmatch(r"-?\d+(\.\d+)?", cleaned):
        return float(cleaned), None
    return None, "unclassified"


def _index_ids(lang):
    """Measure ids linked from the Part 3 index, per part.

    This is what defines a measure. Returns {part: [id, ...]} in index order.
    """
    name, _url = PAGES[(lang, 3)]
    doc = LH.fromstring((SNAPSHOT / name).read_bytes())
    pattern = re.compile(
        r"part-(\d)\.html#(.+)$" if lang == "en" else r"partie-(\d)\.html#(.+)$")
    out = {}
    for a in doc.xpath("//main//a[@href]"):
        m = pattern.search(a.get("href") or "")
        if not m:
            continue
        part, slug = int(m.group(1)), m.group(2)
        out.setdefault(part, [])
        if slug not in out[part]:
            out[part].append(slug)
    return out


def parse_page(lang, part, wanted_ids):
    """Measures and their cost tables from one page, in document order."""
    name, url = PAGES[(lang, part)]
    doc = LH.fromstring((SNAPSHOT / name).read_bytes())
    wanted = set(wanted_ids)

    measures, current = [], None
    for table in doc.xpath("//main//table"):
        caption = table.xpath("./caption")
        if not caption:
            continue
        caption = caption[0]
        slug = caption.get("id")

        if slug and slug in wanted:
            rows = table.xpath("./tbody/tr")
            fields, labels = {}, []
            for i, row in enumerate(rows):
                th = row.xpath("./th")
                td = row.xpath("./td")
                if not th or i >= len(FIELD_SLOTS):
                    continue
                label = normalise_label(text_of(th[0]))
                labels.append((i, label))
                fields[FIELD_SLOTS[i]] = text_of(td[0]) if td else None
            current = {
                "slug": slug, "lang": lang, "part": part, "source_url": url,
                "name": normalise_label(text_of(caption)),
                "fields": fields, "labels": labels, "n_rows": len(rows),
                "costs": [],
            }
            measures.append(current)
            continue

        if current is not None and COST_CAPTION.match(text_of(caption)):
            headers = [text_of(th) for th in table.xpath("./thead/tr/th")]
            for row in table.xpath("./tbody/tr"):
                cells = row.xpath("./th|./td")
                if not cells:
                    continue
                label = text_of(cells[0])
                for col, cell in enumerate(cells[1:], start=1):
                    if col >= len(headers):
                        continue
                    header = headers[col]
                    year = re.match(r"(\d{4})", header)
                    if not year:
                        continue
                    raw = text_of(cell)
                    value, kind = parse_amount(raw)
                    if kind is None:
                        kind = ("projection"
                                if any(m in header for m in PROJECTION_MARKERS)
                                else "estimate")
                    current["costs"].append({
                        "row_label": label, "year": int(year.group(1)),
                        "raw_value": raw, "value_millions": value,
                        "value_kind": kind, "year_header": header,
                    })
    return measures


def parse_all():
    """Every measure in both languages, from the snapshot."""
    out = {}
    for lang in ("en", "fr"):
        ids = _index_ids(lang)
        rows = []
        for part in (4, 5, 6, 7):
            rows.extend(parse_page(lang, part, ids.get(part, [])))
        out[lang] = rows
    return out
