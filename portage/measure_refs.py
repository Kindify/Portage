"""Extract legal references from a measure's `Legal reference` field.

Implements docs/reference-rule.md Part 2, which was written first. Every row
produced here carries `method = 'pattern'`, so it can never be mistaken for the
tagged references of Part 1.

Pattern extraction is allowed here because failure is visible: a reference
either resolves to a citation_path that exists or it does not, and the
unresolved list is published.
"""

import re

#: Instrument names as the report writes them, longest first so that
#: "Income Tax Regulations" is matched before "Income Tax Act" can claim it.
INSTRUMENTS = [
    ("Income Tax Regulations", "ITR"),
    ("Règlement de l'impôt sur le revenu", "ITR"),
    ("Income Tax Application Rules", "ITAR"),
    ("Income Tax Act", "ITA"),
    ("Loi de l'impôt sur le revenu", "ITA"),
    ("Excise Tax Act", "ETA"),
    ("Loi sur la taxe d'accise", "ETA"),
    ("Employment Insurance Act", "EI"),
    ("Canada Pension Plan", "CPP"),
]

#: Only these two are held by this dataset and can resolve to a citation_path.
RESOLVABLE = {"ITA", "ITR"}

#: "Not yet legislated as of ..." states that no provision exists. It is not an
#: unresolved reference, and counting it as one would overstate the failure rate.
NO_PROVISION = re.compile(
    r"^\s*(Not yet legislated|Aucune disposition|Pas encore)", re.I)

#: A section number. The trailing letter must not be the first letter of the
#: next word: an earlier version read "section 146.1Canada Education Savings
#: Act" as the provision "146.1C".
_SECTION = r"\d+(?:\.\d+)*(?:[A-Za-z](?![A-Za-z]))?"

#: A bracketed level as the Act actually writes them: (1) (1.1) (a) (a.1) (ss)
#: (yb) (4i) (i) (viii) (A) (IV). Deliberately narrow - an earlier version
#: accepted any bracketed word and turned "section 258 (rebate)" into the
#: provision "258(rebate)".
_BRACKET = (
    r"\((?:"
    r"\d+(?:\.\d+)*[a-z]{0,2}"      # (1) (1.1) (12.601) (4i)
    r"|[a-z]{1,2}(?:\.\d+)*"         # (a) (ss) (yb) (a.1)
    r"|[ivxl]{1,6}(?:\.\d+)*"        # (i) (viii) (ii.1)
    r"|[A-Z]{1,4}(?:\.\d+)*"         # (A) (IV)
    r")\)"
)

#: A provision: a section number followed by any number of bracketed levels.
PROVISION = re.compile(r"\b(%s)((?:%s)*)" % (_SECTION, _BRACKET))
#: A continuation in a list - bracketed levels with no section number of their own.
CONTINUATION = re.compile(r"(?<![\w.)])((?:%s)+)" % _BRACKET)

#: Words introducing a provision, used to find where a list starts.
LEAD = re.compile(
    r"\b(sections?|subsections?|paragraphs?|subparagraphs?|clauses?|"
    r"articles?|paragraphes?|alin[ée]as?|sous-alin[ée]as?)\b", re.I)

#: Shapes that exist in the report but cannot resolve, because Phase 0 holds
#: only the enacted Body of each instrument.
UNRESOLVABLE_SHAPE = re.compile(
    r"\b(Schedule|Class(?:es)?|annexe|cat[ée]gorie)\b", re.I)

#: "the description of L in subsection 1400(3)" - a formula variable. It
#: resolves to the subsection; the variable survives in raw_text.
VARIABLE = re.compile(
    r"the description of ([A-Z])\b|la description de ([A-Z])\b", re.I)

