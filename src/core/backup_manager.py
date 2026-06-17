"""
Backup manager for application data backup and restore.
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..utils.paths import get_app_data_dir
from ..utils.logger import Logger


class BackupManager:
    """Manages application data backup and restore."""
    
    BACKUP_DIR = "backups"
    
    def __init__(self):
        """Initialize backup manager."""
        self.backup_dir = get_app_data_dir() / self.BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)
    
    def create_backup(self) -> Optional[str]:
        """
        Create backup of application data.
        
        Returns:
            Backup file path if successful, None otherwise
        """
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = self.backup_dir / f"backup_{timestamp}.zip"
            
            # Get data directories to backup
            data_dir = get_app_data_dir()
            
            # Create zip backup
            shutil.make_archive(
                str(backup_file.with_suffix('')),
                'zip',
                data_dir
            )
            
            Logger.info(f"Backup created: {backup_file}")
            return str(backup_file)
        
        except Exception as e:
            Logger.error(f"Error creating backup: {e}")
            return None
    
    def restore_backup(self, backup_file: str) -> bool:
        """
        Restore from backup.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if restored successfully, False otherwise
        """
        try:
            backup_path = Path(backup_file)
            
            if not backup_path.exists():
                Logger.error(f"Backup file not found: {backup_file}")
                return False
            
            data_dir = get_app_data_dir()
            
            # Extract backup
            shutil.unpack_archive(str(backup_path), data_dir)
            
            Logger.info(f"Backup restored: {backup_file}")
            return True
        
        except Exception as e:
            Logger.error(f"Error restoring backup: {e}")
            return False
    
    def list_backups(self) -> list:
        """
        List all available backups.
        
        Returns:
            List of backup file paths
        """
        try:
            backups = list(self.backup_dir.glob("backup_*.zip"))
            backups.sort(reverse=True)  # Most recent first
            return [str(b) for b in backups]
        except Exception as e:
            Logger.error(f"Error listing backups: {e}")
            return []
    
    def delete_backup(self, backup_file: str) -> bool:
        """
        Delete a backup file.
        
        Args:
            backup_file: Path to backup file
            
        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            backup_path = Path(backup_file)
            
            if backup_path.exists():
                backup_path.unlink()
                Logger.info(f"Backup deleted: {backup_file}")
                return True
            
            return False
        
        except Exception as e:
            Logger.error(f"Error deleting backup: {e}")
            return False
    
    def cleanup_old_backups(self, keep_count: int = 5) -> int:
        """
        Delete old backups, keeping only most recent.
        
        Args:
            keep_count: Number of recent backups to keep
            
        Returns:
            Number of backups deleted
        """
        try:
            backups = list(self.backup_dir.glob("backup_*.zip"))
            backups.sort(reverse=True)
            
            deleted = 0
            
            for backup in backups[keep_count:]:
                backup.unlink()
                deleted += 1
            
            if deleted > 0:
                Logger.info(f"Cleaned up {deleted} old backups")
            
            return deleted
        
        except Exception as e:
            Logger.error(f"Error cleaning up backups: {e}")
            return 0
