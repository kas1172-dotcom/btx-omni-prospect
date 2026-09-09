"""Conservative synthesis safety checks; not a claim of complete semantic verification."""
import re
from decimal import Decimal, InvalidOperation

NUMBER = re.compile(r"(?<![\w])[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?:\s*(?:million|billion|thousand)\b|[mMbBkK]\b)?")
COMPLETED_WRITE = re.compile(
    r"\b(?:I|we)\s+(?:have\s+)?(?:successfully\s+)?(?:sent|emailed|created|updated|deleted|approved|submitted|booked|committed)\b|"
    r"(?<!\bno )(?<!\bnot )\b(?:email|message|HubSpot record)\s+(?:has been |was )?(?:sent|updated|created|synchronized)\b",
    re.IGNORECASE,
)
RECORD_IDENTIFIER = re.compile(r'(?<![\w])(?=[A-Za-z0-9:_-]*[A-Za-z])(?=[A-Za-z0-9:_-]*\d)[A-Za-z][A-Za-z0-9]*(?:[-_:][A-Za-z0-9]+)+(?![\w])')
MISLABELED_OPPORTUNITY = re.compile(
    r"(?:\bquote(?:s|d)?\b\s*(?:\([^)]{0,32})?\bOPP[A-Za-z0-9:_-]*\b|"
    r"\bOPP[A-Za-z0-9:_-]*\b\s+(?:(?:is|was|as)\s+)?(?:a\s+|the\s+)?\bquote\b)",
    re.IGNORECASE,
)


def _numbers(text):
    result = set()
    for match in NUMBER.finditer(text):
        token = match.group().replace(",", "").lower().strip()
        if len(token) > 40:
            continue
        scale = Decimal(1)
        for suffix, multiple in (("billion", 10**9), ("million", 10**6), ("thousand", 10**3), ("b", 10**9), ("m", 10**6), ("k", 10**3)):
            if token.endswith(suffix):
                token, scale = token[:-len(suffix)].strip(), Decimal(multiple)
                break
        try:
            result.add(Decimal(token) * scale)
        except InvalidOperation:
            continue
    return result


def synthesis_rejection(content: str, canonical_text: str, *, blocking_constraints: bool = False, diagnostics: dict | None = None) -> str | None:
    if not content.strip() or len(content) > 16000:
        return "INVALID_LENGTH"
    if any(len(match.group()) > 40 for match in NUMBER.finditer(content)):
        return "INVALID_NUMERIC_CLAIM"
    if COMPLETED_WRITE.search(content):
        return "UNSUPPORTED_EXECUTION_CLAIM"
    # Replacement-key prefixes are canonical record types in this application.
    # Calling an OPP record a quote changes the business meaning even when the ID
    # and all numeric claims are otherwise grounded.
    if MISLABELED_OPPORTUNITY.search(content):
        return "MISLABELED_RECORD_TYPE"
    if blocking_constraints and re.search(r"\b(?:capacity is confirmed|ready to commit|no delivery constraints|guaranteed delivery|qualified substitute is available)\b", content, re.IGNORECASE):
        return "CONTRADICTED_CONSTRAINT"
    # Referencing a looked-up invoice ID is not a financial claim. Conversely,
    # digits inside that ID must never authorize a made-up monetary amount.
    known_identifiers = set(RECORD_IDENTIFIER.findall(canonical_text))
    numeric_content, numeric_canonical = content, canonical_text
    for identifier in sorted(known_identifiers, key=len, reverse=True):
        pattern = r'(?<![\w:.-])' + re.escape(identifier) + r'(?![\w:-]|\.\w)'
        numeric_content = re.sub(pattern, 'RECORD_IDENTIFIER', numeric_content)
        numeric_canonical = re.sub(pattern, 'RECORD_IDENTIFIER', numeric_canonical)
    minor_field = r'(["\']\w+_minor["\']\s*:\s*)(-?\d+)'
    # Raw minor-unit integers cannot authorize dollar claims.
    allowed = _numbers(re.sub(minor_field, r'\1"MINOR_UNIT_VALUE"', numeric_canonical))
    # Explicit minor-unit fields may be rendered as major currency units.
    for match in re.finditer(r'["\']\w+_minor["\']\s*:\s*(-?\d+)', canonical_text):
        if len(match.group(1)) <= 24:
            allowed.add(Decimal(match.group(1)) / 100)
    allowed |= {value.quantize(Decimal(".01")) for value in allowed if abs(value) < Decimal("1e24")}
    # Numbered-list ordinals are formatting, not financial observations.
    prose = re.sub(r"(?m)^\s*\d+[.)]\s+", "", numeric_content)
    unsupported = _numbers(prose) - allowed
    if unsupported:
        if diagnostics is not None:
            diagnostics["unsupported_numeric_values"] = [str(value) for value in sorted(unsupported)[:8]]
        return "UNSUPPORTED_NUMERIC_CLAIM"
    return None