#: "paragraph (a.3) of definition of \"investment tax credit\"" - a paragraph
#: inside a defined term. Phase 0 keys definition paragraphs as
#: 127(9)"investment tax credit"(a.3), so the target exists.
DEFINITION_REF = re.compile(
    r"definition of\s+[\"\u201c]?(?P<term>[^\"\u201d,;]+?)[\"\u201d]?"
    r"(?=\s*(?:,|;|$|\sin\b))"
    r"|d[\u00e9e]finition\s+(?:de\s+|du\s+|d')?[\"\u00ab\u201c]\s*(?P<term_fr>[^\"\u00bb\u201d]+?)\s*[\"\u00bb\u201d]", re.I)

#: The paragraph label that belongs to a definition reference.
DEF_PARAGRAPH = re.compile(
    r"(?:paragraph|alin[\u00e9e]as?)\s*(\([0-9a-zA-Z][0-9a-zA-Z.]*\))", re.I)


#: An instrument named after its provisions - "Part V of Schedule V **to the**
#: Excise Tax Act". Without this the segment before an instrument would be
#: credited to it even when it belongs to the previous one.
TRAILING_LINK = re.compile(r"(?:to|of|de|du|\xe0)\s+(?:the\s+|la\s+|le\s+|l')?$", re.I)

#: Spans that name a Schedule, Class or Part. A provision number inside one of
#: these is part of that phrase, not a citation this dataset can resolve.
SCHEDULE_SPAN = re.compile(
    # A clause qualified by "of Schedule(s) X" belongs to that Schedule, even
    # where the provision is named first: "section 2 and paragraph 3(a) of
    # Schedules V and VI" cites the Schedules, not ITR section 2.
    r"[^,;]*?\b(?:of|de|des|du|d')\s*(?:l'|la\s+|les\s+)?(?:Schedules?|annexes?)\b[^,;]*"
    r"|\bClass(?:es)?\b[^;]*?\bSchedule\b\s*[IVXL]+"   # "Classes 41, 41.1 and 41.2 of Schedule II"
    r"|\bClass(?:es)?\b\s*[\d.,\s and]*"
    r"|\bSchedule\b\s*[IVXL]*"
    r"|\bPart\b\s*[IVXL]+(?:\.\d+)?"
    r"|\bannexe\b\s*[IVXL]*|\bcat[\xe9e]gories?\b\s*[\d.,\s et]*", re.I)


#: A title we do not hold and do not name individually - "Global Minimum Tax
#: Act", "Canada-United States Tax Convention", "Non-Taxable Imported Goods
#: (GST/HST) Regulations". Recognising these stops their provisions being
#: credited to whichever instrument was named before them.
OTHER_INSTRUMENT = re.compile(
    r"\b(?:[A-Z][\w.'\-]*(?:\s+(?:of|and|the|for|on|to|[A-Z][\w.'\-]*|\([^)]+\)))*?\s+)"
    r"(Act|Convention|Agreement|Regulations|Rules|Plan|Treaty)\b")


def split_instruments(text):
    """Split a field into (instrument_code, instrument_name, segment) pieces.

    The report writes instruments in both orders and sometimes runs two
    references together with no separator at all, which it does 11 times:
    "subsection 66.1(6)Income Tax Regulations, section 1219". Each instrument
    therefore claims exactly one side - the text before it when it is named
    after its provisions ("... to the Excise Tax Act"), the text after it
    otherwise - so no span is credited to two instruments.
    """
    hits = []
    for name, code in INSTRUMENTS:
        for m in re.finditer(re.escape(name), text):
            hits.append((m.start(), m.end(), name, code))
    known = [(a, b) for a, b, _n, _c in hits]
    for m in OTHER_INSTRUMENT.finditer(text):
        if not any(a <= m.start() < b or a < m.end() <= b for a, b in known):
            hits.append((m.start(), m.end(), m.group(0).strip(), "OTHER"))
    if not hits:
        return [(None, None, text)]

    hits.sort(key=lambda h: (h[0], -(h[1] - h[0])))
    kept, last_end = [], -1
    for start, end, name, code in hits:
        if start >= last_end:
            kept.append((start, end, name, code))
            last_end = end

    segments = []
    for i, (start, end, name, code) in enumerate(kept):
        prev_end = kept[i - 1][1] if i else 0
        next_start = kept[i + 1][0] if i + 1 < len(kept) else len(text)
        before = text[prev_end:start]
        after = text[end:next_start]
        trailing = bool(TRAILING_LINK.search(before.rstrip()))
        segment = before if trailing else after
        segments.append((code, name, segment.strip(" ,;.")))
    return segments


