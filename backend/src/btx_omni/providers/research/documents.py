"""Non-executable article text and passage extraction; no invented completeness."""
from __future__ import annotations

import hashlib
from html.parser import HTMLParser


class _ArticleText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skipped = 0
        self.focus = 0
        self.body: list[str] = []
        self.article: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style", "nav", "footer", "header", "noscript", "svg", "form"}:
            self.skipped += 1
        if tag in {"article", "main"}:
            self.focus += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style", "nav", "footer", "header", "noscript", "svg", "form"}:
            self.skipped = max(0, self.skipped - 1)
        if tag in {"article", "main"}:
            self.focus = max(0, self.focus - 1)

    def handle_data(self, data):
        value = " ".join(data.split())
        if value and not self.skipped:
            self.body.append(value)
            if self.focus:
                self.article.append(value)


def extract_document(payload: bytes, media_type: str, *, max_chars: int = 30000) -> dict:
    if not 0 < max_chars <= 30000:
        raise ValueError("INVALID_EXTRACTION_BUDGET")
    checksum = hashlib.sha256(payload).hexdigest()
    mime = media_type.split(";", 1)[0].strip().lower()
    # PDF/JS/paywall extraction requires a separately qualified renderer. Never
    # label the title/HTML shell as a complete article when it is all we have.
    if mime not in {"text/html", "application/xhtml+xml", "text/plain"}:
        return {"checksum_sha256": checksum, "media_type": mime, "extraction_status": "UNSUPPORTED_MEDIA_TYPE", "extraction_complete": False, "passages": []}
    decoded = payload.decode("utf-8", errors="replace")
    lossy = "\ufffd" in decoded
    if mime == "text/plain":
        text = decoded.strip()
        method = "PLAIN_TEXT"
    else:
        parser = _ArticleText()
        parser.feed(decoded)
        text = "\n".join(parser.article or parser.body)
        method = "ARTICLE_OR_MAIN_TEXT" if parser.article else "BODY_TEXT_UNVERIFIED"
    truncated = len(text) > max_chars
    selected = text[:max_chars]
    text_checksum = hashlib.sha256(f"BTX_PUBLIC_TEXT_2:{method}:{truncated}:{lossy}:{selected}".encode()).hexdigest()
    passages = [{"id": f"passage:{text_checksum[:20]}:{start}", "start_character": start, "end_character": min(start + 1200, len(selected)), "text": selected[start:start + 1200]} for start in range(0, len(selected), 1200)]
    return {"checksum_sha256": checksum, "media_type": mime, "extraction_method": method,
            "extraction_version": "BTX_PUBLIC_TEXT_2", "extracted_text_sha256": text_checksum,
            "extraction_status": "LOSSY_CHARACTER_DECODING" if lossy else "TRUNCATED" if truncated else "TEXT_EXTRACTED" if selected else "NO_READABLE_TEXT",
            "extraction_complete": bool(selected) and not lossy and not truncated and method == "PLAIN_TEXT",
            "completeness_note": "Character decoding lost information; completeness is not established." if lossy else "Extraction stopped at the configured character budget." if truncated else "All plain-text response retained." if method == "PLAIN_TEXT" else "HTML text extraction cannot establish publisher article completeness or recover JavaScript/paywalled text.",
            "extracted_characters": len(selected), "passages": passages}
