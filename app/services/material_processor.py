import hashlib
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.exceptions import (
    DocumentNotFoundError,
    DocumentProcessingError,
    EmptyDocumentError,
    UnsupportedFileTypeError,
)
from app.schemas.material import (
    DocumentChunk,
    ExtractedDocument,
    MaterialMetadata,
)

# Supported extensions
SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt"}

# Default chunking parameters
DEFAULT_CHUNK_SIZE = 1000
DEFAULT_CHUNK_OVERLAP = 200


class DocumentElement:
    """Intermediate representation of an extracted document block."""

    def __init__(
        self,
        text: str,
        page_number: Optional[int] = None,
        slide_number: Optional[int] = None,
        chapter: Optional[str] = None,
        section: Optional[str] = None,
        source_metadata: Optional[Dict[str, Any]] = None,
    ):
        self.text = text
        self.page_number = page_number
        self.slide_number = slide_number
        self.chapter = chapter
        self.section = section
        self.source_metadata = source_metadata or {}


class TextCleaner:
    """Deterministic text cleaner preserving formatting, punctuation, lists, and code."""

    @staticmethod
    def clean(text: str) -> str:
        if not text:
            return ""

        # Normalize line breaks to Unix style \n
        text = text.replace("\r\n", "\n").replace("\r", "\n")

        # Replace non-breaking spaces and tabs with standard space
        text = text.replace("\u00a0", " ").replace("\t", "    ")

        # Remove control characters except standard whitespace \n and \t
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

        # Normalize multiple horizontal spaces into single space, keeping newlines intact
        text = re.sub(r"[ \t]+", " ", text)

        # Strip trailing and leading whitespace per line
        lines = [line.strip() for line in text.split("\n")]

        # Collapse 3 or more consecutive newlines into 2
        cleaned_lines: List[str] = []
        consecutive_empty = 0
        for line in lines:
            if not line:
                consecutive_empty += 1
                if consecutive_empty <= 1:
                    cleaned_lines.append("")
            else:
                consecutive_empty = 0
                cleaned_lines.append(line)

        cleaned_text = "\n".join(cleaned_lines).strip()
        return cleaned_text


class PDFExtractor:
    """Extractor for Portable Document Format (PDF) files using PyMuPDF (fitz) with pypdf fallback."""

    @staticmethod
    def extract(file_path: Path) -> Tuple[List[DocumentElement], Dict[str, Any]]:
        elements: List[DocumentElement] = []
        metadata: Dict[str, Any] = {}

        # 1. Try PyMuPDF (fitz) as primary extractor
        try:
            import fitz
            doc = fitz.open(str(file_path))
            total_pages = len(doc)
            metadata = {
                "total_pages": total_pages,
                "pdf_encrypted": doc.is_encrypted,
                "extractor": "pymupdf",
            }
            current_chapter: Optional[str] = None
            current_section: Optional[str] = None

            for page_idx in range(total_pages):
                page_number = page_idx + 1
                try:
                    page = doc[page_idx]
                    raw_text = page.get_text("text") or ""
                except Exception:
                    raw_text = ""

                cleaned = TextCleaner.clean(raw_text)
                if not cleaned:
                    continue

                for line in cleaned.split("\n"):
                    line_clean = line.strip()
                    if re.match(r"^(Chapter\s+\d+|CHAPTER\s+[0-9IVXLCDM]+)", line_clean, re.IGNORECASE):
                        current_chapter = line_clean
                    elif re.match(r"^(Section\s+\d+(\.\d+)*|\d+\.\d+\s+[A-Za-z])", line_clean, re.IGNORECASE):
                        current_section = line_clean

                elements.append(
                    DocumentElement(
                        text=cleaned,
                        page_number=page_number,
                        chapter=current_chapter,
                        section=current_section,
                        source_metadata={"page_number": page_number, "total_pages": total_pages},
                    )
                )
            doc.close()
            if elements:
                return elements, metadata
        except Exception:
            # Fallback to pypdf if fitz encounters issues
            pass

        # 2. Fallback to pypdf
        try:
            from pypdf import PdfReader
            reader = PdfReader(str(file_path))
            total_pages = len(reader.pages)
            metadata = {
                "total_pages": total_pages,
                "pdf_encrypted": reader.is_encrypted,
                "extractor": "pypdf",
            }
            current_chapter = None
            current_section = None

            for page_idx, page in enumerate(reader.pages):
                page_number = page_idx + 1
                try:
                    raw_text = page.extract_text() or ""
                except Exception as e:
                    raise DocumentProcessingError(f"Failed to extract text from PDF page {page_number}: {e}") from e

                cleaned = TextCleaner.clean(raw_text)
                if not cleaned:
                    continue

                for line in cleaned.split("\n"):
                    line_clean = line.strip()
                    if re.match(r"^(Chapter\s+\d+|CHAPTER\s+[0-9IVXLCDM]+)", line_clean, re.IGNORECASE):
                        current_chapter = line_clean
                    elif re.match(r"^(Section\s+\d+(\.\d+)*|\d+\.\d+\s+[A-Za-z])", line_clean, re.IGNORECASE):
                        current_section = line_clean

                elements.append(
                    DocumentElement(
                        text=cleaned,
                        page_number=page_number,
                        chapter=current_chapter,
                        section=current_section,
                        source_metadata={"page_number": page_number, "total_pages": total_pages},
                    )
                )

            return elements, metadata
        except Exception as e:
            raise DocumentProcessingError(f"Failed to extract text from PDF file: {e}") from e


