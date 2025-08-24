"""
Web archiving and snapshot utilities
"""

from __future__ import annotations
from typing import Optional, Dict, Any
import logging
from pathlib import Path
import hashlib
from datetime import datetime

logger = logging.getLogger(__name__)


def save_wayback(url: str) -> str | None:
    try:
        import httpx
        r = httpx.get("https://web.archive.org/save/" + url, timeout=20)
        return r.headers.get("Content-Location")
    except Exception:
        return None


def save_local_snapshot(content: str, url: str, output_dir: Path = None) -> Optional[str]:
    """
    Save content locally with hash-based filename.
    Returns the local path if successful.
    """
    if not content or not url:
        return None
    
    try:
        # Default to snapshots directory
        if output_dir is None:
            output_dir = Path("snapshots")
        
        output_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename from URL hash and timestamp
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:12]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{url_hash}.html"
        
        filepath = output_dir / filename
        filepath.write_text(content, encoding='utf-8')
        
        logger.info(f"Saved snapshot to {filepath}")
        return str(filepath)
        
    except Exception as e:
        logger.error(f"Failed to save local snapshot: {e}")
        return None


def create_warc_record(url: str, content: str, headers: Dict[str, str] = None) -> Optional[bytes]:
    """
    Create a WARC record for archival purposes.
    Returns WARC bytes if warcio is available.
    """
    try:
        from warcio.warcwriter import WARCWriter
        from warcio.statusandheaders import StatusAndHeaders
        from io import BytesIO
        
        output = BytesIO()
        writer = WARCWriter(output, gzip=True)
        
        # Create response record
        headers_list = []
        if headers:
            headers_list = [(k, v) for k, v in headers.items()]
        
        http_headers = StatusAndHeaders('200 OK', headers_list)
        
        record = writer.create_warc_record(
            url,
            'response',
            payload=BytesIO(content.encode('utf-8')),
            http_headers=http_headers
        )
        
        writer.write_record(record)
        
        return output.getvalue()
        
    except ImportError:
        logger.debug("warcio not available for WARC creation")
        return None
    except Exception as e:
        logger.error(f"Failed to create WARC record: {e}")
        return None


class SnapshotManager:
    """
    Manages web page snapshots with multiple storage backends
    """
    
    def __init__(self, 
                 enable_wayback: bool = False,
                 enable_local: bool = True,
                 enable_warc: bool = False,
                 output_dir: Path = None):
        self.enable_wayback = enable_wayback
        self.enable_local = enable_local
        self.enable_warc = enable_warc
        self.output_dir = output_dir or Path("snapshots")
        
    def snapshot(self, url: str, content: str = None, headers: Dict = None) -> Dict[str, Any]:
        """
        Create snapshots using configured backends.
        Returns dict with snapshot locations.
        """
        results = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "wayback": None,
            "local": None,
            "warc": None
        }
        
        # Wayback Machine
        if self.enable_wayback:
            results["wayback"] = save_wayback(url)
        
        # Local HTML snapshot
        if self.enable_local and content:
            results["local"] = save_local_snapshot(content, url, self.output_dir)
        
        # WARC archive
        if self.enable_warc and content:
            warc_data = create_warc_record(url, content, headers)
            if warc_data:
                warc_path = self.output_dir / "archive.warc.gz"
                warc_path.parent.mkdir(parents=True, exist_ok=True)
                with open(warc_path, 'ab') as f:
                    f.write(warc_data)
                results["warc"] = str(warc_path)
        
        return results