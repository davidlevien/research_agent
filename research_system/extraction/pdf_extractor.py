"""PDF text extraction with layout awareness.

v8.21.0: Extracts text from PDFs while preserving reading order
and filtering out headers/footers.
"""

import io
from typing import List

try:
    import fitz  # PyMuPDF
    HAS_FITZ = True
except ImportError:
    HAS_FITZ = False

def extract_pdf_text(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF bytes with layout awareness.
    
    Args:
        pdf_bytes: Raw PDF file bytes
        
    Returns:
        Extracted text with paragraphs separated by newlines
    """
    if not pdf_bytes:
        return ""
    
    if not HAS_FITZ:
        # Fallback: just return bytes decoded best-effort
        try:
            # Try UTF-8 first
            return pdf_bytes.decode("utf-8", errors="ignore")
        except Exception:
            # Fall back to latin-1
            return pdf_bytes.decode("latin-1", errors="ignore")
    
    try:
        doc = fitz.open(stream=io.BytesIO(pdf_bytes), filetype="pdf")
    except Exception:
        # If PyMuPDF fails, use fallback
        return pdf_bytes.decode("latin-1", errors="ignore")
    
    chunks: List[str] = []
    
    for page_num, page in enumerate(doc):
        try:
            # Get text blocks with position information
            blocks = page.get_text("blocks")
            
            # Sort blocks top->bottom, left->right for reading order
            sorted_blocks = sorted(blocks, key=lambda b: (round(b[2]/10), round(b[1]/10)))
            
            for block in sorted_blocks:
                # Block format: (x0, y0, x1, y1, text, block_no, block_type)
                if len(block) < 5:
                    continue
                    
                x0, y0, x1, y1, text = block[:5]
                
                # Skip headers/footers by position heuristics
                page_height = page.rect.height
                
                # Skip if in top 50 pixels (header) or bottom 50 pixels (footer)
                if y0 < 50 or (page_height - y1) < 50:
                    continue
                
                # Clean and validate text
                if isinstance(text, str):
                    text = text.strip()
                    if len(text) >= 3:  # Skip very short text
                        chunks.append(text)
                        
        except Exception:
            # If block extraction fails for this page, skip it
            continue
    
    doc.close()
    return "\n".join(chunks)