class DocxExtractor:
    """Extractor for Microsoft Word (DOCX) files using python-docx."""

    @staticmethod
    def extract(file_path: Path) -> Tuple[List[DocumentElement], Dict[str, Any]]:
        try:
            import docx
            doc = docx.Document(str(file_path))
        except Exception as e:
            raise DocumentProcessingError(f"Failed to read DOCX file: {e}") from e

        elements: List[DocumentElement] = []
        current_chapter: Optional[str] = None
        current_section: Optional[str] = None
        heading_count = 0

        for para in doc.paragraphs:
            raw_text = para.text
            cleaned = TextCleaner.clean(raw_text)
            if not cleaned:
                continue

            style_name = (para.style.name if para.style else "").lower()

            # Detect chapter / headings from Word styles
            if "heading 1" in style_name or "title" in style_name:
                current_chapter = cleaned
                current_section = None
                heading_count += 1
                elements.append(
                    DocumentElement(
                        text=cleaned,
                        chapter=current_chapter,
                        section=current_section,
                        source_metadata={"style": para.style.name, "is_heading": True, "heading_level": 1},
                    )
                )
            elif "heading 2" in style_name or "heading 3" in style_name or "subtitle" in style_name:
                current_section = cleaned
                heading_count += 1
                elements.append(
                    DocumentElement(
                        text=cleaned,
                        chapter=current_chapter,
                        section=current_section,
                        source_metadata={"style": para.style.name, "is_heading": True, "heading_level": 2},
                    )
                )
            else:
                # Detect pattern-based headings if styles are generic
                if re.match(r"^(Chapter\s+\d+|CHAPTER\s+[0-9IVXLCDM]+)", cleaned, re.IGNORECASE):
                    current_chapter = cleaned
                    heading_count += 1
                elif re.match(r"^(Section\s+\d+(\.\d+)*|\d+\.\d+\s+[A-Za-z])", cleaned, re.IGNORECASE):
                    current_section = cleaned
                    heading_count += 1

                elements.append(
                    DocumentElement(
                        text=cleaned,
                        chapter=current_chapter,
                        section=current_section,
                        source_metadata={"style": getattr(para.style, "name", "Normal"), "is_heading": False},
                    )
                )

        # Also extract table text if present
        for table_idx, table in enumerate(doc.tables):
            table_rows: List[str] = []
            for row in table.rows:
                row_cells = [TextCleaner.clean(cell.text) for cell in row.cells]
                row_str = " | ".join(filter(None, row_cells))
                if row_str:
                    table_rows.append(row_str)
            if table_rows:
                table_text = "\n".join(table_rows)
                elements.append(
                    DocumentElement(
                        text=table_text,
                        chapter=current_chapter,
                        section=current_section,
                        source_metadata={"is_table": True, "table_index": table_idx + 1},
                    )
                )

        metadata = {
            "total_paragraphs": len(doc.paragraphs),
            "total_tables": len(doc.tables),
            "total_headings": heading_count,
        }
        return elements, metadata


