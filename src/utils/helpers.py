"""
Helper functions and utilities.
"""

import json
import urllib.parse
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime

from .paths import get_app_data_dir, get_config_dir, get_database_path


def parse_dropped_file_path(raw_data: str) -> str:
    """Extracts a real filesystem path from a tkinterdnd2 <<Drop>> event's
    raw event.data string. Previously duplicated, byte-for-byte, in both
    card_creator_tab.py and contact_import_review.py -- extracted here so
    the two can't silently drift apart again.

    Handles the common case -- a single Tcl-braced path when it contains
    spaces, or a bare unbraced path when it doesn't -- plus a real,
    documented tkinterdnd2 cross-platform quirk the original hand-rolled
    parsing never covered: some drag sources hand back a file:// URI
    (percent-encoded) instead of a plain filesystem path, which
    Path(...).is_file() then correctly reports as not existing -- a
    genuine upload/import failure for a perfectly real file. Found and
    fixed while investigating a live report of Card Creator's "Crop"
    button staying disabled after what looked like a successful drag-drop
    upload."""
    raw = raw_data.strip()
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1]
    path = raw.split("} {")[0] if "} {" in raw else raw
    if path.lower().startswith("file://"):
        parsed = urllib.parse.urlparse(path)
        decoded = urllib.parse.unquote(parsed.path)
        # urlparse gives "/C:/Users/..." for a Windows file:// URI --
        # strip the leading slash in front of a drive letter.
        if len(decoded) >= 3 and decoded[0] == "/" and decoded[2] == ":":
            decoded = decoded[1:]
        path = decoded
    return path


def save_json(data: Dict[str, Any], filename: str, directory: Optional[Path] = None) -> bool:
    """
    Save data to JSON file.
    
    Args:
        data: Dictionary to save
        filename: Filename (with .json extension)
        directory: Directory to save in (default: config dir)
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if directory is None:
            directory = get_config_dir()
        
        directory.mkdir(parents=True, exist_ok=True)
        filepath = directory / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        
        return True
    except Exception as e:
        print(f"Error saving JSON: {e}")
        return False


def load_json(filename: str, directory: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """
    Load data from JSON file.
    
    Args:
        filename: Filename (with .json extension)
        directory: Directory to load from (default: config dir)
        
    Returns:
        Dictionary if successful, None otherwise
    """
    try:
        if directory is None:
            directory = get_config_dir()
        
        filepath = directory / filename
        
        if not filepath.exists():
            return None
        
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading JSON: {e}")
        return None


def format_timestamp(dt: datetime) -> str:
    """
    Format datetime to readable string.
    
    Args:
        dt: Datetime object
        
    Returns:
        Formatted string (YYYY-MM-DD HH:MM:SS)
    """
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def truncate_string(text: str, max_length: int = 50, suffix: str = "...") -> str:
    """
    Truncate string to max length with suffix.
    
    Args:
        text: String to truncate
        max_length: Maximum length
        suffix: Suffix to add if truncated
        
    Returns:
        Truncated string
    """
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix


def format_phone_display(phone: str) -> str:
    """
    Format phone number for display.
    
    Args:
        phone: Phone number
        
    Returns:
        Formatted phone number
    """
    if not phone:
        return ""
    
    # Format as +92 XXXXX XXXXX
    if phone.startswith("+92"):
        return f"+92 {phone[3:8]} {phone[8:]}"
    
    return phone


def humanize_number(number: int) -> str:
    """
    Convert number to human readable format.
    
    Args:
        number: Number to format
        
    Returns:
        Formatted number string
    """
    if number >= 1000000:
        return f"{number / 1000000:.1f}M"
    elif number >= 1000:
        return f"{number / 1000:.1f}K"
    else:
        return str(number)


def calculate_eta(current: int, total: int, elapsed_seconds: float) -> Optional[str]:
    """
    Calculate estimated time to completion.
    
    Args:
        current: Current count
        total: Total count
        elapsed_seconds: Elapsed time in seconds
        
    Returns:
        ETA string or None if not calculable
    """
    if current == 0 or total == 0:
        return None
    
    try:
        rate = current / elapsed_seconds  # items per second
        remaining = total - current
        eta_seconds = remaining / rate
        
        hours = int(eta_seconds // 3600)
        minutes = int((eta_seconds % 3600) // 60)
        seconds = int(eta_seconds % 60)
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    except:
        return None


def is_first_launch() -> bool:
    """
    Check if this is first launch of application.
    
    Returns:
        True if first launch, False otherwise
    """
    config_dir = get_config_dir()
    first_launch_file = config_dir / ".first_launch_complete"
    
    return not first_launch_file.exists()


def mark_first_launch_complete() -> None:
    """Mark first launch as complete."""
    config_dir = get_config_dir()
    first_launch_file = config_dir / ".first_launch_complete"
    first_launch_file.touch()


__all__ = [
    "get_app_data_dir",
    "get_config_dir",
    "get_database_path",
    "save_json",
    "load_json",
    "format_timestamp",
    "truncate_string",
    "format_phone_display",
    "humanize_number",
    "calculate_eta",
    "is_first_launch",
    "mark_first_launch_complete",
    "parse_dropped_file_path",
]
