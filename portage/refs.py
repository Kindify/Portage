"""Tagged cross-references.

Phase 1, step 1. Only references the source marks up as elements are collected
here - `XRefExternal` (a reference to another instrument), `DefinitionRef` (a
reference to a defined term), and `XRefInternal`, of which the whole corpus
contains exactly one. Every row carries `method = 'tagged'`.

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

#: The elements the source marks up as references.
TAGGED = ("XRefExternal", "DefinitionRef", "XRefInternal")

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


def definition_index(records, lang):
    """Defined term -> the definition records that define it, in one language.

    Implements docs/reference-rule.md section 1. Candidates are `<Definition>`
    records only, matched on `defined_term_en` / `defined_term_fr` after the
    same normalisation that builds definition citation paths, so the two sides
    cannot drift apart.

    A record counts in a language only if it carries text in that language: a
    definition split into `X` and `X~fr` is one candidate per language, not two.

    Known gap, stated in the rule: terms defined inline - `<DefinedTermEn>` in a
    provision's own `<Text>` with no `<Definition>` wrapper, 962 of them in the
    English Act - are not candidates. Around 150 references whose term really is
    defined somewhere come out unresolved because of it.
    """
    term_col = "defined_term_%s" % lang
    text_col = "text_%s" % lang
    index = defaultdict(list)
    for rec in records:
        if rec["level"] != "definition":
            continue
        if not rec.get(text_col):
            continue
        term = normalise_term(rec.get(term_col))
        if term:
            index[term].append(rec["citation_path"])
    return index


def extract(xml_path, act, lang, source_url, section_records):
    """Tagged cross-references for one instrument in one language.

    Implements docs/reference-rule.md. Returns a list of dicts; each carries a
    `resolution` of 'unique', 'ambiguous' or 'unresolved', and `candidate_paths`
    listing every definition that matched. Nothing is ever chosen from among
    several candidates - see the rule's governing principle.
    """
    walker, _meta = parse_walker(xml_path, act, source_url)
    index = definition_index(section_records, lang)

    # Walk the body once in document order. Iterating per owned element would
    # count a reference once for every owned ancestor it has, which inflated an
    # early run from 2,224 elements to 7,755 rows.
    found = [el for el in walker.body.iter()
             if isinstance(el.tag, str) and el.tag in TAGGED]

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
            "resolution": "unresolved",
            "candidate_paths": [],
            "unresolved_reason": "",
            "order_index": order,
        }

        if tag == "XRefExternal":
            # Rule section 2. Resolve only if the target is an instrument we
            # hold AND the reference names a provision. The element's text is
            # always an instrument title, so the second condition is never met
            # in this source and every row stays unresolved.
            link = ref.get("link")
            row["target_act"] = INSTRUMENTS.get(link) if link else None
            if not link:
                row["unresolved_reason"] = (
                    "no link attribute - the source names the instrument in "
                    "text only")
            elif row["target_act"] is None:
                row["unresolved_reason"] = (
                    "refers to an instrument this dataset does not hold")
            else:
                row["unresolved_reason"] = "names an instrument, not a provision"

        elif tag == "XRefInternal":
            # Rule section 3. Exactly one exists, in the French Act, and its
            # target instrument is named in prose rather than in the markup:
            # "l'article 51 de la Loi de 2012 apportant des modifications
            # techniques" is not section 51 of this Act. Resolving a bare
            # section number here would produce a confidently wrong link.
            row["unresolved_reason"] = (
                "bare section number whose target instrument is named in "
                "prose, not in the markup")

        else:
            # Rule section 1. Exact match after the shared normalisation,
            # against definitions in the same instrument and language.
            term = normalise_term(raw)
            matches = sorted(index.get(term, [])) if term else []
            row["candidate_paths"] = matches
            if len(matches) == 1:
                row["resolution"] = "unique"
                row["to_citation_path"] = matches[0]
                row["target_act"] = act
            elif len(matches) > 1:
                row["resolution"] = "ambiguous"
                row["target_act"] = act
                row["unresolved_reason"] = (
                    "defined in %d places in %s - which one governs here is a "
                    "scope question this tool does not answer"
                    % (len(matches), act))
            else:
                row["unresolved_reason"] = "no definition of this term in %s" % act

        rows.append(row)

    return rows
