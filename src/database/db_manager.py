"""
Database manager for MessageCannon using SQLite.
"""

import sqlite3
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
import threading

from ..utils.helpers import get_database_path
from ..utils.logger import Logger
from ..models import Contact, Campaign, Template, MessageLog, MessageStatus


DEFAULT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL UNIQUE,
    name TEXT,
    tags TEXT,
    custom_fields TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS campaigns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    message_template TEXT NOT NULL,
    total_contacts INTEGER DEFAULT 0,
    sent_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    message_delay INTEGER DEFAULT 30,
    use_jitter BOOLEAN DEFAULT 1,
    scheduled_time TIMESTAMP,
    is_recurring BOOLEAN DEFAULT 0,
    recurrence_pattern TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS message_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    campaign_id INTEGER,
    contact_phone TEXT NOT NULL,
    contact_name TEXT,
    message_text TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    sent_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    category TEXT,
    message_text TEXT NOT NULL,
    description TEXT,
    is_default BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
);

CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone);
CREATE INDEX IF NOT EXISTS idx_message_logs_campaign ON message_logs(campaign_id);
CREATE INDEX IF NOT EXISTS idx_message_logs_status ON message_logs(status);
CREATE INDEX IF NOT EXISTS idx_campaigns_created ON campaigns(created_at);
"""


class DatabaseManager:
    """Manages SQLite database operations."""
    
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        """Initialize database manager."""
        if hasattr(self, '_initialized'):
            return
        
        self.db_path = get_database_path()
        self._initialize_database()
        self._initialized = True
    
    def _initialize_database(self) -> None:
        """Initialize database with schema."""
        try:
            schema_sql = self._load_schema_sql()
            
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
            
            Logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            Logger.error(f"Database initialization error: {e}")
            raise

    def _load_schema_sql(self) -> str:
        """Load schema SQL from source/package paths with safe fallback."""
        candidates = [Path(__file__).with_name("schema.sql")]

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            base = Path(meipass)
            candidates.extend([
                base / "src" / "database" / "schema.sql",
                base / "database" / "schema.sql",
            ])

        for schema_path in candidates:
            if schema_path.exists():
                schema_text = schema_path.read_text(encoding="utf-8")
                marker = 'SCHEMA = """'
                if marker in schema_text:
                    start = schema_text.find(marker)
                    start = schema_text.find('"""', start) + 3
                    end = schema_text.rfind('"""')
                    if start > 2 and end > start:
                        return schema_text[start:end]
                return schema_text

        Logger.warning("schema.sql not found in expected locations, using embedded default schema")
        return DEFAULT_SCHEMA_SQL
    
    @contextmanager
    def get_connection(self):
        """Get database connection context manager."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    # Contacts Operations
    def add_contact(self, contact: Contact) -> Optional[int]:
        """
        Add contact to database.
        
        Args:
            contact: Contact object
            
        Returns:
            Contact ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO contacts (phone, name, tags, custom_fields)
                    VALUES (?, ?, ?, ?)
                    """,
                    (
                        contact.phone,
                        contact.name,
                        ','.join(contact.tags) if contact.tags else '',
                        json.dumps(contact.custom_fields)
                    )
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            Logger.warning(f"Contact with phone {contact.phone} already exists")
            return None
        except Exception as e:
            Logger.error(f"Error adding contact: {e}")
            return None
    
    def add_contacts_batch(self, contacts: List[Contact]) -> int:
        """
        Add multiple contacts efficiently.
        
        Args:
            contacts: List of Contact objects
            
        Returns:
            Number of contacts added
        """
        count = 0
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                for contact in contacts:
                    try:
                        cursor.execute(
                            """
                            INSERT INTO contacts (phone, name, tags, custom_fields)
                            VALUES (?, ?, ?, ?)
                            """,
                            (
                                contact.phone,
                                contact.name,
                                ','.join(contact.tags) if contact.tags else '',
                                json.dumps(contact.custom_fields)
                            )
                        )
                        count += 1
                    except sqlite3.IntegrityError:
                        Logger.debug(f"Duplicate contact: {contact.phone}")
                        continue
                
                conn.commit()
        except Exception as e:
            Logger.error(f"Error adding contacts batch: {e}")
        
        return count
    
    def get_contacts(self, limit: Optional[int] = None, offset: int = 0) -> List[Contact]:
        """
        Get all contacts with optional limit.
        
        Args:
            limit: Maximum number of contacts to return
            offset: Number of contacts to skip
            
        Returns:
            List of Contact objects
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM contacts"
                params = []
                
                if limit:
                    query += " LIMIT ? OFFSET ?"
                    params = [limit, offset]
                
                cursor.execute(query, params)
                contacts = []
                
                for row in cursor.fetchall():
                    contact = Contact(
                        id=row['id'],
                        phone=row['phone'],
                        name=row['name'] or '',
                        tags=row['tags'].split(',') if row['tags'] else [],
                        custom_fields=json.loads(row['custom_fields']) if row['custom_fields'] else {},
                        created_at=datetime.fromisoformat(row['created_at'])
                    )
                    contacts.append(contact)
                
                return contacts
        except Exception as e:
            Logger.error(f"Error getting contacts: {e}")
            return []
    
    def search_contacts(self, query: str) -> List[Contact]:
        """
        Search contacts by name or phone.
        
        Args:
            query: Search query
            
        Returns:
            List of matching Contact objects
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                search_pattern = f"%{query}%"
                
                cursor.execute(
                    """
                    SELECT * FROM contacts 
                    WHERE phone LIKE ? OR name LIKE ?
                    LIMIT 100
                    """,
                    (search_pattern, search_pattern)
                )
                
                contacts = []
                for row in cursor.fetchall():
                    contact = Contact(
                        id=row['id'],
                        phone=row['phone'],
                        name=row['name'] or '',
                        tags=row['tags'].split(',') if row['tags'] else [],
                        custom_fields=json.loads(row['custom_fields']) if row['custom_fields'] else {},
                    )
                    contacts.append(contact)
                
                return contacts
        except Exception as e:
            Logger.error(f"Error searching contacts: {e}")
            return []
    
    def delete_contact(self, contact_id: int) -> bool:
        """
        Delete contact by ID.
        
        Args:
            contact_id: Contact ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM contacts WHERE id = ?", (contact_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            Logger.error(f"Error deleting contact: {e}")
            return False
    
    def get_contact_count(self) -> int:
        """
        Get total number of contacts.
        
        Returns:
            Number of contacts
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM contacts")
                return cursor.fetchone()['count']
        except Exception as e:
            Logger.error(f"Error getting contact count: {e}")
            return 0
    
    # Campaign Operations
    def add_campaign(self, campaign: Campaign) -> Optional[int]:
        """
        Add campaign to database.
        
        Args:
            campaign: Campaign object
            
        Returns:
            Campaign ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO campaigns 
                    (name, message_template, total_contacts, sent_count, failed_count,
                     message_delay, use_jitter, scheduled_time, is_recurring, recurrence_pattern)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        campaign.name,
                        campaign.message_template,
                        campaign.total_contacts,
                        campaign.sent_count,
                        campaign.failed_count,
                        campaign.message_delay,
                        campaign.use_jitter,
                        campaign.scheduled_time.isoformat() if campaign.scheduled_time else None,
                        campaign.is_recurring,
                        campaign.recurrence_pattern
                    )
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            Logger.error(f"Error adding campaign: {e}")
            return None
    
    def get_campaigns(self, limit: Optional[int] = None) -> List[Campaign]:
        """
        Get campaigns from database.
        
        Args:
            limit: Maximum number of campaigns
            
        Returns:
            List of Campaign objects
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                query = "SELECT * FROM campaigns ORDER BY created_at DESC"
                if limit:
                    query += f" LIMIT {limit}"
                
                cursor.execute(query)
                campaigns = []
                
                for row in cursor.fetchall():
                    campaign = Campaign(
                        id=row['id'],
                        name=row['name'],
                        message_template=row['message_template'],
                        total_contacts=row['total_contacts'],
                        sent_count=row['sent_count'],
                        failed_count=row['failed_count'],
                        message_delay=row['message_delay'],
                        use_jitter=bool(row['use_jitter']),
                        scheduled_time=datetime.fromisoformat(row['scheduled_time']) if row['scheduled_time'] else None,
                        is_recurring=bool(row['is_recurring']),
                        recurrence_pattern=row['recurrence_pattern'],
                        created_at=datetime.fromisoformat(row['created_at']),
                        updated_at=datetime.fromisoformat(row['updated_at'])
                    )
                    campaigns.append(campaign)
                
                return campaigns
        except Exception as e:
            Logger.error(f"Error getting campaigns: {e}")
            return []
    
    # Message Log Operations
    def add_message_log(self, log: MessageLog) -> Optional[int]:
        """
        Add message log entry.
        
        Args:
            log: MessageLog object
            
        Returns:
            Log ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO message_logs 
                    (campaign_id, contact_phone, contact_name, message_text, status, 
                     sent_at, error_message, retry_count)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        log.campaign_id,
                        log.contact_phone,
                        log.contact_name,
                        log.message_text,
                        log.status.value,
                        log.sent_at.isoformat() if log.sent_at else None,
                        log.error_message,
                        log.retry_count
                    )
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            Logger.error(f"Error adding message log: {e}")
            return None
    
    def get_message_logs(self, campaign_id: Optional[int] = None, limit: int = 100) -> List[MessageLog]:
        """
        Get message logs.
        
        Args:
            campaign_id: Filter by campaign ID
            limit: Maximum number of logs
            
        Returns:
            List of MessageLog objects
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                if campaign_id:
                    cursor.execute(
                        """
                        SELECT * FROM message_logs 
                        WHERE campaign_id = ?
                        ORDER BY created_at DESC
                        LIMIT ?
                        """,
                        (campaign_id, limit)
                    )
                else:
                    cursor.execute(
                        "SELECT * FROM message_logs ORDER BY created_at DESC LIMIT ?",
                        (limit,)
                    )
                
                logs = []
                for row in cursor.fetchall():
                    log = MessageLog(
                        id=row['id'],
                        campaign_id=row['campaign_id'],
                        contact_phone=row['contact_phone'],
                        contact_name=row['contact_name'],
                        message_text=row['message_text'],
                        status=MessageStatus(row['status']),
                        sent_at=datetime.fromisoformat(row['sent_at']) if row['sent_at'] else None,
                        error_message=row['error_message'],
                        retry_count=row['retry_count']
                    )
                    logs.append(log)
                
                return logs
        except Exception as e:
            Logger.error(f"Error getting message logs: {e}")
            return []
    
    # Template Operations
    def add_template(self, template: Template) -> Optional[int]:
        """
        Add template to database.
        
        Args:
            template: Template object
            
        Returns:
            Template ID if successful, None otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO templates (name, category, message_text, description, is_default)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        template.name,
                        template.category,
                        template.message_text,
                        template.description,
                        template.is_default
                    )
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            Logger.error(f"Error adding template: {e}")
            return None
    
    def get_templates(self) -> List[Template]:
        """
        Get all templates.
        
        Returns:
            List of Template objects
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM templates ORDER BY is_default DESC, category, name"
                )
                
                templates = []
                for row in cursor.fetchall():
                    template = Template(
                        id=row['id'],
                        name=row['name'],
                        category=row['category'],
                        message_text=row['message_text'],
                        description=row['description'],
                        is_default=bool(row['is_default']),
                        created_at=datetime.fromisoformat(row['created_at'])
                    )
                    templates.append(template)
                
                return templates
        except Exception as e:
            Logger.error(f"Error getting templates: {e}")
            return []
    
    # Settings Operations
    def set_setting(self, key: str, value: str) -> bool:
        """
        Set application setting.
        
        Args:
            key: Setting key
            value: Setting value
            
        Returns:
            True if successful, False otherwise
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
                    (key, value)
                )
                conn.commit()
                return True
        except Exception as e:
            Logger.error(f"Error setting setting: {e}")
            return False
    
    def get_setting(self, key: str, default: str = "") -> str:
        """
        Get application setting.
        
        Args:
            key: Setting key
            default: Default value if not found
            
        Returns:
            Setting value
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
                row = cursor.fetchone()
                return row['value'] if row else default
        except Exception as e:
            Logger.error(f"Error getting setting: {e}")
            return default