class PPTXExtractor:
    """Extractor for Microsoft PowerPoint (PPTX) files using python-pptx."""

    @staticmethod
    def extract(file_path: Path) -> Tuple[List[DocumentElement], Dict[str, Any]]:
        try:
            from pptx import Presentation
            prs = Presentation(str(file_path))
        except Exception as e:
            raise DocumentProcessingError(f"Failed to read PPTX file: {e}") from e

        elements: List[DocumentElement] = []
        total_slides = len(prs.slides)

        for slide_idx, slide in enumerate(prs.slides):
            slide_number = slide_idx + 1
            slide_title: Optional[str] = None
            slide_texts: List[str] = []

            # Extract slide title if present
            if slide.shapes.title and slide.shapes.title.has_text_frame:
                title_text = TextCleaner.clean(slide.shapes.title.text)
                if title_text:
                    slide_title = title_text

            # Extract text from all shapes
            for shape in slide.shapes:
                if shape == slide.shapes.title:
                    continue
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        p_text = TextCleaner.clean(paragraph.text)
                        if p_text:
                            slide_texts.append(p_text)
                elif shape.has_table:
                    for row in shape.table.rows:
                        row_cells = [TextCleaner.clean(cell.text) for cell in row.cells]
                        row_str = " | ".join(filter(None, row_cells))
                        if row_str:
                            slide_texts.append(row_str)

            # Combine slide title and body text
            combined_parts = []
            if slide_title:
                combined_parts.append(slide_title)
            if slide_texts:
                combined_parts.extend(slide_texts)

            if combined_parts:
                slide_content = "\n".join(combined_parts)
                elements.append(
                    DocumentElement(
                        text=slide_content,
                        slide_number=slide_number,
                        section=slide_title,
                        source_metadata={
                            "slide_number": slide_number,
                            "total_slides": total_slides,
                            "slide_title": slide_title,
                        },
                    )
                )

        metadata = {
            "total_slides": total_slides,
        }
        return elements, metadata


class TXTExtractor:
    """Extractor for plain text (TXT) documents."""

    @staticmethod
    def extract(file_path: Path) -> Tuple[List[DocumentElement], Dict[str, Any]]:
        content = None
        for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(file_path, "r", encoding=encoding) as f:
                    content = f.read()
                break
            except (UnicodeDecodeError, LookupError):
                continue

        if content is None:
            raise DocumentProcessingError(f"Unable to decode text file: {file_path}")

        paragraphs = re.split(r"\n\s*\n", content)
        elements: List[DocumentElement] = []
        current_chapter: Optional[str] = None
        current_section: Optional[str] = None
        total_sections = 0

        for para in paragraphs:
            cleaned = TextCleaner.clean(para)
            if not cleaned:
                continue

            lines = cleaned.split("\n")
            first_line = lines[0].strip()

            if first_line.startswith("# ") or re.match(r"^(Chapter\s+\d+|CHAPTER\s+[0-9IVXLCDM]+)", first_line, re.IGNORECASE):
                current_chapter = first_line.lstrip("# ").strip()
                current_section = None
                total_sections += 1
            elif first_line.startswith("## ") or first_line.startswith("### ") or re.match(r"^(Section\s+\d+|\d+\.\d+)", first_line, re.IGNORECASE):
                current_section = first_line.lstrip("#").strip()
                total_sections += 1

            elements.append(
                DocumentElement(
                    text=cleaned,
                    chapter=current_chapter,
                    section=current_section,
                    source_metadata={"line_count": len(lines)},
                )
            )

        metadata = {
            "total_paragraphs": len(elements),
            "total_sections": total_sections,
        }
        return elements, metadata


