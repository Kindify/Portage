"""Parse a Justice Laws XML instrument into flat records.

XML in, list of records out. No database, no file writing, so it can be tested
directly. Structure comes from element nesting and <Label> elements only -
nothing is inferred from body text, position, indentation or number patterns.

The citation path rule this implements is specified in docs/citation-path-rule.md.
"""

from collections import defaultdict

from lxml import etree

from .labels import normalise, normalise_term

LIMS = "{http://justice.gc.ca/lims}"

#: The seven addressable levels, mapped to the level name stored in the database.
ADDRESSABLE = {
    "Section": "section",
    "Subsection": "subsection",
    "Paragraph": "paragraph",
    "Subparagraph": "subparagraph",
    "Clause": "clause",
    "Subclause": "subclause",
    "Subsubclause": "subsubclause",
}

#: Containers whose text is captured whole, because they hold no addressable
#: descendants. Verified against the source, not assumed - see docs/source-notes.md.
OPAQUE = {
    "ContinuedParagraph": ("continued", "c"),
    "ContinuedSectionSubsection": ("continued", "c"),
    "ContinuedSubparagraph": ("continued", "c"),
    "ContinuedClause": ("continued", "c"),
    "ContinuedSubclause": ("continued", "c"),
    "ContinuedDefinition": ("continued", "c"),
    "ContinuedFormulaParagraph": ("continued", "c"),
    "FormulaGroup": ("formula", "f"),
    "Heading": ("heading", "h"),
}

#: Stored in their own columns *when they belong to an addressable unit or a
#: Definition*. Elsewhere - a <Label> on a FormulaDefinition, for instance,
#: which carries the formula's variable name - they are ordinary body text and
#: must not be dropped.
METADATA = {"Label", "MarginalNote", "HistoricalNote"}

#: Elements that store their own Label/MarginalNote/HistoricalNote in columns.
OWNERS = set(ADDRESSABLE) | {"Definition"}


def _text_of(el):
    """All text inside an element, in document order, exactly as published.

    Inline elements (XRefExternal, DefinedTermEn, DefinitionRef, Repealed) are
    part of the sentence and are carried through untouched.
    """
    return "".join(el.itertext())


def _own_text(el):
    """An addressable unit's own opening text: its direct <Text> child.

    The source guarantees at most one, always before any structural child;
    both invariants were checked against the file, not assumed.
    """
    for child in el:
        if isinstance(child.tag, str) and child.tag == "Text":
            return _text_of(child)
    return ""


def _is_text_leaf(el):
    """True when nothing inside this element is tracked structurally.

    Such a subtree is captured whole as text. This is a structural test, not a
    list of element names, so an element type nobody anticipated is captured
    rather than dropped.
    """
    for d in el.iter():
        if d is el:
            continue
        if not isinstance(d.tag, str):
            continue
        if d.tag in ADDRESSABLE or d.tag == "Definition" or d.tag in OPAQUE or d.tag == "Text":
            return False
    return True


def _defined_terms(definition):
    """The definition's own term and its other-language equivalent.

    Read from the DIRECT children of the definition's own <Text>, never by a
    descendant search. A descendant search returns the first DefinedTerm
    anywhere in the body, which is normally a cross-reference to a *different*
    definition - in the French file that mis-keyed "action admissible" to a
    phrase quoted in its body, and collided three definitions onto one path.

    The published pattern is: own term first, then the body, then the other
    language's equivalent in parentheses at the end.
    """
    text = None
    for child in definition:
        if isinstance(child.tag, str) and child.tag == "Text":
            text = child
            break
    if text is None:
        return None, None

    terms = [c for c in text if isinstance(c.tag, str)
             and c.tag in ("DefinedTermEn", "DefinedTermFr")]
    if not terms:
        return None, None

    # The definition's own term is the first DefinedTerm in its opening <Text>.
    own = terms[0]
    other_tag = "DefinedTermFr" if own.tag == "DefinedTermEn" else "DefinedTermEn"

    # The other language's equivalent is published in parentheses at the END of
    # the definition - which for a definition with paragraphs is after the last
    # of them, not in the opening <Text>. So search the whole subtree and take
    # the LAST match: cross-references to other definitions occur mid-body, the
    # equivalent comes last. Nested definitions are excluded so their terms are
    # not mistaken for this one's.
    other = None
    for candidate in definition.iter(other_tag):
        if any(a is not definition and a.tag == "Definition"
               for a in candidate.iterancestors()):
            continue
        other = candidate

    if own.tag == "DefinedTermEn":
        return own.text, (other.text if other is not None else None)
    return (other.text if other is not None else None), own.text


