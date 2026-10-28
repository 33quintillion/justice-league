"""Turns an officially obtained file into citable sections.

Nothing here fetches from the internet: a researcher downloads the official file (respecting each
site's terms and robots rules) and uploads it with its official URL. The original bytes are kept.
"""
from __future__ import annotations

import hashlib
import io
import re
from dataclasses import dataclass

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MIN_TEXT_CHARS = 200
ALLOWED_TYPES = {"application/pdf", "text/plain"}


class IngestError(ValueError):
    pass


@dataclass
class ParsedSection:
    ref: str
    ref_key: str
    heading: str
    text: str


def sniff_media_type(data: bytes, declared: str | None) -> str:
    """Decides the type from the bytes themselves; the declared type is never trusted alone."""
    if data.startswith(b"%PDF-"):
        return "application/pdf"
    try:
        data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise IngestError("Unsupported file: upload an official PDF or a UTF-8 text file") from e
    if b"\x00" in data:
        raise IngestError("Unsupported file: binary content is not plain text")
    return "text/plain"


def extract_text(data: bytes, media_type: str) -> str:
    if media_type == "application/pdf":
        from pypdf import PdfReader
        from pypdf.errors import PdfReadError

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise IngestError("Encrypted PDFs cannot be processed")
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except PdfReadError as e:
            raise IngestError("The PDF could not be read") from e
    else:
        text = data.decode("utf-8")
    text = text.replace("\r\n", "\n").replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    if len(text.strip()) < MIN_TEXT_CHARS:
        raise IngestError(
            "Too little text could be extracted. This may be a scanned document; OCR arrives with Document Studio (Phase 5)."
        )
    return text


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# "35A. Heading of section.—(1) text"  (em dash, en dash or hyphen after the heading)
_STATUTE_RE = re.compile(r"^\s*(\d{1,4})([A-Z]{0,3})\.\s+([^\n]{2,300}?)\.?\s*[—–-]{1,2}\s*", re.M)
# "14. Paragraph text" for judgments
_PARA_RE = re.compile(r"^\s*(\d{1,4})\.\s+(?=\S)", re.M)


def _accept_sequence(matches: list[re.Match], number_of) -> list[re.Match]:
    """Keeps matches whose numbering moves forward sensibly. Rejects footnotes ("1. Subs. by Act...")
    and numbered lists that restart, which would otherwise be mistaken for sections."""
    kept: list[re.Match] = []
    last: tuple[int, str] | None = None
    for m in matches:
        num, suffix = number_of(m)
        if last is None or (num == last[0] and suffix > last[1]) or (last[0] < num <= last[0] + 5):
            kept.append(m)
            last = (num, suffix)
    return kept


def split_sections(text: str, source_type: str, title: str = "") -> list[ParsedSection]:
    unit = "Article" if "constitution" in title.lower() else "Section"
    sections: list[ParsedSection] = []
    if source_type == "judgment":
        ms = _accept_sequence(list(_PARA_RE.finditer(text)), lambda m: (int(m.group(1)), ""))
        for i, m in enumerate(ms):
            end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
            body = text[m.end():end].strip()
            if body:
                sections.append(ParsedSection(f"Para {m.group(1)}", m.group(1), "", body))
    else:
        ms = _accept_sequence(list(_STATUTE_RE.finditer(text)), lambda m: (int(m.group(1)), m.group(2)))
        for i, m in enumerate(ms):
            end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
            key = f"{m.group(1)}{m.group(2)}"
            sections.append(
                ParsedSection(f"{unit} {key}", key.lower(), m.group(3).strip(), text[m.end():end].strip())
            )
    if len(sections) >= 2:
        return sections
    # Fallback for guidance, notifications or unusual layouts: fixed-size parts on paragraph boundaries.
    parts, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if buf and len(buf) + len(para) > 1500:
            parts.append(buf)
            buf = ""
        buf = f"{buf}\n\n{para}".strip()
    if buf:
        parts.append(buf)
    return [ParsedSection(f"Part {i}", f"part{i}", "", p) for i, p in enumerate(parts, 1)]