def provisions_in(segment):
    """Ordered provision paths in one segment, with lists and ranges expanded.

    A bracketed item with no section number of its own inherits the section from
    the item before it: "subsections 39(1.1) and (2)" is 39(1.1) and 39(2).
    Inheriting copies a number that is present in the same field; it is not a
    guess about meaning.
    """
    spans = [(m.start(), m.end()) for m in SCHEDULE_SPAN.finditer(segment)]

    def in_schedule(pos):
        return any(a <= pos < b for a, b in spans)

    found, previous = [], None
    for match in re.finditer(
            r"(%s)((?:%s)*)|((?:%s)+)" % (_SECTION, _BRACKET, _BRACKET), segment):
        pos = match.start()
        if match.group(1):
            path = match.group(1) + (match.group(2) or "")
            if not in_schedule(pos):
                previous = path
            found.append((path, pos, in_schedule(pos)))
        elif (match.group(3) and previous and not in_schedule(pos)
              and not re.match(r"\s*(?:of|de|du|d')\s*(?:the\s+|la\s+|le\s+|l')?"
                               r"(?:Class|Schedule|Part|"
                               r"annexe|cat[\xe9e]gorie|partie|definition|"
                               r"d[\xe9e]finition)\b",
                               segment[match.end():], re.I)):
            # A continuation inherits the previous path's prefix at matching
            # depth: after 1100(1)(a.3), "(yb)" is 1100(1)(yb), not 1100(yb).
            # After 39(1.1), "(2)" is 39(2). It copies levels that are present
            # in the same field, so it is mechanical, not a guess.
            levels = re.findall(_BRACKET, match.group(3))
            prefix_levels = re.findall(_BRACKET, previous)
            keep = len(prefix_levels) - len(levels)
            if keep < 0:
                keep = 0
            base = previous
            for _ in range(len(prefix_levels) - keep):
                base = base[:base.rfind("(")]
            found.append((base + match.group(3), pos, False))
    return found


#: French writes a paragraph label without its opening bracket - "alinéa
#: 118(1)d)" where English writes "paragraph 118(1)(d)". Phase 0's citation
#: paths use the English form, so French reference text is normalised to it
#: before extraction. Same convention, same fix, as docs/citation-path-rule.md.
#: A bare French label token: the text immediately before an unmatched ")".
_FR_BARE_LABEL = re.compile(r"([0-9A-Za-z][0-9A-Za-z.]*)$")

#: A bare token that carries its section number with it: French writes
#: "alinéa 38a.2)" where English writes "paragraph 38(a.2)".
_FR_SECTION_AND_LABEL = re.compile(r"^(\d+(?:\.\d+)*)([A-Za-z][0-9A-Za-z.]*)$")


def normalise_french_labels(text):
    """Rewrite French paragraph labels into the bracketed English form.

    French writes "alinéas 149(1)(c) et d) à d.6)" where English writes
    "paragraphs 149(1)(c) and (d) to (d.6)". Phase 0's citation paths use the
    English form, so the French text is rewritten before extraction.

    The rewrite is driven by **bracket matching**, not by the word in front of
    the label. An earlier version keyed on "alinéa" and on a preceding ")", and
    so missed labels that follow "et" or "à": "d.6)" was then read by the
    section pattern as the number 6, resolving to ITA section 6. Two of the
    thirty references in the first precision sample failed that way, and the
    hand check is what caught it.

    A ")" with no unclosed "(" to its left cannot be closing anything, so
    whatever token sits in front of it is a bare label.
    """
    out, depth = [], 0
    for ch in text:
        if ch == "(":
            depth += 1
            out.append(ch)
        elif ch == ")":
            if depth > 0:
                depth -= 1
                out.append(ch)
            else:
                # Unmatched closer: wrap the token before it.
                prefix = "".join(out)
                m = _FR_BARE_LABEL.search(prefix)
                if m:
                    token = m.group(1)
                    split = _FR_SECTION_AND_LABEL.match(token)
                    wrapped = ("%s(%s)" % (split.group(1), split.group(2))
                               if split else "(%s)" % token)
                    out = list(prefix[:m.start()]) + list(wrapped)
                else:
                    out.append(ch)
        else:
            out.append(ch)
    return "".join(out)


