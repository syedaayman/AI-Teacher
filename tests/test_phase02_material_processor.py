import io
from pathlib import Path
import pytest
from pypdf import PdfWriter
import docx
from pptx import Presentation
from pptx.util import Inches

from app.core.exceptions import (
    DocumentNotFoundError,
    EmptyDocumentError,
    UnsupportedFileTypeError,
)
from app.services.material_processor import (
    DocxExtractor,
    MaterialProcessor,
    PDFExtractor,
    PPTXExtractor,
    TXTExtractor,
    TextCleaner,
    process_document,
)


def create_minimal_pdf_bytes(pages_content: list[list[str]]) -> bytes:
    """Create a minimal valid multi-page PDF binary with text content."""
    page_count = len(pages_content)
    page_obj_ids = [3 + i * 2 for i in range(page_count)]
    content_obj_ids = [4 + i * 2 for i in range(page_count)]
    font_obj_id = 3 + page_count * 2

    catalog = "1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
    kids_str = " ".join(f"{pid} 0 R" for pid in page_obj_ids)
    pages_obj = f"2 0 obj\n<< /Type /Pages /Kids [{kids_str}] /Count {page_count} >>\nendobj\n"

    body_parts = [catalog, pages_obj]

    for i, lines in enumerate(pages_content):
        pid = page_obj_ids[i]
        cid = content_obj_ids[i]
        page_entry = (
            f"{pid} 0 obj\n"
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Contents {cid} 0 R /Resources << /Font << /F1 {font_obj_id} 0 R >> >> >>\nendobj\n"
        )
        stream_text = "BT\n/F1 12 Tf\n100 700 Td\n"
        for line_idx, line in enumerate(lines):
            safe_line = line.replace("(", "\\(").replace(")", "\\)")
            if line_idx > 0:
                stream_text += "0 -20 Td\n"
            stream_text += f"({safe_line}) Tj\n"
        stream_text += "ET\n"

        stream_bytes = stream_text.encode("latin1")
        content_entry = (
            f"{cid} 0 obj\n"
            f"<< /Length {len(stream_bytes)} >>\n"
            f"stream\n{stream_text}endstream\nendobj\n"
        )
        body_parts.extend([page_entry, content_entry])

    font_entry = f"{font_obj_id} 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n"
    body_parts.append(font_entry)

    header = "%PDF-1.4\n"
    offsets = [0]
    curr_offset = len(header)
    for part in body_parts:
        offsets.append(curr_offset)
        curr_offset += len(part.encode("latin1"))

    total_objs = len(body_parts) + 1
    xref = f"xref\n0 {total_objs}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        xref += f"{off:010d} 00000 n \n"

    trailer = f"trailer\n<< /Size {total_objs} /Root 1 0 R >>\nstartxref\n{curr_offset}\n%%EOF\n"

    full_pdf = header + "".join(body_parts) + xref + trailer
    return full_pdf.encode("latin1")


