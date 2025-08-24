"""PDF table extraction for harvesting structured data."""

import re
from io import BytesIO
from typing import List, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Optional import - PDF table extraction is optional
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    logger.debug("pdfplumber not available - PDF table extraction disabled")


def find_numeric_cells(pdf_bytes: bytes, max_tables: int = 20) -> List[str]:
    """
    Extract cells from PDF tables that contain numeric data with dates/periods.
    
    Args:
        pdf_bytes: PDF file content as bytes
        max_tables: Maximum number of table rows to return
        
    Returns:
        List of table rows as pipe-delimited strings
    """
    if not PDFPLUMBER_AVAILABLE:
        logger.debug("PDF table extraction skipped - pdfplumber not installed")
        return []
        
    out = []
    
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page in pdf.pages:
                tables = page.extract_tables() or []
                
                for table in tables:
                    if not table:
                        continue
                        
                    for row in table:
                        if not row:
                            continue
                        
                        # Convert row to string
                        cell_line = " | ".join([str(c or "") for c in row])
                        
                        # Check if row contains both temporal and numeric data
                        has_period = bool(re.search(r"\b(20\d{2}|Q[1-4]|Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\b", cell_line))
                        has_number = bool(re.search(r"\d+(\.\d+)?\s*%|\b\d+(?:,\d{3})+\b|\b\d+\.\d+\b", cell_line))
                        
                        if has_period and has_number:
                            # Limit line length
                            out.append(cell_line[:300])
                            
                            if len(out) >= max_tables:
                                return out
                                
    except Exception as e:
        logger.warning(f"Error extracting PDF tables: {e}")
        
    return out


def extract_structured_tables(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Extract structured table data from PDF.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        List of dictionaries representing tables with headers and rows
    """
    if not PDFPLUMBER_AVAILABLE:
        return []
        
    tables_data = []
    
    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                tables = page.extract_tables() or []
                
                for table_num, table in enumerate(tables, 1):
                    if not table or len(table) < 2:
                        continue
                    
                    # Assume first row is header
                    headers = table[0]
                    rows = table[1:]
                    
                    # Skip tables without valid headers
                    if not headers or all(h is None for h in headers):
                        continue
                    
                    # Clean headers
                    headers = [str(h or f"Column_{i}") for i, h in enumerate(headers)]
                    
                    # Convert to structured format
                    table_dict = {
                        "page": page_num,
                        "table_num": table_num,
                        "headers": headers,
                        "rows": []
                    }
                    
                    for row in rows:
                        if row and any(cell is not None for cell in row):
                            row_dict = {}
                            for i, cell in enumerate(row):
                                if i < len(headers):
                                    row_dict[headers[i]] = str(cell or "")
                            table_dict["rows"].append(row_dict)
                    
                    if table_dict["rows"]:
                        tables_data.append(table_dict)
                        
    except Exception as e:
        logger.warning(f"Error extracting structured tables: {e}")
        
    return tables_data


def find_statistical_claims(pdf_bytes: bytes) -> List[str]:
    """
    Extract statistical claims from PDF tables.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        List of potential statistical claims
    """
    if not PDFPLUMBER_AVAILABLE:
        return []
        
    claims = []
    tables = extract_structured_tables(pdf_bytes)
    
    for table in tables:
        headers = table.get("headers", [])
        
        # Look for statistical headers
        stat_headers = []
        for header in headers:
            header_lower = header.lower()
            if any(term in header_lower for term in [
                "growth", "change", "increase", "decrease", "rate",
                "percentage", "%", "total", "average", "mean", "median"
            ]):
                stat_headers.append(header)
        
        if not stat_headers:
            continue
        
        # Extract claims from rows
        for row in table.get("rows", []):
            claim_parts = []
            
            # Get entity/category (usually first column)
            if headers and headers[0] in row:
                entity = row[headers[0]]
                if entity and len(entity) > 2:
                    claim_parts.append(entity)
            
            # Get statistical values
            for header in stat_headers:
                if header in row:
                    value = row[header]
                    if value and re.search(r'\d', value):
                        claim_parts.append(f"{header}: {value}")
            
            if len(claim_parts) >= 2:
                claim = " - ".join(claim_parts)
                claims.append(claim[:200])
                
    return claims[:20]  # Limit to top 20 claims


def extract_key_metrics(pdf_bytes: bytes) -> Dict[str, List[str]]:
    """
    Extract key metrics organized by category.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        Dictionary with metric categories and values
    """
    if not PDFPLUMBER_AVAILABLE:
        return {}
        
    metrics = {
        "percentages": [],
        "amounts": [],
        "dates": [],
        "entities": []
    }
    
    try:
        numeric_cells = find_numeric_cells(pdf_bytes, max_tables=50)
        
        for cell in numeric_cells:
            # Extract percentages
            pct_matches = re.findall(r'\d+(?:\.\d+)?\s*%', cell)
            metrics["percentages"].extend(pct_matches[:5])
            
            # Extract large numbers (thousands/millions/billions)
            amount_matches = re.findall(r'\b\d{1,3}(?:,\d{3})+(?:\.\d+)?\b', cell)
            metrics["amounts"].extend(amount_matches[:5])
            
            # Extract years and quarters
            date_matches = re.findall(r'\b20\d{2}\b|Q[1-4]\s+20\d{2}', cell)
            metrics["dates"].extend(date_matches[:5])
            
            # Extract potential entity names (capitalized phrases)
            entity_matches = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', cell)
            metrics["entities"].extend(entity_matches[:5])
        
        # Deduplicate
        for key in metrics:
            metrics[key] = list(dict.fromkeys(metrics[key]))[:10]
            
    except Exception as e:
        logger.warning(f"Error extracting key metrics: {e}")
        
    return metrics