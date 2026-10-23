"""A1 - PDF parsing: text per page, chunking, embedded images with captions."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pymupdf

from .config import settings


@dataclass
class Chunk:
    id: str
    doc_id: str
    file_name: str
    page: int
    text: str


@dataclass
class ImageItem:
    id: str
    doc_id: str
    file_name: str
    page: int
    figure_label: str
    caption: str
    context_text: str
    path: str  # absolute path on disk


@dataclass
class ParsedDoc:
    pages: int = 0
    chunks: list[Chunk] = field(default_factory=list)
    images: list[ImageItem] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    failed: bool = False


_CAPTION = re.compile(r"(?im)^\s*((?:fig(?:ure)?\.?)\s*(\d+[a-z]?)\s*[.:\-]?[^\n]{0,200})")


def split_text(text: str, size: int, overlap: int) -> list[str]:
    """Split text into chunks of ~size characters with overlap, preferring sentence ends."""
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        return []
    out, start, n = [], 0, len(text)
    while start < n:
        end = min(start + size, n)
        if end < n:
            window_start = start + int(size * 0.6)
            cut = max(text.rfind(". ", window_start, end), text.rfind("\n", window_start, end))
            if cut == -1:
                cut = text.rfind(" ", window_start, end)
            if cut != -1:
                end = cut + 1
        piece = text[start:end].strip()
        if piece:
            out.append(piece)
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return out


def parse_pdf(path: str | Path, doc_id: str, file_name: str,
              images_dir: Path | None = None) -> ParsedDoc:
    res = ParsedDoc()
    images_dir = Path(images_dir or settings.images_dir)
    try:
        doc = pymupdf.open(str(path))
    except Exception as e:  # noqa: BLE001
        res.failed = True
        res.errors.append(f"Cannot open PDF (corrupted or not a PDF): {e}")
        return res
    try:
        if doc.needs_pass:
            res.failed = True
            res.errors.append("The PDF is password protected.")
            return res
        res.pages = doc.page_count
        out_dir = images_dir / doc_id
        total_chars = 0
        seen_xrefs: set[int] = set()
        for pno in range(doc.page_count):
            page = doc[pno]
            try:
                text = page.get_text("text") or ""
            except Exception as e:  # noqa: BLE001
                res.errors.append(f"Page {pno + 1}: text extraction failed ({e})")
                continue
            total_chars += len(text.strip())
            for i, piece in enumerate(split_text(text, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)):
                res.chunks.append(Chunk(id=f"{doc_id}:{pno + 1}:{i}", doc_id=doc_id,
                                        file_name=file_name, page=pno + 1, text=piece))
            try:
                _extract_images(doc, page, pno + 1, text, doc_id, file_name, out_dir, seen_xrefs, res)
            except Exception as e:  # noqa: BLE001
                res.errors.append(f"Page {pno + 1}: image extraction failed ({e})")
        if total_chars == 0:
            res.failed = True
            res.errors.append("No extractable text: the PDF looks scanned (OCR is not enabled).")
    finally:
        doc.close()
    return res


def _extract_images(doc, page, pno, text, doc_id, file_name, out_dir, seen, res: ParsedDoc) -> None:
    captions = [(m.group(1).strip(), f"Figure {m.group(2)}") for m in _CAPTION.finditer(text)]
    ctx = re.sub(r"\s+", " ", text).strip()[:500]
    n = 0
    for xref, *_ in page.get_images(full=True):
        if xref in seen:
            continue
        info = doc.extract_image(xref)
        if not info:
            continue
        if min(info["width"], info["height"]) < settings.MIN_IMAGE_PX:
            continue  # logos, icons, rules (A1.3)
        seen.add(xref)
        out_dir.mkdir(parents=True, exist_ok=True)
        fpath = out_dir / f"p{pno}_i{n}.{info.get('ext', 'png')}"
        fpath.write_bytes(info["image"])
        cap, label = captions[n] if n < len(captions) else (captions[0] if captions else ("", f"Image p.{pno}"))
        res.images.append(ImageItem(id=f"{doc_id}:img:{pno}:{n}", doc_id=doc_id, file_name=file_name,
                                    page=pno, figure_label=label, caption=cap,
                                    context_text=(cap + " " + ctx).strip(), path=str(fpath)))
        n += 1
    # vector diagrams: no raster image but a figure caption and many drawing operators
    if n == 0 and captions:
        try:
            if len(page.get_drawings()) >= 8:
                out_dir.mkdir(parents=True, exist_ok=True)
                fpath = out_dir / f"p{pno}_page.png"
                page.get_pixmap(dpi=110).save(str(fpath))
                cap, label = captions[0]
                res.images.append(ImageItem(id=f"{doc_id}:img:{pno}:v", doc_id=doc_id, file_name=file_name,
                                            page=pno, figure_label=label, caption=cap,
                                            context_text=(cap + " " + ctx).strip(), path=str(fpath)))
        except Exception:  # noqa: BLE001
            pass
