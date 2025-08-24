"""WARC capture for provenance and auditing."""

import time
import os
import httpx
from io import BytesIO
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Optional import - WARC functionality is optional
try:
    from warcio.warcwriter import WARCWriter
    WARCIO_AVAILABLE = True
except ImportError:
    WARCIO_AVAILABLE = False
    logger.debug("warcio not available - WARC capture disabled")


def warc_capture(
    url: str,
    headers: Optional[dict] = None,
    timeout: int = 30,
    output_dir: str = "archives"
) -> Optional[str]:
    """
    Capture HTTP response in WARC format for provenance.
    
    Args:
        url: URL to capture
        headers: Request headers
        timeout: Request timeout
        output_dir: Directory to save WARC files
        
    Returns:
        Path to WARC file if successful, None otherwise
    """
    if not WARCIO_AVAILABLE:
        logger.debug("WARC capture skipped - warcio not installed")
        return None
        
    try:
        # Make request
        r = httpx.get(url, headers=headers, timeout=timeout, follow_redirects=True)
        
        # Create output directory
        os.makedirs(output_dir, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = int(time.time())
        filename = f"{timestamp}_{_sanitize_filename(url)}.warc.gz"
        path = os.path.join(output_dir, filename)
        
        # Write WARC record
        with open(path, "wb") as output:
            writer = WARCWriter(output, gzip=True)
            
            # Create response record
            record = writer.create_warc_record(
                url,
                'response',
                payload=BytesIO(r.content),
                http_headers=r.headers
            )
            writer.write_record(record)
            
            # Optionally add metadata record
            metadata = {
                "status_code": r.status_code,
                "final_url": str(r.url),
                "capture_time": timestamp,
                "user_agent": headers.get("User-Agent") if headers else None
            }
            
            metadata_record = writer.create_warc_record(
                url,
                'metadata',
                payload=BytesIO(str(metadata).encode()),
                warc_content_type='application/json'
            )
            writer.write_record(metadata_record)
        
        logger.info(f"WARC captured: {path}")
        return path
        
    except Exception as e:
        logger.warning(f"WARC capture failed for {url}: {e}")
        return None


def _sanitize_filename(url: str) -> str:
    """Sanitize URL for use in filename."""
    import re
    # Remove protocol
    clean = re.sub(r'^https?://', '', url)
    # Replace special characters
    clean = re.sub(r'[^\w\-_.]', '_', clean)
    # Limit length
    return clean[:100]


def capture_batch(
    urls: list[str],
    headers: Optional[dict] = None,
    output_dir: str = "archives"
) -> dict[str, Optional[str]]:
    """
    Capture multiple URLs to WARC files.
    
    Args:
        urls: List of URLs to capture
        headers: Request headers
        output_dir: Directory to save WARC files
        
    Returns:
        Dictionary mapping URL to WARC file path
    """
    results = {}
    
    for url in urls:
        path = warc_capture(url, headers, output_dir=output_dir)
        results[url] = path
        
        # Small delay between captures to be polite
        if path:
            time.sleep(0.5)
    
    return results


def read_warc(filepath: str) -> list[dict]:
    """
    Read records from a WARC file.
    
    Args:
        filepath: Path to WARC file
        
    Returns:
        List of record dictionaries
    """
    if not WARCIO_AVAILABLE:
        logger.warning("Cannot read WARC - warcio not installed")
        return []
        
    try:
        from warcio.archiveiterator import ArchiveIterator
        
        records = []
        
        with open(filepath, 'rb') as stream:
            for record in ArchiveIterator(stream):
                record_dict = {
                    'type': record.rec_type,
                    'url': record.rec_headers.get_header('WARC-Target-URI'),
                    'date': record.rec_headers.get_header('WARC-Date'),
                    'content_type': record.rec_headers.get_header('Content-Type'),
                    'content_length': record.rec_headers.get_header('Content-Length'),
                }
                
                # Read content for small records
                if record.content_stream() and record_dict.get('content_length'):
                    try:
                        length = int(record_dict['content_length'])
                        if length < 1_000_000:  # 1MB limit
                            record_dict['content'] = record.content_stream().read()
                    except Exception:
                        pass
                
                records.append(record_dict)
        
        return records
        
    except Exception as e:
        logger.error(f"Failed to read WARC file {filepath}: {e}")
        return []