def _marginal_note(el):
    for child in el:
        if isinstance(child.tag, str) and child.tag == "MarginalNote":
            return _text_of(child)
    return None


def _historical_note(el):
    for child in el:
        if isinstance(child.tag, str) and child.tag == "HistoricalNote":
            return " ".join(_text_of(child).split())
    return None


class _Walker:
    def __init__(self, act, source_url):
        self.act = act
        self.source_url = source_url
        self.records = []
        self.order = 0
        # Fragment counters are keyed on the owning path, not held per call, so
        # two sibling wrappers under the same parent cannot produce the same path.
        self.counters = defaultdict(int)
        self.seen_paths = set()
        self.dup_terms = defaultdict(int)

    def _next(self, parent_path, letter):
        self.counters[(parent_path, letter)] += 1
        return "%s~%s%d" % (parent_path, letter, self.counters[(parent_path, letter)])

    def _emit(self, **kw):
        self.order += 1
        rec = {
            "act": self.act,
            "order_index": self.order,
            "source_url": self.source_url,
            "label_raw": None,
            "label_anomaly": 0,
            "anomaly_reason": "",
            "heading_en": None,
            "history_note": None,
            "defined_term_en": None,
            "defined_term_fr": None,
            "text_en": "",
        }
        rec.update(kw)
        self.records.append(rec)
        return rec

    def walk(self, el, prefix, parent_path, skip_direct_text):
        """Walk children of `el` in document order, emitting records.

        `skip_direct_text` is True when `el` is a unit whose own opening <Text>
        has already been captured on its record. Every other <Text> encountered
        is emitted as a fragment - the walker must never silently drop text, or
        the round-trip test would pass while the database lost a sentence.
        """
        seen_direct_text = False

        for child in el:
            if not isinstance(child.tag, str):
                continue
            tag = child.tag

            if tag in METADATA:
                if el.tag in OWNERS:
                    continue  # stored in a column on the owning record
                # A Label outside a unit is body text - the variable name in a
                # formula, for example. Dropping it would silently corrupt the
                # sentence it introduces.
                self._emit(
                    citation_path=self._next(parent_path, "t"),
                    level="text",
                    parent_path=parent_path or None,
                    is_addressable=0,
                    text_en=_text_of(child),
                )
                continue

            if tag == "Text":
                if skip_direct_text and not seen_direct_text:
                    seen_direct_text = True
                    continue
                # Text inside a wrapper we descended through (FormulaDefinition,
                # FormulaParagraph, Provision). It belongs to the nearest
                # addressable ancestor but has no identity of its own.
                self._emit(
                    citation_path=self._next(parent_path, "t"),
                    level="text",
                    parent_path=parent_path or None,
                    is_addressable=0,
                    text_en=_text_of(child),
                )
                continue

            if tag in ADDRESSABLE:
                level = ADDRESSABLE[tag]
                label = child.find("Label")
                raw = label.text if label is not None else None
                token, anomaly, reason = normalise(raw, level)
                path = prefix + token
                if path in self.seen_paths:
                    # The published XML does repeat a label: the French 142.6(8)b)
                    # has two subparagraphs numbered (iv) where the English has
                    # (iv) and (v). Disambiguate deterministically and catalogue
                    # it; the source text is never altered.
                    self.dup_terms[path] += 1
                    path = "%s#%d" % (path, self.dup_terms[path] + 1)
                    anomaly = True
                    reason = (reason + "; " if reason else "") + \
                        "duplicate label in the same provision"
                self.seen_paths.add(path)
                self._emit(
                    citation_path=path,
                    level=level,
                    parent_path=parent_path,
                    is_addressable=1,
                    label_raw=raw,
                    label_anomaly=1 if anomaly else 0,
                    anomaly_reason=reason,
                    heading_en=_marginal_note(child),
                    history_note=_historical_note(child),
                    text_en=_own_text(child),
                )
                self.walk(child, path, path, skip_direct_text=True)

            elif tag == "Definition":
                # No <Label>, but it holds addressable Paragraphs, so it needs a
                # key or 248(1)(a) collides 86 ways. The key is the defined term,
                # not a document-order ordinal: each language file alphabetises
                # its definitions in its own language, so ordinal 1 is "absorbed
                # capacity" in English and "tax shelter" in French. See
                # docs/citation-path-rule.md section 4.
                raw_en, raw_fr = _defined_terms(child)
                term_en = normalise_term(raw_en)
                term_fr = normalise_term(raw_fr)

                if term_en:
                    path, fallback = '%s"%s"' % (parent_path, term_en), ""
                elif term_fr:
                    path, fallback = '%s"%s"' % (parent_path, term_fr), "french term - no english term present"
                else:
                    path, fallback = self._next(parent_path, "d"), "ordinal - no defined term in either language"

                # The Act does define the same term twice in one subsection -
                # 44.1(1) "eligible small business corporation share" is two
                # distinct definitions. Disambiguate deterministically rather
                # than lose one to the uniqueness constraint.
                if path in self.seen_paths:
                    self.dup_terms[path] += 1
                    path = "%s#%d" % (path, self.dup_terms[path] + 1)
                    fallback = (fallback + "; " if fallback else "") + \
                        "duplicate defined term in the same provision"
                self.seen_paths.add(path)

                self._emit(
                    citation_path=path,
                    level="definition",
                    parent_path=parent_path,
                    is_addressable=0,
                    label_anomaly=1 if fallback else 0,
                    anomaly_reason=fallback,
                    defined_term_en=term_en,
                    defined_term_fr=term_fr,
                    text_en=_own_text(child),
                )
                self.walk(child, path, path, skip_direct_text=True)

            elif tag in OPAQUE:
                level, letter = OPAQUE[tag]
                self._emit(
                    citation_path=self._next(parent_path, letter),
                    level=level,
                    parent_path=parent_path or None,
                    is_addressable=0,
                    text_en=_text_of(child),
                )

            elif _is_text_leaf(child):
                # A subtree containing nothing we track structurally - a
                # <FormulaTerm> holding a formula's variable name, for example.
                # Capture it whole. Without this branch the walker would descend,
                # find no child it recognises, and silently drop the text.
                self._emit(
                    citation_path=self._next(parent_path, "t"),
                    level="text",
                    parent_path=parent_path or None,
                    is_addressable=0,
                    text_en=_text_of(child),
                )

            else:
                # A wrapper with no identity of its own (FormulaDefinition,
                # FormulaParagraph, Provision, SectionPiece). Descend without
                # emitting, but its <Text> children are not skipped.
                self.walk(child, prefix, parent_path, skip_direct_text=False)
                if child.tail and child.tail.strip():
                    self._emit(
                        citation_path=self._next(parent_path, "t"),
                        level="text",
                        parent_path=parent_path or None,
                        is_addressable=0,
                        text_en=child.tail,
                    )