class TextChunker:
    """Deterministic document chunker with structural boundary preference."""

    def __init__(self, chunk_size: int = DEFAULT_CHUNK_SIZE, chunk_overlap: int = DEFAULT_CHUNK_OVERLAP):
        if chunk_size <= 0:
            raise ValueError("chunk_size must be a positive integer")
        if chunk_overlap < 0:
            raise ValueError("chunk_overlap must be non-negative")
        if chunk_overlap >= chunk_size:
            raise ValueError("chunk_overlap must be strictly less than chunk_size")

        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _split_into_sentences(self, text: str) -> List[str]:
        """Split text into sentences using punctuation boundaries."""
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    def _split_large_text(self, text: str) -> List[str]:
        """Split a large text exceeding chunk_size into overlapping segments respecting sentences."""
        if len(text) <= self.chunk_size:
            return [text]

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if len(paragraphs) > 1:
            chunks = []
            curr_para_chunk = ""
            for p in paragraphs:
                if not curr_para_chunk:
                    curr_para_chunk = p
                elif len(curr_para_chunk) + len(p) + 2 <= self.chunk_size:
                    curr_para_chunk += "\n\n" + p
                else:
                    chunks.extend(self._split_large_text(curr_para_chunk))
                    curr_para_chunk = p
            if curr_para_chunk:
                chunks.extend(self._split_large_text(curr_para_chunk))
            return chunks

        sentences = self._split_into_sentences(text)
        if not sentences or (len(sentences) == 1 and len(sentences[0]) > self.chunk_size):
            chunks = []
            step = max(1, self.chunk_size - self.chunk_overlap)
            for i in range(0, len(text), step):
                chunk = text[i : i + self.chunk_size].strip()
                if chunk:
                    chunks.append(chunk)
                if i + self.chunk_size >= len(text):
                    break
            return chunks

        chunks = []
        curr_sentences: List[str] = []
        curr_len = 0

        for sentence in sentences:
            s_len = len(sentence)
            if s_len > self.chunk_size:
                if curr_sentences:
                    chunks.append(" ".join(curr_sentences))
                    curr_sentences = []
                    curr_len = 0
                step = max(1, self.chunk_size - self.chunk_overlap)
                for i in range(0, s_len, step):
                    sub = sentence[i : i + self.chunk_size].strip()
                    if sub:
                        chunks.append(sub)
                    if i + self.chunk_size >= s_len:
                        break
                continue

            if curr_len + s_len + (1 if curr_len > 0 else 0) <= self.chunk_size:
                curr_sentences.append(sentence)
                curr_len += s_len + (1 if curr_len > 0 else 0)
            else:
                if curr_sentences:
                    chunks.append(" ".join(curr_sentences))

                overlap_sentences: List[str] = []
                overlap_len = 0
                for s in reversed(curr_sentences):
                    if overlap_len + len(s) + 1 <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_len += len(s) + 1
                    else:
                        break

                curr_sentences = overlap_sentences + [sentence]
                curr_len = sum(len(s) for s in curr_sentences) + max(0, len(curr_sentences) - 1)

        if curr_sentences:
            chunks.append(" ".join(curr_sentences))

        return chunks

    def chunk_elements(
        self,
        elements: List[DocumentElement],
        material_id: str,
        filename: str,
        file_type: str,
    ) -> List[DocumentChunk]:
        """
        Group and split document elements respecting structural boundaries:
        Chapter -> Section -> Page/Slide -> Paragraph -> Sentence -> Size.
        """
        chunks: List[DocumentChunk] = []
        chunk_index = 0

        if not elements:
            return chunks

        current_group: List[DocumentElement] = []
        current_context: Tuple[Any, Any, Any, Any] = (None, None, None, None)

        def flush_group(group: List[DocumentElement]):
            nonlocal chunk_index
            if not group:
                return

            first_elem = group[0]
            combined_paragraphs = [e.text.strip() for e in group if e.text.strip()]
            if not combined_paragraphs:
                return

            curr_text_buffer: List[str] = []
            curr_buffer_len = 0

            for para in combined_paragraphs:
                para_len = len(para)
                if para_len > self.chunk_size:
                    if curr_text_buffer:
                        buf_text = "\n\n".join(curr_text_buffer)
                        for seg in self._split_large_text(buf_text):
                            chunk_id = self._make_chunk_id(material_id, chunk_index, seg)
                            chunks.append(
                                DocumentChunk(
                                    chunk_id=chunk_id,
                                    material_id=material_id,
                                    filename=filename,
                                    file_type=file_type,
                                    chunk_index=chunk_index,
                                    text=seg,
                                    chapter=first_elem.chapter,
                                    section=first_elem.section,
                                    page_number=first_elem.page_number,
                                    slide_number=first_elem.slide_number,
                                    source_metadata=dict(first_elem.source_metadata),
                                )
                            )
                            chunk_index += 1
                        curr_text_buffer = []
                        curr_buffer_len = 0

                    for seg in self._split_large_text(para):
                        chunk_id = self._make_chunk_id(material_id, chunk_index, seg)
                        chunks.append(
                            DocumentChunk(
                                chunk_id=chunk_id,
                                material_id=material_id,
                                filename=filename,
                                file_type=file_type,
                                chunk_index=chunk_index,
                                text=seg,
                                chapter=first_elem.chapter,
                                section=first_elem.section,
                                page_number=first_elem.page_number,
                                slide_number=first_elem.slide_number,
                                source_metadata=dict(first_elem.source_metadata),
                            )
                        )
                        chunk_index += 1
                elif curr_buffer_len + para_len + (2 if curr_buffer_len > 0 else 0) <= self.chunk_size:
                    curr_text_buffer.append(para)
                    curr_buffer_len += para_len + (2 if curr_buffer_len > 0 else 0)
                else:
                    buf_text = "\n\n".join(curr_text_buffer)
                    for seg in self._split_large_text(buf_text):
                        chunk_id = self._make_chunk_id(material_id, chunk_index, seg)
                        chunks.append(
                            DocumentChunk(
                                chunk_id=chunk_id,
                                material_id=material_id,
                                filename=filename,
                                file_type=file_type,
                                chunk_index=chunk_index,
                                text=seg,
                                chapter=first_elem.chapter,
                                section=first_elem.section,
                                page_number=first_elem.page_number,
                                slide_number=first_elem.slide_number,
                                source_metadata=dict(first_elem.source_metadata),
                            )
                        )
                        chunk_index += 1
                    curr_text_buffer = [para]
                    curr_buffer_len = para_len

            if curr_text_buffer:
                buf_text = "\n\n".join(curr_text_buffer)
                for seg in self._split_large_text(buf_text):
                    chunk_id = self._make_chunk_id(material_id, chunk_index, seg)
                    chunks.append(
                        DocumentChunk(
                            chunk_id=chunk_id,
                            material_id=material_id,
                            filename=filename,
                            file_type=file_type,
                            chunk_index=chunk_index,
                            text=seg,
                            chapter=first_elem.chapter,
                            section=first_elem.section,
                            page_number=first_elem.page_number,
                            slide_number=first_elem.slide_number,
                            source_metadata=dict(first_elem.source_metadata),
                        )
                    )
                    chunk_index += 1

        for elem in elements:
            context = (elem.chapter, elem.section, elem.page_number, elem.slide_number)
            if not current_group:
                current_group.append(elem)
                current_context = context
            elif context == current_context:
                current_group.append(elem)
            else:
                flush_group(current_group)
                current_group = [elem]
                current_context = context

        if current_group:
            flush_group(current_group)

        return chunks

    @staticmethod
    def _make_chunk_id(material_id: str, chunk_index: int, text_segment: str) -> str:
        content_hash = hashlib.sha256(
            f"{material_id}:{chunk_index}:{text_segment}".encode("utf-8")
        ).hexdigest()[:20]
        return f"chk_{material_id[:8]}_{chunk_index:04d}_{content_hash[:8]}"


