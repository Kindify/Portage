"""Tagged cross-references.

Phase 1, step 1. Only references the source marks up as elements are collected
here - `XRefExternal` (a reference to another instrument) and `DefinitionRef`
(a reference to a defined term). Every row carries `method = 'tagged'`.

References from one provision to another inside the same instrument are *not*
here, because the source does not tag them. `XRefInternal` exists in the schema
but the English Act and Regulations contain none at all, and the French Act
contains exactly one. Provision-to-provision references live in prose
("Notwithstanding subsections 152(4) to (5)") and are a separate, later job with
its own extraction method and its own validation.

Nothing in this module reads body text to decide anything. A reference is found
because the source tagged it, and attributed to a provision because the parser
recorded which element produced which record.
"""

from collections import defaultdict

from .labels import normalise_term
from .parse import parse_walker

#: Elements the source marks up as references.
TAGGED = ("XRefExternal", "DefinitionRef")

#: Justice Laws chapter identifiers for the instruments we hold.
INSTRUMENTS = {"I-3.3": "ITA", "C.R.C.,_c._945": "ITR", "C.R.C.,_ch._945": "ITR"}


def _text(el):
    return " ".join("".join(el.itertext()).split())


def _owner(el, owner_of):
    """The citation path of the provision this reference sits in.

    Walks up to the nearest element that produced a record. Returns None only
    if the reference sits outside the Body, which does not occur in practice
    but is not assumed.
    """
    for ancestor in el.iterancestors():
        path = owner_of.get(id(ancestor))
        if path is not None:
            return path
    return None


def definition_index(walker, lang):
    """Defined term -> the citation paths that define it, within one instrument.

    Two structural forms count as a definition site, because the source uses
    both:

    1. A `<Definition>` element - 2,191 of them in the English Act.
    2. A `<DefinedTermEn>` / `<DefinedTermFr>` marked up inline in a
       provision's own `<Text>`, with no `<Definition>` wrapper - a further 962
       in the English Act. ITA 10.1(5) is one: "an *eligible derivative*, of a
       taxpayer for a taxation year, **means** a swap agreement...". It defines
       the term as plainly as any `<Definition>` does; it is simply not wrapped.

    Indexing only the first form would leave 148 references looking as though
    nothing in the Act defines them, which is false. Including the second form
    lowers the share of references that resolve to exactly one place, because
    more real candidates means more genuine ambiguity. That is the honest
    direction: the index describes where terms are defined, not what makes the
    number look good.

    A term can be defined many times - "investment tax credit" is referenced 21
    times and defined in several places - so this maps to a list and the caller
    decides. Taking the first would be a guess dressed as a result.
    """
    tag = "DefinedTermEn" if lang == "en" else "DefinedTermFr"
    index = defaultdict(list)
    seen = set()
    for el in walker.body.iter(tag):
        term = normalise_term(el.text)
        if not term:
            continue
        owner = _owner(el, walker.owner_of)
        if owner is None:
            continue
        if (term, owner) in seen:
            continue
        seen.add((term, owner))
        index[term].append(owner)
    return index


def extract(xml_path, act, lang, source_url):
    """Tagged cross-references for one instrument in one language.

    Returns a list of dicts. Resolution is attempted only for DefinitionRef,
    and only where the term matches exactly one definition in the same
    instrument. Everything else is returned unresolved with a stated reason -
    never dropped, never guessed.
    """
    walker, _meta = parse_walker(xml_path, act, source_url)
    index = definition_index(walker, lang)

    # Walk the body once in document order. Iterating per owned element would
    # count a reference once for every owned ancestor it has, which inflated an
    # early run from 2,224 elements to 7,755 rows.
    found = []
    for el in walker.body.iter():
        if isinstance(el.tag, str) and el.tag in TAGGED:
            found.append(el)

    rows = []
    order = 0
    for ref in found:
        tag = ref.tag
        # Attribute to the nearest record, so a reference inside a nested
        # provision is not credited to its grandparent.
        owner = _owner(ref, walker.owner_of)
        if owner is None:
            continue
        order += 1
        raw = _text(ref)
        row = {
            "act": act,
            "lang": lang,
            "from_citation_path": owner,
            "ref_kind": tag,
            "raw_text": raw,
            "reference_type": ref.get("reference-type"),
            "target_link": ref.get("link"),
            "target_act": None,
            "to_citation_path": None,
            "resolved": 0,
            "unresolved_reason": "",
            "order_index": order,
        }

        if tag == "XRefExternal":
            link = ref.get("link")
            row["target_act"] = INSTRUMENTS.get(link) if link else None
            if not link:
                row["unresolved_reason"] = (
                    "no link attribute - the source names the instrument "
                    "in text only")
            elif row["target_act"] is None:
                row["unresolved_reason"] = (
                    "refers to an instrument this dataset does not hold")
            else:
                # A reference to the instrument as a whole. There is no
                # provision to point at, and inventing one would be a
                # guess.
                row["unresolved_reason"] = (
                    "names an instrument, not a provision")
        else:
            term = normalise_term(raw)
            matches = index.get(term, []) if term else []
            if len(matches) == 1:
                row["to_citation_path"] = matches[0]
                row["resolved"] = 1
                row["target_act"] = act
            elif len(matches) > 1:
                row["unresolved_reason"] = (
                    "ambiguous - %d definitions of this term in %s"
                    % (len(matches), act))
            else:
                row["unresolved_reason"] = (
                    "no definition of this term in %s" % act)
        rows.append(row)

    rows.sort(key=lambda r: r["order_index"])
    return rows