@pytest.fixture(scope="module")
def fixture_dir(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("fixtures")


@pytest.fixture(scope="module")
def sample_txt_file(fixture_dir: Path) -> Path:
    """Fixture providing a formatted TXT document."""
    txt_path = fixture_dir / "sample_doc.txt"
    content = (
        "# Chapter 1: Introduction to AI\n\n"
        "Artificial Intelligence represents a major milestone in computational science.\n"
        "It includes machine learning, neural networks, and expert systems.\n\n"
        "## Section 1.1: Foundations\n\n"
        "Modern deep learning is based on multi-layer artificial neural networks.\n"
        "Transformers utilize self-attention mechanisms to process sequence data efficiently."
    )
    txt_path.write_text(content, encoding="utf-8")
    return txt_path


@pytest.fixture(scope="module")
def sample_docx_file(fixture_dir: Path) -> Path:
    """Fixture providing a structured DOCX document with headings."""
    docx_path = fixture_dir / "sample_doc.docx"
    doc = docx.Document()
    doc.add_heading("Chapter 2: Neural Networks", level=1)
    doc.add_paragraph("Neural networks consist of interconnected layers of artificial nodes.")
    doc.add_heading("Section 2.1: Backpropagation", level=2)
    doc.add_paragraph("Backpropagation calculates the gradient of the loss function with respect to weights.")
    doc.save(str(docx_path))
    return docx_path


@pytest.fixture(scope="module")
def sample_pptx_file(fixture_dir: Path) -> Path:
    """Fixture providing a structured PPTX presentation."""
    pptx_path = fixture_dir / "sample_presentation.pptx"
    prs = Presentation()

    # Slide 1 (Title slide)
    title_layout = prs.slide_layouts[0]
    slide1 = prs.slides.add_slide(title_layout)
    slide1.shapes.title.text = "AI System Overview"
    slide1.placeholders[1].text = "An introductory guide to generative intelligence."

    # Slide 2 (Content slide)
    bullet_layout = prs.slide_layouts[1]
    slide2 = prs.slides.add_slide(bullet_layout)
    slide2.shapes.title.text = "Key Components"
    tf = slide2.shapes.placeholders[1].text_frame
    tf.text = "1. Material Processing Pipeline"
    p = tf.add_paragraph()
    p.text = "2. Vector Retrieval Engine"

    prs.save(str(pptx_path))
    return pptx_path


@pytest.fixture(scope="module")
def sample_pdf_file(fixture_dir: Path) -> Path:
    """Fixture providing a 2-page PDF document."""
    pdf_path = fixture_dir / "sample_doc.pdf"
    pdf_bytes = create_minimal_pdf_bytes([
        ["Chapter 1: Quantum Computing", "Quantum computing leverages qubits and superposition."],
        ["Section 1.1: Quantum Entanglement", "Entanglement allows correlation between distinct particles."]
    ])
    pdf_path.write_bytes(pdf_bytes)
    return pdf_path


def test_01_txt_extraction_and_chunking(sample_txt_file: Path):
    """Verify TXT file is processed and chunks are created with section context."""
    doc = process_document(sample_txt_file)
    assert doc.filename == "sample_doc.txt"
    assert doc.file_type == "txt"
    assert len(doc.chunks) >= 2
    assert doc.metadata.total_chunks == len(doc.chunks)
    assert any("Introduction to AI" in (c.chapter or "") for c in doc.chunks)
    assert any("Foundations" in (c.section or "") for c in doc.chunks)


def test_02_docx_extraction_and_metadata(sample_docx_file: Path):
    """Verify DOCX headings and paragraphs are extracted with proper chapter/section."""
    doc = process_document(sample_docx_file)
    assert doc.filename == "sample_doc.docx"
    assert doc.file_type == "docx"
    assert len(doc.chunks) >= 2
    assert any(c.chapter == "Chapter 2: Neural Networks" for c in doc.chunks)
    assert any(c.section == "Section 2.1: Backpropagation" for c in doc.chunks)


def test_03_pptx_extraction_and_slide_metadata(sample_pptx_file: Path):
    """Verify PPTX slide numbers and titles are extracted and attached to chunks."""
    doc = process_document(sample_pptx_file)
    assert doc.filename == "sample_presentation.pptx"
    assert doc.file_type == "pptx"
    assert doc.metadata.total_slides == 2

    slide_numbers = [c.slide_number for c in doc.chunks if c.slide_number is not None]
    assert 1 in slide_numbers
    assert 2 in slide_numbers
    assert any("AI System Overview" in c.text for c in doc.chunks)
    assert any("Material Processing Pipeline" in c.text for c in doc.chunks)


def test_04_pdf_extraction_and_page_metadata(sample_pdf_file: Path):
    """Verify PDF multi-page extraction preserves 1-based page numbers."""
    doc = process_document(sample_pdf_file)
    assert doc.filename == "sample_doc.pdf"
    assert doc.file_type == "pdf"
    assert doc.metadata.total_pages == 2

    page_numbers = [c.page_number for c in doc.chunks if c.page_number is not None]
    assert 1 in page_numbers
    assert 2 in page_numbers
    assert any("Quantum Computing" in c.text for c in doc.chunks)


def test_05_unsupported_file_rejection(tmp_path: Path):
    """Verify unsupported file extensions raise UnsupportedFileTypeError."""
    unsupported = tmp_path / "image.png"
    unsupported.write_bytes(b"\x89PNG\r\n\x1a\n")
    with pytest.raises(UnsupportedFileTypeError) as exc:
        process_document(unsupported)
    assert "Unsupported file format" in str(exc.value)


def test_06_missing_file_handling(tmp_path: Path):
    """Verify non-existent file path raises DocumentNotFoundError."""
    missing = tmp_path / "does_not_exist.pdf"
    with pytest.raises(DocumentNotFoundError) as exc:
        process_document(missing)
    assert "Document not found" in str(exc.value)


def test_07_empty_document_handling(tmp_path: Path):
    """Verify empty document raises EmptyDocumentError."""
    empty_txt = tmp_path / "empty.txt"
    empty_txt.write_text("", encoding="utf-8")
    with pytest.raises(EmptyDocumentError) as exc:
        process_document(empty_txt)
    assert "empty" in str(exc.value).lower()


def test_08_pdf_page_metadata_preserved_in_all_chunks(sample_pdf_file: Path):
    """Verify every chunk extracted from PDF has page_number set and valid source_metadata."""
    doc = process_document(sample_pdf_file)
    for chunk in doc.chunks:
        assert chunk.page_number is not None
        assert chunk.page_number in [1, 2]
        assert "page_number" in chunk.source_metadata


def test_09_pptx_slide_metadata_preserved_in_all_chunks(sample_pptx_file: Path):
    """Verify every chunk extracted from PPTX has slide_number and total_slides metadata."""
    doc = process_document(sample_pptx_file)
    for chunk in doc.chunks:
        assert chunk.slide_number is not None
        assert chunk.slide_number in [1, 2]
        assert chunk.source_metadata.get("total_slides") == 2


def test_10_docx_heading_and_section_metadata(sample_docx_file: Path):
    """Verify DOCX chunking retains hierarchical heading styles."""
    doc = process_document(sample_docx_file)
    section_chunks = [c for c in doc.chunks if c.section == "Section 2.1: Backpropagation"]
    assert len(section_chunks) > 0
    assert section_chunks[0].chapter == "Chapter 2: Neural Networks"


def test_11_deterministic_chunk_ids(sample_txt_file: Path):
    """Verify repeated runs on the same document generate identical chunk IDs."""
    doc1 = process_document(sample_txt_file)
    doc2 = process_document(sample_txt_file)

    assert doc1.material_id == doc2.material_id
    assert len(doc1.chunks) == len(doc2.chunks)
    for c1, c2 in zip(doc1.chunks, doc2.chunks):
        assert c1.chunk_id == c2.chunk_id
        assert c1.chunk_index == c2.chunk_index
        assert c1.text == c2.text


def test_12_deterministic_chunk_ordering(sample_docx_file: Path):
    """Verify chunk_index is strictly sequential starting from 0."""
    doc = process_document(sample_docx_file)
    indices = [c.chunk_index for c in doc.chunks]
    assert indices == list(range(len(doc.chunks)))


def test_13_metadata_survives_chunking(sample_pptx_file: Path):
    """Verify all chunk attributes maintain filename, file_type, and material_id."""
    doc = process_document(sample_pptx_file)
    for chunk in doc.chunks:
        assert chunk.filename == doc.filename
        assert chunk.file_type == "pptx"
        assert chunk.material_id == doc.material_id
        assert isinstance(chunk.source_metadata, dict)


def test_14_chunk_size_configuration(tmp_path: Path):
    """Verify smaller chunk_size generates more chunks for large text."""
    long_txt = tmp_path / "long_doc.txt"
    sentences = [f"This is informative sentence number {i} detailing system specifications." for i in range(50)]
    long_txt.write_text("\n\n".join(sentences), encoding="utf-8")

    doc_large = process_document(long_txt, chunk_size=1000, chunk_overlap=100)
    doc_small = process_document(long_txt, chunk_size=200, chunk_overlap=50)

    assert len(doc_small.chunks) > len(doc_large.chunks)
    assert all(len(c.text) <= 250 for c in doc_small.chunks)


def test_15_text_cleaner_behavior():
    """Verify TextCleaner normalizes whitespace and line breaks without destroying formulas/punctuation."""
    dirty_text = "E = mc^2\r\n\r\n\r\n\r\n  f(x)   =  a*x^2 + b*x + c  \n\n\t1. First item"
    cleaned = TextCleaner.clean(dirty_text)
    assert "E = mc^2" in cleaned
    assert "f(x) = a*x^2 + b*x + c" in cleaned
    assert "1. First item" in cleaned
    assert "\r" not in cleaned
    assert "\n\n\n" not in cleaned


def test_16_material_id_full_content_determinism(tmp_path: Path):
    """Verify identical file content generates identical material_id on separate runs."""
    doc_path = tmp_path / "test_doc.txt"
    doc_path.write_text("Deterministic content for material ID test.", encoding="utf-8")

    doc1 = process_document(doc_path)
    doc2 = process_document(doc_path)

    assert doc1.material_id == doc2.material_id
    assert doc1.material_id.startswith("mat_")


def test_17_material_id_differs_for_different_content(tmp_path: Path):
    """Verify different file content produces distinct material_id even with identical size and past-64KB variance."""
    # Create two 70KB files with identical filename and size, differing only past the 64KB mark
    base_padding = "A" * (65536 + 100)
    content1 = base_padding + "X"
    content2 = base_padding + "Y"

    file1 = tmp_path / "content1.txt"
    file2 = tmp_path / "content2.txt"

    file1.write_text(content1, encoding="utf-8")
    file2.write_text(content2, encoding="utf-8")

    doc1 = process_document(file1)
    doc2 = process_document(file2)

    assert doc1.material_id != doc2.material_id

