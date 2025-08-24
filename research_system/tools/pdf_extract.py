"""
PDF text extraction utilities with table support
"""

from __future__ import annotations
from typing import Optional, Dict, Any, List, Union
import io
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_pdf_text(path_or_bytes: Union[str, Path, bytes, io.BytesIO]) -> Dict[str, Any]:
    """
    Extract text and metadata from PDF using PyMuPDF (fast) or pdfplumber (fallback).
    
    Args:
        path_or_bytes: File path, Path object, bytes, or BytesIO object
    
    Returns:
        Dict with 'text', 'title', 'pages', 'metadata', and optional 'tables'
    """
    result = {
        "text": "",
        "title": None,
        "pages": 0,
        "metadata": {},
        "tables": [],
        "error": None
    }
    
    # Try PyMuPDF first (faster and more reliable)
    try:
        import fitz  # PyMuPDF
        
        # Open document based on input type
        if isinstance(path_or_bytes, (bytes, bytearray)):
            doc = fitz.open(stream=path_or_bytes, filetype="pdf")
        elif isinstance(path_or_bytes, io.BytesIO):
            doc = fitz.open(stream=path_or_bytes.getvalue(), filetype="pdf")
        else:
            doc = fitz.open(str(path_or_bytes))
        
        # Extract text from all pages
        text_parts = []
        for page_num, page in enumerate(doc, 1):
            page_text = page.get_text()
            if page_text:
                text_parts.append(f"[Page {page_num}]\n{page_text}")
        
        result["text"] = "\n\n".join(text_parts)
        result["pages"] = len(doc)
        
        # Extract metadata
        metadata = doc.metadata
        if metadata:
            result["title"] = metadata.get("title")
            result["metadata"] = {
                "author": metadata.get("author"),
                "subject": metadata.get("subject"),
                "keywords": metadata.get("keywords"),
                "creator": metadata.get("creator"),
                "producer": metadata.get("producer"),
                "creationDate": str(metadata.get("creationDate")) if metadata.get("creationDate") else None,
                "modDate": str(metadata.get("modDate")) if metadata.get("modDate") else None
            }
        
        doc.close()
        logger.debug(f"Successfully extracted {result['pages']} pages using PyMuPDF")
        return result
        
    except ImportError:
        logger.debug("PyMuPDF not available, trying pdfplumber")
    except Exception as e:
        logger.warning(f"PyMuPDF extraction failed: {e}")
        result["error"] = str(e)
    
    # Fallback to pdfplumber (better for tables)
    try:
        import pdfplumber
        
        # Open PDF based on input type
        if isinstance(path_or_bytes, (bytes, bytearray)):
            pdf_file = io.BytesIO(path_or_bytes)
        elif isinstance(path_or_bytes, io.BytesIO):
            pdf_file = path_or_bytes
        else:
            pdf_file = str(path_or_bytes)
        
        with pdfplumber.open(pdf_file) as pdf:
            # Extract text from all pages
            text_parts = []
            for page_num, page in enumerate(pdf.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(f"[Page {page_num}]\n{page_text}")
                
                # Extract tables if present
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table:
                        result["tables"].append({
                            "page": page_num,
                            "index": table_idx,
                            "data": table
                        })
            
            result["text"] = "\n\n".join(text_parts)
            result["pages"] = len(pdf.pages)
            
            # Extract metadata
            if pdf.metadata:
                result["metadata"] = dict(pdf.metadata)
                result["title"] = pdf.metadata.get("Title")
        
        logger.debug(f"Successfully extracted {result['pages']} pages using pdfplumber")
        return result
        
    except ImportError:
        logger.warning("pdfplumber not available")
        result["error"] = "No PDF extraction library available (install pymupdf or pdfplumber)"
    except Exception as e:
        logger.error(f"pdfplumber extraction failed: {e}")
        result["error"] = str(e)
    
    return result


def extract_pdf_with_layout(path_or_bytes: Union[str, Path, bytes]) -> Dict[str, Any]:
    """
    Extract PDF preserving layout information (useful for forms, reports).
    Uses PyMuPDF's layout preservation mode.
    """
    result = {
        "text": "",
        "blocks": [],
        "pages": 0,
        "error": None
    }
    
    try:
        import fitz
        
        if isinstance(path_or_bytes, (bytes, bytearray)):
            doc = fitz.open(stream=path_or_bytes, filetype="pdf")
        else:
            doc = fitz.open(str(path_or_bytes))
        
        for page_num, page in enumerate(doc, 1):
            # Get text blocks with position information
            blocks = page.get_text("blocks")
            
            for block in blocks:
                if block[6] == 0:  # Text block (not image)
                    result["blocks"].append({
                        "page": page_num,
                        "bbox": block[:4],  # Bounding box (x0, y0, x1, y1)
                        "text": block[4],
                        "type": "text"
                    })
        
        # Also get regular text for convenience
        result["text"] = "\n".join(page.get_text() for page in doc)
        result["pages"] = len(doc)
        
        doc.close()
        return result
        
    except Exception as e:
        logger.error(f"Layout extraction failed: {e}")
        result["error"] = str(e)
        return result


def extract_tables_from_pdf(path_or_bytes: Union[str, Path, bytes]) -> List[Dict[str, Any]]:
    """
    Extract tables from PDF specifically.
    Returns list of tables with page numbers.
    """
    tables = []
    
    # Try camelot first (best for tables)
    try:
        import camelot
        
        if isinstance(path_or_bytes, bytes):
            # Save to temp file for camelot
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(path_or_bytes)
                tmp_path = tmp.name
            
            tables_camelot = camelot.read_pdf(tmp_path, pages='all', flavor='stream')
            
            # Clean up temp file
            Path(tmp_path).unlink()
        else:
            tables_camelot = camelot.read_pdf(str(path_or_bytes), pages='all', flavor='stream')
        
        for table in tables_camelot:
            tables.append({
                "page": table.page,
                "data": table.df.values.tolist(),
                "headers": table.df.columns.tolist(),
                "accuracy": table.accuracy
            })
        
        logger.debug(f"Extracted {len(tables)} tables using camelot")
        return tables
        
    except ImportError:
        logger.debug("camelot not available, trying tabula")
    except Exception as e:
        logger.warning(f"camelot extraction failed: {e}")
    
    # Fallback to tabula
    try:
        import tabula
        
        if isinstance(path_or_bytes, bytes):
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                tmp.write(path_or_bytes)
                tmp_path = tmp.name
            
            dfs = tabula.read_pdf(tmp_path, pages='all', multiple_tables=True)
            Path(tmp_path).unlink()
        else:
            dfs = tabula.read_pdf(str(path_or_bytes), pages='all', multiple_tables=True)
        
        for idx, df in enumerate(dfs):
            tables.append({
                "page": idx + 1,  # tabula doesn't provide exact page
                "data": df.values.tolist(),
                "headers": df.columns.tolist()
            })
        
        logger.debug(f"Extracted {len(tables)} tables using tabula")
        return tables
        
    except ImportError:
        logger.debug("tabula not available")
    except Exception as e:
        logger.warning(f"tabula extraction failed: {e}")
    
    # Final fallback to pdfplumber (already implemented above)
    try:
        import pdfplumber
        
        if isinstance(path_or_bytes, bytes):
            pdf_file = io.BytesIO(path_or_bytes)
        else:
            pdf_file = str(path_or_bytes)
        
        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                page_tables = page.extract_tables()
                for table_idx, table in enumerate(page_tables):
                    if table:
                        tables.append({
                            "page": page_num,
                            "data": table
                        })
        
        logger.debug(f"Extracted {len(tables)} tables using pdfplumber")
        
    except Exception as e:
        logger.error(f"All table extraction methods failed: {e}")
    
    return tables


def extract_quote_span(pdf_content: Dict[str, Any], search_text: str, context_chars: int = 150) -> Optional[str]:
    """
    Extract a quote span from PDF content that matches search text.
    Returns the matched text with surrounding context.
    """
    if not pdf_content.get("text") or not search_text:
        return None
    
    text = pdf_content["text"]
    search_lower = search_text.lower()
    text_lower = text.lower()
    
    # Find the search text in the PDF
    pos = text_lower.find(search_lower)
    if pos == -1:
        # Try fuzzy matching for partial matches
        words = search_lower.split()
        if len(words) > 3:
            # Try with first few words
            partial = " ".join(words[:3])
            pos = text_lower.find(partial)
    
    if pos == -1:
        return None
    
    # Extract with context
    start = max(0, pos - context_chars)
    end = min(len(text), pos + len(search_text) + context_chars)
    
    quote = text[start:end]
    
    # Clean up the quote
    if start > 0:
        quote = "..." + quote.lstrip()
    if end < len(text):
        quote = quote.rstrip() + "..."
    
    # Add page reference if available
    if "Page" in text[max(0, pos-50):pos]:
        page_match = text[max(0, pos-50):pos].rfind("[Page")
        if page_match != -1:
            page_info = text[max(0, pos-50):pos][page_match:].split("]")[0] + "]"
            quote = f"{page_info} {quote}"
    
    return quote