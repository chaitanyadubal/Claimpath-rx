"""
backend/ingestion/pdf_parser.py
Medical policy PDF parser using Docling (primary) + pdfplumber fallback.
"""
import logging
from pathlib import Path
import pdfplumber

logger = logging.getLogger(__name__)


class PolicyPDFParser:
    def __init__(self):
        self._docling_ok = self._check_docling()

    def _check_docling(self) -> bool:
        try:
            from docling.document_converter import DocumentConverter
            return True
        except ImportError:
            logger.warning("Docling not available — using pdfplumber")
            return False

    def parse(self, file_path: str | Path) -> dict:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Not found: {file_path}")
        if self._docling_ok:
            try:
                return self._parse_docling(path)
            except Exception as e:
                logger.warning(f"Docling failed ({e}), fallback to pdfplumber")
        return self._parse_pdfplumber(path)

    def _parse_docling(self, path: Path) -> dict:
        from docling.document_converter import DocumentConverter
        from docling.datamodel.pipeline_options import PdfPipelineOptions
        opts = PdfPipelineOptions()
        opts.do_ocr = False
        opts.do_table_structure = True
        converter = DocumentConverter()
        result = converter.convert(str(path))
        doc = result.document
        tables = []
        for table in doc.tables:
            try:
                tables.append(table.export_to_dataframe().values.tolist())
            except Exception:
                pass
        return {
            "text": doc.export_to_markdown(),
            "tables": tables,
            "pages": len(doc.pages) if hasattr(doc, "pages") else 0,
            "parser": "docling",
        }

    def _parse_pdfplumber(self, path: Path) -> dict:
        texts, tables = [], []
        with pdfplumber.open(path) as pdf:
            pages = len(pdf.pages)
            for page in pdf.pages:
                texts.append(page.extract_text() or "")
                for t in page.extract_tables():
                    if t:
                        tables.append(t)
        return {
            "text": "\n\n".join(texts),
            "tables": tables,
            "pages": pages,
            "parser": "pdfplumber",
        }

    def chunk_text(self, text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
        """Paragraph-aware chunker optimized for medical policy documents."""
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        chunks, current, current_len = [], [], 0
        for para in paragraphs:
            plen = len(para)
            if current_len + plen > chunk_size and current:
                chunks.append("\n\n".join(current))
                overlap_buf, overlap_len = [], 0
                for p in reversed(current):
                    if overlap_len + len(p) <= overlap:
                        overlap_buf.insert(0, p)
                        overlap_len += len(p)
                    else:
                        break
                current, current_len = overlap_buf, overlap_len
            current.append(para)
            current_len += plen
        if current:
            chunks.append("\n\n".join(current))
        return chunks
