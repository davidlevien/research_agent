"""Safe datetime formatting utilities to prevent strftime errors."""

from datetime import datetime, date, timezone
from typing import Union, Optional
import logging
import time
import re

logger = logging.getLogger(__name__)

def ensure_dt(x: Union[datetime, float, int, str, None]) -> Optional[datetime]:
    """
    Convert various timestamp formats to datetime objects safely.
    
    Args:
        x: Timestamp in various formats (datetime, epoch float/int, ISO string, etc.)
        
    Returns:
        datetime object or None if conversion fails
    """
    if x is None:
        return None
    
    if isinstance(x, datetime):
        return x
    
    if isinstance(x, (int, float)):
        # Treat as epoch seconds
        try:
            # Handle very large timestamps (milliseconds)
            timestamp = float(x)
            if timestamp > 1e10:  # Likely milliseconds
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OSError, OverflowError) as e:
            logger.debug(f"Failed to convert timestamp {x} to datetime: {e}")
            return None
    
    if isinstance(x, str):
        # Try common datetime formats
        formats = [
            "%Y-%m-%d",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%dT%H:%M:%S",
            "%Y/%m/%d",
            "%Y/%m/%d %H:%M:%S"
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(x, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        
        # Last resort: try parsing as epoch string
        try:
            timestamp = float(x)
            if timestamp > 1e10:  # Likely milliseconds
                timestamp = timestamp / 1000
            return datetime.fromtimestamp(timestamp, tz=timezone.utc)
        except (ValueError, OSError, OverflowError):
            logger.debug(f"Failed to parse datetime string: {x}")
            return None
    
    return None

def safe_strftime(x: Union[datetime, float, int, str, None], fmt: str) -> str:
    """
    Safely format any timestamp-like object using strftime.
    
    Args:
        x: Timestamp in any format
        fmt: strftime format string
        
    Returns:
        Formatted string or empty string if conversion fails
    """
    dt = ensure_dt(x)
    if dt is None:
        return ""
    
    try:
        return dt.strftime(fmt)
    except (ValueError, AttributeError) as e:
        logger.debug(f"Failed to format datetime {dt} with format {fmt}: {e}")
        return ""


def fmt_date(dt_like, fmt: str = "%Y-%m-%d") -> str:
    """
    Accepts datetime, epoch float/int, or ISO string; returns safe formatted date.
    
    This is the primary function used throughout the system to format dates.
    It handles all common input types robustly.
    """
    if isinstance(dt_like, (int, float)):
        dt = datetime.fromtimestamp(float(dt_like), tz=timezone.utc)
    elif isinstance(dt_like, str):
        try:
            dt = datetime.fromisoformat(dt_like.replace("Z", "+00:00"))
        except Exception:
            dt = datetime.fromtimestamp(time.time(), tz=timezone.utc)
    elif isinstance(dt_like, datetime):
        dt = dt_like
    elif dt_like is None:
        dt = datetime.fromtimestamp(time.time(), tz=timezone.utc)
    else:
        dt = datetime.fromtimestamp(time.time(), tz=timezone.utc)
    
    return dt.strftime(fmt)


def safe_format_dt(
    x: Optional[Union[int, float, datetime, date, str]], 
    fmt: str = "%Y-%m-%d %H:%M:%S",
    default: str = "—"
) -> str:
    """
    Safely format a datetime-like value to string with fallback.
    
    Args:
        x: Value to format - can be:
            - None: returns default
            - int/float: treated as epoch seconds
            - datetime/date: formatted directly
            - str: parsed then formatted
        fmt: strftime format string
        default: Default value to return if conversion fails
        
    Returns:
        Formatted string or default value
    """
    if x is None:
        return default
    
    # Special case: if input is a date-only string and we're using default format,
    # preserve the date-only format to match expected behavior
    if (isinstance(x, str) and fmt == "%Y-%m-%d %H:%M:%S" and 
        re.match(r'^\d{4}-\d{2}-\d{2}$', x)):
        return x
    
    # Use the new safe_strftime function
    result = safe_strftime(x, fmt)
    if result:
        return result
    
    # Handle date objects specially
    if isinstance(x, date) and not isinstance(x, datetime):
        try:
            if "%H" in fmt or "%M" in fmt or "%S" in fmt:
                # Convert to datetime at midnight for time formatting
                dt = datetime.combine(x, datetime.min.time())
                return dt.strftime(fmt)
            return x.strftime(fmt)
        except Exception as e:
            logger.warning(f"Failed to format date {x!r} with format {fmt}: {e}")
            return default
    
    # Fallback for other types
    return str(x) if x is not None else default


def format_timestamp_header(timestamp: Optional[Union[int, float, datetime]], include_time: bool = True) -> str:
    """
    Format a timestamp for report headers.
    
    Args:
        timestamp: Timestamp to format
        include_time: Whether to include time or just date
        
    Returns:
        Formatted string like "2024-03-15" or "2024-03-15 14:30"
    """
    fmt = "%Y-%m-%d %H:%M" if include_time else "%Y-%m-%d"
    return safe_format_dt(timestamp, fmt)


def format_duration(seconds: Optional[Union[int, float]]) -> str:
    """
    Format a duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string like "5m 23s" or "1h 15m"
    """
    if seconds is None:
        return "—"
    
    try:
        seconds = int(seconds)
        
        if seconds < 60:
            return f"{seconds}s"
        
        minutes = seconds // 60
        remaining_seconds = seconds % 60
        
        if minutes < 60:
            if remaining_seconds > 0:
                return f"{minutes}m {remaining_seconds}s"
            return f"{minutes}m"
        
        hours = minutes // 60
        remaining_minutes = minutes % 60
        
        if remaining_minutes > 0:
            return f"{hours}h {remaining_minutes}m"
        return f"{hours}h"
        
    except Exception as e:
        logger.warning(f"Failed to format duration {seconds}: {e}")
        return str(seconds) if seconds is not None else "—"


def ensure_datetime(x: Optional[Union[int, float, datetime, str]]) -> Optional[datetime]:
    """
    Convert various datetime representations to datetime object.
    
    Args:
        x: Value to convert
        
    Returns:
        datetime object or None
    """
    if x is None:
        return None
    
    try:
        if isinstance(x, datetime):
            return x
        
        if isinstance(x, (int, float)):
            return datetime.fromtimestamp(x)
        
        if isinstance(x, str):
            # Try common ISO formats
            for fmt in ["%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"]:
                try:
                    return datetime.strptime(x, fmt)
                except ValueError:
                    continue
        
        return None
        
    except Exception as e:
        logger.warning(f"Failed to convert {x!r} to datetime: {e}")
        return None