def parse(xml_path, act, source_url):
    """Parse one instrument. Returns (records, meta)."""
    tree = etree.parse(str(xml_path))
    root = tree.getroot()

    meta = {
        "act": act,
        "source_url": source_url,
        "consolidation_date": root.get(LIMS + "pit-date"),
        "last_amended_date": root.get(LIMS + "lastAmendedDate"),
        "currency_date": root.get(LIMS + "current-date"),
        "root_element": root.tag,
    }

    body = root.find("Body")
    walker = _Walker(act, source_url)
    walker.walk(body, "", "", skip_direct_text=False)
    return walker.records, meta


def source_text(xml_path):
    """The text of the instrument as published, in document order.

    This is the target the round-trip test compares against. It is built by a
    deliberately different route from the parser: a mixed-content walk that
    collects every character of text under <Body> except the Label,
    MarginalNote and HistoricalNote belonging to a unit, which the parser stores
    in columns instead.

    The difference in method is the point. An earlier version of this function
    shared the parser's blind spot - both skipped every <Label>, so both lost the
    formula variable names in FormulaDefinition, and the round-trip test passed
    while the database was missing text. A check that reuses the thing it is
    checking proves nothing.
    """
    root = etree.parse(str(xml_path)).getroot()
    body = root.find("Body")
    out = []

    def collect(el):
        for child in el:
            if not isinstance(child.tag, str):
                continue
            if child.tag in METADATA and el.tag in OWNERS:
                continue
            if child.tag in OPAQUE:
                out.append(_text_of(child))
                continue
            if child.text:
                out.append(child.text)
            collect(child)
            if child.tail:
                out.append(child.tail)

    collect(body)
    return "".join(out)
