"""
Helper functions and utilities.
"""

import os
import json
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


def get_app_data_dir() -> Path:
    """
    Get application data directory.
    
    Returns:
        Path to .messagecannon directory in user home
    """
    app_dir = Path.home() / ".messagecannon"
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


def get_config_dir() -> Path:
    """Get configuration directory."""
    config_dir = get_app_data_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_database_path() -> Path:
    """Get database file path."""
    db_dir = get_app_data_dir() / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "messagecannon.db"


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