class MaterialProcessor:
    """Core document processing service for PDF, DOCX, PPTX, and TXT materials."""

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)

    @staticmethod
    def _generate_material_id(file_path: Path, file_size: int) -> str:
        """Generate a deterministic material ID based on filename, size, and complete file content."""
        hasher = hashlib.sha256()
        hasher.update(file_path.name.encode("utf-8"))
        hasher.update(str(file_size).encode("utf-8"))
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
        except Exception:
            pass
        return f"mat_{hasher.hexdigest()[:16]}"


    def process_document(
        self,
        file_path: Union[str, Path],
        material_id: Optional[str] = None,
    ) -> ExtractedDocument:
        """
        Process a single document file through validation, extraction, cleaning, chunking, and metadata preservation.
        """
        path = Path(file_path).resolve()

        # 1. Validate file existence
        if not path.exists() or not path.is_file():
            raise DocumentNotFoundError(f"Document not found at path: {path}")

        # 2. Detect file type
        suffix = path.suffix.lower()
        if suffix not in SUPPORTED_EXTENSIONS:
            raise UnsupportedFileTypeError(
                f"Unsupported file format '{suffix}'. Supported formats are: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
            )

        file_type = suffix.lstrip(".")
        file_size = path.stat().st_size

        if file_size == 0:
            raise EmptyDocumentError(f"Document is empty (0 bytes): {path.name}")

        mat_id = material_id or self._generate_material_id(path, file_size)

        # 3. Extract text elements using modular extractors
        if suffix == ".pdf":
            elements, format_meta = PDFExtractor.extract(path)
        elif suffix == ".docx":
            elements, format_meta = DocxExtractor.extract(path)
        elif suffix == ".pptx":
            elements, format_meta = PPTXExtractor.extract(path)
        elif suffix == ".txt":
            elements, format_meta = TXTExtractor.extract(path)
        else:
            raise UnsupportedFileTypeError(f"Unhandled file extension: {suffix}")

        # 4. Check for empty extraction
        total_extracted_text = "".join(elem.text for elem in elements).strip()
        if not total_extracted_text:
            raise EmptyDocumentError(
                f"Document '{path.name}' yielded no extractable text. Note: Scanned PDFs without OCR are not readable."
            )

        # 5. Chunk the content deterministically
        chunks = self.chunker.chunk_elements(
            elements=elements,
            material_id=mat_id,
            filename=path.name,
            file_type=file_type,
        )

        if not chunks:
            raise EmptyDocumentError(f"No chunks could be produced for document '{path.name}'")

        # 6. Build summary metadata
        raw_text_combined = "\n\n".join(elem.text for elem in elements)
        total_sections = sum(1 for e in elements if e.section or e.chapter)

        metadata = MaterialMetadata(
            material_id=mat_id,
            filename=path.name,
            file_type=file_type,
            file_size_bytes=file_size,
            total_pages=format_meta.get("total_pages"),
            total_slides=format_meta.get("total_slides"),
            total_sections=format_meta.get("total_headings") or format_meta.get("total_sections") or (total_sections if total_sections > 0 else None),
            total_chunks=len(chunks),
            source_metadata=format_meta,
        )

        return ExtractedDocument(
            material_id=mat_id,
            filename=path.name,
            file_type=file_type,
            metadata=metadata,
            chunks=chunks,
            raw_text=raw_text_combined,
        )


def process_document(
    file_path: Union[str, Path],
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    material_id: Optional[str] = None,
) -> ExtractedDocument:
    """Convenience top-level function for processing a document."""
    processor = MaterialProcessor(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    return processor.process_document(file_path=file_path, material_id=material_id)
