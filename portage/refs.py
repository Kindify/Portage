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
    """Term -> [(citation_path, 'definition_record')] for one instrument.

    `<Definition>` records only, matched on `defined_term_en` / `defined_term_fr`
    after the same normalisation that builds definition citation paths, so the
    two sides cannot drift apart. A record counts in a language only if it
    carries text in that language, so a definition split into `X` and `X~fr` is
    one candidate per language rather than two.
    """
    term_col = "defined_term_%s" % lang
    text_col = "text_%s" % lang
    index = defaultdict(list)
    for rec in records:
        if rec["level"] != "definition" or not rec.get(text_col):
            continue
        term = normalise_term(rec.get(term_col))
        if term:
            index[term].append((rec["citation_path"], "definition_record"))
    return index


def inline_term_index(walker, lang):
    """Term -> [(citation_path, 'inline_defined_term')] for one instrument.

    The source defines terms in two structural forms. The second is a
    `<DefinedTermEn>` / `<DefinedTermFr>` marked up inside a provision's own
    `<Text>`, with no `<Definition>` wrapper - 964 of them in the English Act,
    431 in the English Regulations. ITA 10.1(5) is one: "an *eligible
    derivative*, of a taxpayer for a taxation year, **means** a swap
    agreement...". It defines the term as plainly as any wrapped definition.

    **These are found by element nesting, not by prose.** An inline site is a
    DefinedTerm element with no `<Definition>` ancestor. Nothing here looks for
    the word "means" or any other wording, so the ban on text heuristics is not
    touched.
    """
    tag = "DefinedTermEn" if lang == "en" else "DefinedTermFr"
    index = defaultdict(list)
    seen = set()
    for el in walker.body.iter(tag):
        if any(a.tag == "Definition" for a in el.iterancestors()):
            continue
        term = normalise_term(el.text)
        if not term:
            continue
        owner = _owner(el, walker.owner_of)
        if owner is None or (term, owner) in seen:
            continue
        seen.add((term, owner))
        index[term].append((owner, "inline_defined_term"))
    return index


def candidate_index(walker, section_records, lang):
    """Every definition site in one instrument, both structural forms."""
    index = defaultdict(list)
    for source in (definition_index(section_records, lang),
                   inline_term_index(walker, lang)):
        for term, sites in source.items():
            index[term].extend(sites)
    return index


def extract(walker, act, lang, same_index, other_index=None, other_act=None):
    """Tagged cross-references for one instrument in one language.

    Implements docs/reference-rule.md. `same_index` holds definition sites in
    this instrument and is what decides `resolution`. `other_index` holds sites
    in the *other* instrument: those are recorded as candidates so a reader can
    see them, but they never change the resolution, because which instrument's
    definition governs is a legal question this tool does not answer.
    """
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
            "candidates": [],
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
            # techniques" is not section 51 of this Act. A bare section number
            # with no instrument qualifier never resolves.
            row["unresolved_reason"] = (
                "bare section number with no instrument qualifier - the target "
                "instrument is named in prose, not in the markup")

        else:
            # Rule section 1. Exact match after the shared normalisation.
            term = normalise_term(raw)
            same = sorted(same_index.get(term, [])) if term else []
            other = sorted(other_index.get(term, [])) if (term and other_index) else []
            row["candidates"] = (
                [(p, k, act, "same_instrument") for p, k in same]
                + [(p, k, other_act, "other_instrument") for p, k in other])

            # Resolution is computed over same-instrument candidates only.
            if len(same) == 1:
                row["resolution"] = "unique"
                row["to_citation_path"] = same[0][0]
                row["target_act"] = act
            elif len(same) > 1:
                row["resolution"] = "ambiguous"
                row["target_act"] = act
                row["unresolved_reason"] = (
                    "defined in %d places in %s - which one governs here is a "
                    "scope question this tool does not answer" % (len(same), act))
            elif other:
                row["unresolved_reason"] = (
                    "not defined in %s; %d definition(s) of this term in %s are "
                    "recorded as candidates, but which instrument governs is a "
                    "legal question this tool does not answer"
                    % (act, len(other), other_act))
            else:
                row["unresolved_reason"] = "no definition of this term in %s" % act

        rows.append(row)

    return rows
