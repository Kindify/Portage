"""Label normalisation.

Turns a raw <Label> from the Justice Laws XML into the normalised token used to
build a citation path. The rule this implements is specified in
docs/citation-path-rule.md section 2, and the reasoning is in docs/decisions.md.

Two things this module must never do: read anything other than the label text,
and alter the source. It produces a derived key. `label_raw` keeps the original.
"""

import re
import unicodedata

QUOTES = "“”«»‘’\""

#: A token that already looks like a normalised bracketed label: (a) (4) (iii.1)
_BRACKETED = re.compile(r"^\([0-9A-Za-z][0-9A-Za-z.]*\)$")
#: A bare label of the French form: a)  b.1)  ii)
_BARE = re.compile(r"^([0-9A-Za-z][0-9A-Za-z.]*)\)$")
#: An unmatched opening bracket: (b
_UNMATCHED = re.compile(r"^\(([0-9A-Za-z][0-9A-Za-z.]*)$")
#: A bare section-style number: 87  110.6  1100A
_NUMERIC = re.compile(r"^[0-9][0-9A-Za-z.]*$")
#: A section-level range, after connector normalisation: "3000 to 3002"
_RANGE = re.compile(r"^[0-9][0-9A-Za-z.]*(?: (?:to|and) [0-9][0-9A-Za-z.]*)+$")


def _collapse(text):
    """Rule 1. Collapse whitespace, including the non-breaking spaces the
    French file uses after an opening guillemet."""
    if text is None:
        return ""
    text = text.replace(" ", " ")
    return " ".join(text.split())


def normalise(raw, level):
    """Normalise one raw label.

    Returns (token, anomaly, reason). `anomaly` is True when the rule had to do
    something beyond ordinary bracketing, in which case `reason` names the rule
    so the case can be catalogued and a human can look at it.
    """
    s = _collapse(raw)
    if not s:
        return "", True, "empty label"

    # Rule 2: section labels are bare.
    if level == "section":
        s = s.rstrip(".")
        if _NUMERIC.match(s):
            return s, False, ""
        # Range connectors apply at section level too. The Regulations number
        # sections "3000 to 3002" in English and "3000 à 3002" in French; without
        # this the two never join and the provision looks French-only.
        ranged = re.sub(r"\s+et\s+", " and ", re.sub(r"\s+à\s+", " to ", s))
        if _RANGE.match(ranged):
            return ranged, False, ""
        stripped = s.strip(QUOTES).strip()
        if stripped != s and _NUMERIC.match(stripped):
            return stripped, True, "stray quotation mark"
        return s, True, "unrecognised section label"

    # Rule 2b: at subsubclause level a bare numeral is the published form.
    # The XML labels these 1, 2, 3 - unbracketed - and that is correct, not a
    # defect. Flagging them would bury the real anomalies in noise.
    if level == "subsubclause" and _NUMERIC.match(s):
        return s, False, ""

    anomaly, reason = False, ""

    # Rule 3: strip stray quotation marks at either end.
    stripped = s.strip(QUOTES).strip()
    if stripped != s:
        anomaly, reason = True, "stray quotation mark"
        s = stripped

    # Rule 3b: remove whitespace immediately inside brackets, so the published
    # "(b )" normalises to "(b)" rather than falling apart into two tokens.
    tightened = re.sub(r"\(\s+", "(", re.sub(r"\s+\)", ")", s))
    if tightened != s:
        anomaly, reason = True, "whitespace inside brackets"
        s = tightened

    # Rule 4: range connectors, French form to English form.
    s = re.sub(r"\s+et\s+", " and ", s)
    s = re.sub(r"\s+à\s+", " to ", s)

    # Rules 5 and 6 apply per token, so ranges are handled the same way.
    out, token_anomaly, token_reason = [], False, ""
    for token in s.split(" "):
        if token in ("and", "to"):
            out.append(token)
            continue
        if _BRACKETED.match(token):
            out.append(token)
            continue
        m = _BARE.match(token)                       # Rule 5: a) -> (a)
        if m:
            out.append("(%s)" % m.group(1))
            continue
        m = _UNMATCHED.match(token)                  # Rule 6: (b -> (b)
        if m:
            out.append("(%s)" % m.group(1))
            token_anomaly, token_reason = True, "unmatched opening bracket"
            continue
        # Rule 7: leave it alone, flag it, catalogue it.
        out.append(token)
        token_anomaly, token_reason = True, "unrecognised label form"

    if token_anomaly:
        anomaly = True
        reason = "%s; %s" % (reason, token_reason) if reason else token_reason

    return " ".join(out), anomaly, reason


def normalise_term(raw):
    """Normalise a defined term for use in a citation path.

    Unicode NFC, collapsed whitespace, nothing else. Case is preserved as
    published: lowercasing and quote-stripping were both measured against the
    real files and changed the English/French join rate by zero, so neither is
    applied. The less a normalisation does, the less it can do wrong.

    Specified in docs/citation-path-rule.md section 4.
    """
    if raw is None:
        return None
    text = " ".join(unicodedata.normalize("NFC", raw).split())
    return text or None