def extract(field_text, lang="en", term_map=None):
    """Reference rows for one measure's Legal reference field.

    `term_map` maps a French defined term to its English one, taken from Phase 0's
    symmetric bilingual join. It is required for French references, because
    Phase 0 keys every definition by its English term. A term that does not join
    is left unresolved with the reason `term_not_joined` - a term we declined to
    pair across languages is one we must decline to resolve across languages.

    Returns a list of dicts with instrument, citation_path (or None), raw_text
    and a reason where it did not resolve.
    """
    text = (field_text or "").strip()
    if not text:
        return []
    if lang == "fr":
        text = normalise_french_labels(text)
    if NO_PROVISION.match(text):
        # Not an unresolved reference - a statement that no provision exists.
        return []

    rows, order = [], 0
    for code, name, segment in split_instruments(text):
        if code is None:
            order += 1
            rows.append({
                "instrument": None, "instrument_name": None,
                "citation_path": None, "raw_text": text, "order_index": order,
                "reason": "no instrument named - a provision number alone is "
                          "not a citation",
            })
            continue

        variable = VARIABLE.search(segment)
        found = provisions_in(segment)
        definition = DEFINITION_REF.search(segment)

        if not found:
            order += 1
            rows.append({
                "instrument": code, "instrument_name": name,
                "citation_path": None, "raw_text": segment or text,
                "order_index": order,
                "reason": "instrument named but no provision recognised",
            })
            continue

        for path, _pos, in_schedule in found:
            order += 1
            row = {
                "instrument": code, "instrument_name": name,
                "citation_path": None, "raw_text": segment,
                "order_index": order, "reason": "",
            }
            if code not in RESOLVABLE:
                row["reason"] = "%s is not held by this dataset" % name
            elif in_schedule:
                row["reason"] = (
                    "Schedule, Class or Part - this dataset holds only the "
                    "enacted Body of each instrument")
            else:
                row["citation_path"] = path
            if variable and row["citation_path"]:
                row["variable"] = variable.group(1) or variable.group(2)
            rows.append(row)

        # A paragraph inside a defined term: 127(9) "investment tax credit"
        # (a.3). See docs/reference-rule.md, "Paragraphs of a definition".
        if definition and code in RESOLVABLE:
            # Prefer a subsection - "definition of X in subsection 127(9)" -
            # but a definition can also hang off a bare section, as in
            # "definition of X in section 248". Both are real keys in Phase 0.
            host = next(
                (path for path, _pos, sched in found if "(" in path and not sched),
                None)
            if host is None:
                host = next(
                    (path for path, _pos, sched in found if not sched), None)
            if host:
                order += 1
                raw_term = " ".join(
                    (definition.group("term") or definition.group("term_fr") or ""
                     ).split()).strip("\u201c\u201d\"\u00ab\u00bb ")
                term, reason = raw_term, ""
                if lang == "fr":
                    term = (term_map or {}).get(raw_term)
                    if not term:
                        reason = "term_not_joined"
                para = DEF_PARAGRAPH.search(segment)
                path = None
                if term:
                    path = '%s"%s"%s' % (
                        host, term, para.group(1) if para else "")
                rows.append({
                    "instrument": code, "instrument_name": name,
                    "citation_path": path, "raw_text": segment,
                    "order_index": order,
                    "reason": reason, "defined_term": raw_term,
                })
    return rows
