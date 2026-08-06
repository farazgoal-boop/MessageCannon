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

from ..utils.paths import get_database_path
from ..utils.logger import Logger
from ..models import Contact, Campaign, Template, MessageLog, MessageStatus


DEFAULT_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT UNIQUE,
    email TEXT,
    name TEXT,
    tags TEXT,
    custom_fields TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    opted_out INTEGER DEFAULT 0,
    bounced INTEGER DEFAULT 0
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
    contact_phone TEXT,
    contact_email TEXT,
    contact_name TEXT,
    subject TEXT,
    message_text TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    sent_at TIMESTAMP,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bounced INTEGER DEFAULT 0,
    bounce_reason TEXT,
    bounce_checked_at TIMESTAMP,
    FOREIGN KEY (campaign_id) REFERENCES campaigns(id)
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone TEXT NOT NULL,
    message_text TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    sent_at TIMESTAMP,
    delivered_at TIMESTAMP,
    read_at TIMESTAMP,
    error_reason TEXT,
    whatsapp_message_id TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
CREATE INDEX IF NOT EXISTS idx_messages_phone ON messages(phone);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
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
            self._run_migrations()
        except Exception as e:
            Logger.error(f"Database initialization error: {e}")
            raise

    def _run_migrations(self) -> None:
        """Run safe ALTER TABLE migrations to update the database to the current schema version."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                
                # Check contacts columns
                cursor.execute("PRAGMA table_info(contacts)")
                cols = [row[1] for row in cursor.fetchall()]
                if "email" not in cols:
                    try:
                        cursor.execute("ALTER TABLE contacts ADD COLUMN email TEXT")
                        conn.commit()
                        Logger.info("Added email column to contacts table")
                    except Exception as e:
                        Logger.error(f"Migration error (contacts.email): {e}")
                if "opted_out" not in cols:
                    try:
                        cursor.execute("ALTER TABLE contacts ADD COLUMN opted_out INTEGER DEFAULT 0")
                        conn.commit()
                        Logger.info("Added opted_out column to contacts table")
                    except Exception as e:
                        Logger.error(f"Migration error (contacts.opted_out): {e}")
                if "bounced" not in cols:
                    try:
                        cursor.execute("ALTER TABLE contacts ADD COLUMN bounced INTEGER DEFAULT 0")
                        conn.commit()
                        Logger.info("Added bounced column to contacts table")
                    except Exception as e:
                        Logger.error(f"Migration error (contacts.bounced): {e}")

                # Check message_logs columns
                cursor.execute("PRAGMA table_info(message_logs)")
                cols = [row[1] for row in cursor.fetchall()]
                if "contact_email" not in cols:
                    try:
                        cursor.execute("ALTER TABLE message_logs ADD COLUMN contact_email TEXT")
                        conn.commit()
                        Logger.info("Added contact_email column to message_logs table")
                    except Exception as e:
                        Logger.error(f"Migration error (message_logs.contact_email): {e}")
                if "subject" not in cols:
                    try:
                        cursor.execute("ALTER TABLE message_logs ADD COLUMN subject TEXT")
                        conn.commit()
                        Logger.info("Added subject column to message_logs table")
                    except Exception as e:
                        Logger.error(f"Migration error (message_logs.subject): {e}")
                if "bounced" not in cols:
                    try:
                        cursor.execute("ALTER TABLE message_logs ADD COLUMN bounced INTEGER DEFAULT 0")
                        conn.commit()
                        Logger.info("Added bounced column to message_logs table")
                    except Exception as e:
                        Logger.error(f"Migration error (message_logs.bounced): {e}")
                if "bounce_reason" not in cols:
                    try:
                        cursor.execute("ALTER TABLE message_logs ADD COLUMN bounce_reason TEXT")
                        conn.commit()
                        Logger.info("Added bounce_reason column to message_logs table")
                    except Exception as e:
                        Logger.error(f"Migration error (message_logs.bounce_reason): {e}")
                if "bounce_checked_at" not in cols:
                    try:
                        cursor.execute("ALTER TABLE message_logs ADD COLUMN bounce_checked_at TIMESTAMP")
                        conn.commit()
                        Logger.info("Added bounce_checked_at column to message_logs table")
                    except Exception as e:
                        Logger.error(f"Migration error (message_logs.bounce_checked_at): {e}")

            self._migrate_contacts_phone_nullable()
        except Exception as e:
            Logger.error(f"Error running database migrations: {e}")

    def _migrate_contacts_phone_nullable(self) -> None:
        """Rebuild `contacts` without a NOT NULL constraint on `phone`, if the
        real on-disk table still has one.

        This is the deferred migration flagged (not silently skipped) when
        the import-review flow was first built: `DEFAULT_SCHEMA_SQL`/
        `schema.sql`'s `CREATE TABLE IF NOT EXISTS contacts` has always
        declared `phone TEXT UNIQUE` (nullable) -- but that only applies to a
        brand-new install. Any database created under an older version of
        this app, before that column was ever NOT NULL-free, keeps the
        constraint forever, since `CREATE TABLE IF NOT EXISTS` never alters
        an existing table. SQLite has no `ALTER TABLE ... DROP CONSTRAINT`,
        so the standard, safe rebuild is: rename the old table, create a
        fresh one from the current schema, copy every row across (converting
        any stored `''` phone to a real `NULL`, which is what makes multiple
        email-only contacts able to coexist under the `UNIQUE` phone index --
        SQLite allows any number of NULLs in a UNIQUE column, but only one
        `''`), drop the old table, recreate the index.

        A real file-level `.bak` copy is taken first (same safety pattern
        already used in this codebase for the SMTP-password-encryption
        migration) -- this only ever runs once per real install (idempotent:
        a fresh/already-migrated DB has no NOT NULL to find and this becomes
        a no-op PRAGMA check on every subsequent startup).
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(contacts)")
                info = cursor.fetchall()
                phone_col = next((r for r in info if r[1] == "phone"), None)
                if phone_col is None or phone_col[3] != 1:
                    return  # no NOT NULL on phone -- nothing to do

            import shutil
            backup_path = f"{self.db_path}.pre-phone-migration.bak"
            if not Path(backup_path).exists():
                shutil.copy2(self.db_path, backup_path)
                Logger.info(f"Backed up database to {backup_path} before phone-nullable migration")

            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("PRAGMA table_info(contacts)")
                cols = [r[1] for r in cursor.fetchall()]
                has_email = "email" in cols
                has_opted_out = "opted_out" in cols
                has_bounced = "bounced" in cols

                cursor.execute("ALTER TABLE contacts RENAME TO contacts_pre_phone_migration")
                cursor.execute("""
                    CREATE TABLE contacts (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        phone TEXT UNIQUE,
                        email TEXT,
                        name TEXT,
                        tags TEXT,
                        custom_fields TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        opted_out INTEGER DEFAULT 0,
                        bounced INTEGER DEFAULT 0
                    )
                """)
                email_expr = "email" if has_email else "NULL"
                opted_out_expr = "opted_out" if has_opted_out else "0"
                bounced_expr = "bounced" if has_bounced else "0"
                cursor.execute(f"""
                    INSERT INTO contacts (id, phone, email, name, tags, custom_fields, created_at, opted_out, bounced)
                    SELECT id, NULLIF(phone, ''), {email_expr}, name, tags, custom_fields, created_at, {opted_out_expr}, {bounced_expr}
                    FROM contacts_pre_phone_migration
                """)
                cursor.execute("DROP TABLE contacts_pre_phone_migration")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(phone)")
                conn.commit()
                Logger.info("Migrated contacts.phone to nullable — email-only contacts can now be saved")
        except Exception as e:
            Logger.error(f"Migration error (contacts.phone nullable): {e}")

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
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
        )
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
                    INSERT INTO contacts (phone, email, name, tags, custom_fields)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        contact.phone or None,
                        contact.email,
                        contact.name,
                        ','.join(contact.tags) if contact.tags else '',
                        json.dumps(contact.custom_fields)
                    )
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.IntegrityError:
            Logger.warning(f"Contact with phone {contact.phone} or email {contact.email} already exists")
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
                            INSERT INTO contacts (phone, email, name, tags, custom_fields)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                contact.phone or None,
                                contact.email,
                                contact.name,
                                ','.join(contact.tags) if contact.tags else '',
                                json.dumps(contact.custom_fields)
                            )
                        )
                        count += 1
                    except sqlite3.IntegrityError:
                        Logger.debug(f"Duplicate contact: {contact.phone} / {contact.email}")
                        continue
                
                conn.commit()
        except Exception as e:
            Logger.error(f"Error adding contacts batch: {e}")

        return count

    def get_existing_phones(self) -> set:
        """Cheap set of every phone already saved — used by import-review
        duplicate detection so it doesn't have to load full Contact objects."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT phone FROM contacts WHERE phone IS NOT NULL AND phone != ''")
                return {row[0] for row in cursor.fetchall()}
        except Exception as e:
            Logger.error(f"Error reading existing phones: {e}")
            return set()

    def update_contact_by_phone(self, phone: str, name: str = "", email: str = "",
                                 custom_fields: Optional[dict] = None) -> bool:
        """Merge new data into an existing contact matched by phone (the
        UNIQUE key) — only overwrites a field if the new value is non-empty,
        so merging never blanks out data the existing contact already had."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name, email, custom_fields FROM contacts WHERE phone = ?", (phone,))
                row = cursor.fetchone()
                if row is None:
                    return False
                # Existing data wins — only fall back to the new value when
                # the existing contact's field is blank (this was backwards
                # before: it must never let an import silently overwrite
                # real data the user already had).
                merged_name = row["name"] or name or ""
                merged_email = row["email"] or email or ""
                try:
                    existing_custom = json.loads(row["custom_fields"] or "{}")
                except (TypeError, ValueError):
                    existing_custom = {}
                existing_custom.update({k: v for k, v in (custom_fields or {}).items() if v})
                cursor.execute(
                    "UPDATE contacts SET name = ?, email = ?, custom_fields = ? WHERE phone = ?",
                    (merged_name, merged_email, json.dumps(existing_custom), phone),
                )
                conn.commit()
                return True
        except Exception as e:
            Logger.error(f"Error merging contact {phone}: {e}")
            return False

    def get_existing_emails(self) -> set:
        """Cheap set of every email already saved — the email-side equivalent
        of `get_existing_phones()`, needed once email-only contacts (no
        phone, so nothing to key duplicate detection off via phone) became
        importable."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT email FROM contacts WHERE email IS NOT NULL AND email != ''")
                return {row[0].lower() for row in cursor.fetchall()}
        except Exception as e:
            Logger.error(f"Error reading existing emails: {e}")
            return set()

    def update_contact_by_email(self, email: str, name: str = "", phone: str = "",
                                 custom_fields: Optional[dict] = None) -> bool:
        """Merge new data into an existing, phone-less contact matched by
        email — same existing-data-wins/fill-blanks-only semantics as
        `update_contact_by_phone`, for rows that have no phone to match on."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT id, name, phone, custom_fields FROM contacts WHERE email = ? COLLATE NOCASE",
                    (email,))
                row = cursor.fetchone()
                if row is None:
                    return False
                merged_name = row["name"] or name or ""
                merged_phone = row["phone"] or (phone or None)
                try:
                    existing_custom = json.loads(row["custom_fields"] or "{}")
                except (TypeError, ValueError):
                    existing_custom = {}
                existing_custom.update({k: v for k, v in (custom_fields or {}).items() if v})
                cursor.execute(
                    "UPDATE contacts SET name = ?, phone = ?, custom_fields = ? WHERE id = ?",
                    (merged_name, merged_phone, json.dumps(existing_custom), row["id"]),
                )
                conn.commit()
                return True
        except Exception as e:
            Logger.error(f"Error merging contact {email}: {e}")
            return False

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
                    email_val = ""
                    try:
                        email_val = row['email'] or ''
                    except (IndexError, sqlite3.OperationalError):
                        pass
                    opted_out_val = False
                    try:
                        opted_out_val = bool(row['opted_out'])
                    except (IndexError, sqlite3.OperationalError):
                        pass
                    bounced_val = False
                    try:
                        bounced_val = bool(row['bounced'])
                    except (IndexError, sqlite3.OperationalError):
                        pass

                    contact = Contact(
                        id=row['id'],
                        phone=row['phone'] or '',
                        email=email_val,
                        name=row['name'] or '',
                        tags=row['tags'].split(',') if row['tags'] else [],
                        custom_fields=json.loads(row['custom_fields']) if row['custom_fields'] else {},
                        created_at=datetime.fromisoformat(row['created_at']),
                        opted_out=opted_out_val,
                        bounced=bounced_val,
                    )
                    contacts.append(contact)

                return contacts
        except Exception as e:
            Logger.error(f"Error getting contacts: {e}")
            return []
    
    def search_contacts(self, query: str) -> List[Contact]:
        """
        Search contacts by name, phone, or email.
        
        Args:
            query: Search query
            
        Returns:
            List of matching Contact objects
        """
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                search_pattern = f"%{query}%"
                
                # Check columns to decide query
                cursor.execute("PRAGMA table_info(contacts)")
                cols = [r[1] for r in cursor.fetchall()]
                if "email" in cols:
                    sql_query = """
                        SELECT * FROM contacts 
                        WHERE phone LIKE ? OR name LIKE ? OR email LIKE ?
                        LIMIT 100
                    """
                    params = (search_pattern, search_pattern, search_pattern)
                else:
                    sql_query = """
                        SELECT * FROM contacts 
                        WHERE phone LIKE ? OR name LIKE ?
                        LIMIT 100
                    """
                    params = (search_pattern, search_pattern)

                cursor.execute(sql_query, params)
                
                contacts = []
                for row in cursor.fetchall():
                    email_val = ""
                    if "email" in cols:
                        email_val = row['email'] or ''
                    opted_out_val = bool(row['opted_out']) if "opted_out" in cols else False

                    contact = Contact(
                        id=row['id'],
                        phone=row['phone'] or '',
                        email=email_val,
                        name=row['name'] or '',
                        tags=row['tags'].split(',') if row['tags'] else [],
                        custom_fields=json.loads(row['custom_fields']) if row['custom_fields'] else {},
                        opted_out=opted_out_val,
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

    def set_contact_opted_out(self, contact_id: int, opted_out: bool) -> bool:
        """Mark a contact as opted-out (or resubscribed). Opted-out contacts
        must be excluded from every future send, both channels — enforced at
        the point contacts are selected for sending, not here."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE contacts SET opted_out = ? WHERE id = ?",
                    (1 if opted_out else 0, contact_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            Logger.error(f"Error setting contact opted_out state: {e}")
            return False

    def set_contact_bounced(self, contact_id: int, bounced: bool) -> bool:
        """Mark a contact as bounced (or clear the flag). Bounced contacts
        must be excluded from future email sends, same enforcement pattern
        as opted_out — enforced at the point contacts are selected for
        sending, not here."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE contacts SET bounced = ? WHERE id = ?",
                    (1 if bounced else 0, contact_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            Logger.error(f"Error setting contact bounced state: {e}")
            return False

    def set_contact_bounced_by_email(self, email: str, bounced: bool = True) -> bool:
        """Same as set_contact_bounced, but matched by email address
        (case-insensitive) — the address a bounce reconciliation actually
        has, not a contact id. Returns True only if a real contact row was
        matched and updated."""
        if not email:
            return False
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE contacts SET bounced = ? WHERE email = ? COLLATE NOCASE",
                    (1 if bounced else 0, email))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            Logger.error(f"Error setting contact bounced state by email {email}: {e}")
            return False

    def delete_all_contacts(self) -> int:
        """Delete every contact. Returns the number of rows removed."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM contacts")
                conn.commit()
                return cursor.rowcount
        except Exception as e:
            Logger.error(f"Error deleting all contacts: {e}")
            return 0

    def clear_campaign_history(self) -> int:
        """Delete every campaign and message log row. Returns rows removed
        (campaigns + message_logs combined)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM message_logs")
                removed = cursor.rowcount
                cursor.execute("DELETE FROM campaigns")
                removed += cursor.rowcount
                conn.commit()
                return removed
        except Exception as e:
            Logger.error(f"Error clearing campaign history: {e}")
            return 0

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
    
    def update_campaign(self, campaign_id: int, sent_count: int, failed_count: int) -> bool:
        """Update campaign sent/failed counts after completion."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE campaigns
                    SET sent_count = ?, failed_count = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                    """,
                    (sent_count, failed_count, campaign_id),
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            Logger.error(f"Error updating campaign: {e}")
            return False

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
                
                # Check columns to decide query
                cursor.execute("PRAGMA table_info(message_logs)")
                cols = [r[1] for r in cursor.fetchall()]
                
                if "contact_email" in cols and "subject" in cols:
                    sql_query = """
                        INSERT INTO message_logs 
                        (campaign_id, contact_phone, contact_email, contact_name, subject, message_text, status, 
                         sent_at, error_message, retry_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    params = (
                        log.campaign_id,
                        log.contact_phone,
                        log.contact_email,
                        log.contact_name,
                        log.subject,
                        log.message_text,
                        log.status.value,
                        log.sent_at.isoformat() if log.sent_at else None,
                        log.error_message,
                        log.retry_count
                    )
                else:
                    sql_query = """
                        INSERT INTO message_logs 
                        (campaign_id, contact_phone, contact_name, message_text, status, 
                         sent_at, error_message, retry_count)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    params = (
                        log.campaign_id,
                        log.contact_phone,
                        log.contact_name,
                        log.message_text,
                        log.status.value,
                        log.sent_at.isoformat() if log.sent_at else None,
                        log.error_message,
                        log.retry_count
                    )

                cursor.execute(sql_query, params)
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
                
                cursor.execute("PRAGMA table_info(message_logs)")
                cols = [r[1] for r in cursor.fetchall()]
                
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
                    contact_email_val = ""
                    subject_val = ""
                    if "contact_email" in cols:
                        contact_email_val = row['contact_email'] or ''
                    if "subject" in cols:
                        subject_val = row['subject'] or ''
                    bounced_val = bool(row['bounced']) if "bounced" in cols else False
                    bounce_reason_val = row['bounce_reason'] if "bounce_reason" in cols else None
                    bounce_checked_val = None
                    if "bounce_checked_at" in cols and row['bounce_checked_at']:
                        bounce_checked_val = datetime.fromisoformat(row['bounce_checked_at'])

                    log = MessageLog(
                        id=row['id'],
                        campaign_id=row['campaign_id'],
                        contact_phone=row['contact_phone'] or '',
                        contact_email=contact_email_val,
                        contact_name=row['contact_name'] or '',
                        subject=subject_val,
                        message_text=row['message_text'],
                        status=MessageStatus(row['status']),
                        sent_at=datetime.fromisoformat(row['sent_at']) if row['sent_at'] else None,
                        error_message=row['error_message'],
                        retry_count=row['retry_count'],
                        bounced=bounced_val,
                        bounce_reason=bounce_reason_val,
                        bounce_checked_at=bounce_checked_val,
                    )
                    logs.append(log)

                return logs
        except Exception as e:
            Logger.error(f"Error getting message logs: {e}")
            return []

    def get_sent_email_logs_for_bounce_check(self, campaign_id: int) -> List[MessageLog]:
        """Real, already-sent (SMTP-accepted) email rows for one campaign
        that haven't been reconciled against a bounce yet — the candidate
        set a bounce check cross-references real inbox NDRs against.
        Deliberately scoped to status='sent' (never 'failed' — those are
        already known failures, not something bounce-checking should
        touch) and bounced=0 (a row already confirmed bounced doesn't need
        re-checking, though re-running is harmless either way)."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM message_logs "
                    "WHERE campaign_id = ? AND status = 'sent' AND bounced = 0 "
                    "AND contact_email IS NOT NULL AND contact_email != ''",
                    (campaign_id,)
                )
                logs = []
                for row in cursor.fetchall():
                    logs.append(MessageLog(
                        id=row['id'],
                        campaign_id=row['campaign_id'],
                        contact_phone=row['contact_phone'] or '',
                        contact_email=row['contact_email'] or '',
                        contact_name=row['contact_name'] or '',
                        subject=row['subject'] or '',
                        message_text=row['message_text'],
                        status=MessageStatus(row['status']),
                        sent_at=datetime.fromisoformat(row['sent_at']) if row['sent_at'] else None,
                        error_message=row['error_message'],
                        retry_count=row['retry_count'],
                        bounced=bool(row['bounced']),
                        bounce_reason=row['bounce_reason'],
                        bounce_checked_at=datetime.fromisoformat(row['bounce_checked_at']) if row['bounce_checked_at'] else None,
                    ))
                return logs
        except Exception as e:
            Logger.error(f"Error getting sent email logs for bounce check (campaign {campaign_id}): {e}")
            return []

    def mark_message_log_bounced(self, log_id: int, reason: str) -> bool:
        """Reconcile one message_logs row as a confirmed bounce, found by a
        real IMAP bounce check. status is intentionally left as 'sent'
        (SMTP genuinely accepted it — that fact doesn't change) — bounced
        is a separate, later-confirmed flag layered on top, so the existing
        warm-up/daily-limit counters that count status='sent' rows aren't
        retroactively corrupted by a bounce discovered days later."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE message_logs SET bounced = 1, bounce_reason = ?, "
                    "bounce_checked_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (reason, log_id))
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            Logger.error(f"Error marking message log {log_id} bounced: {e}")
            return False

    def get_campaign_bounce_stats(self, campaign_id: int) -> dict:
        """Real bounced count + list of (email, reason) for one campaign —
        used by the report UI to show a genuine, reconciled Bounced count
        instead of assuming every SMTP-accepted send was delivered."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT contact_name, contact_email, bounce_reason FROM message_logs "
                    "WHERE campaign_id = ? AND bounced = 1",
                    (campaign_id,)
                )
                rows = cursor.fetchall()
                return {
                    "bounced_count": len(rows),
                    "bounced": [(r["contact_name"] or r["contact_email"], r["contact_email"], r["bounce_reason"]) for r in rows],
                }
        except Exception as e:
            Logger.error(f"Error getting bounce stats for campaign {campaign_id}: {e}")
            return {"bounced_count": 0, "bounced": []}

    def get_email_stats_since(self, since_date_iso: str) -> dict:
        """Sent/failed counts of message_logs rows (the email path) created
        on or after the given LOCAL calendar day, for the reputation
        indicator's failure-rate signal. Uses `created_at` (always
        populated by the DB default, unlike `sent_at` which is null for a
        failed attempt) rather than `sent_at`, so failed sends are
        correctly included in the window.

        Real bug found and fixed while writing this method's own tests:
        `created_at`'s DEFAULT CURRENT_TIMESTAMP is SQLite's own UTC clock,
        but every caller in this app (get_email_sent_count_on, the warm-up
        scheduler) reasons in local calendar dates via date.today(). A first
        version compared the raw stored string directly against the local
        date string and returned zero rows whenever local time had already
        crossed into a new calendar day but UTC hadn't yet (reproduced for
        real on this dev machine, UTC+5, confirmed by inserting rows and
        reading back created_at). Fixed with SQLite's own `datetime(...,
        'localtime')` conversion so this function's date parameter means
        the same "local calendar day" as every other caller in the app,
        not a silent UTC/local mismatch."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT status, COUNT(*) FROM message_logs "
                    "WHERE date(datetime(created_at, 'localtime')) >= date(?) GROUP BY status",
                    (since_date_iso,)
                )
                counts = {row[0]: row[1] for row in cursor.fetchall()}
                return {"sent": counts.get("sent", 0), "failed": counts.get("failed", 0)}
        except Exception as e:
            Logger.error(f"Error getting email stats since {since_date_iso}: {e}")
            return {"sent": 0, "failed": 0}

    def get_email_sent_count_on(self, target_date_iso: str) -> int:
        """Count of message_logs rows (the email send path) with status
        'sent' whose sent_at falls on the given calendar day, for the
        email warm-up scheduler's cumulative daily cap. `target_date_iso`
        is a "YYYY-MM-DD" string; sent_at is stored as a full
        datetime.isoformat() string, so a substring prefix match is used
        rather than SQLite's own date() parsing to avoid any ambiguity
        from the embedded time/microseconds component."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT COUNT(*) FROM message_logs "
                    "WHERE status = 'sent' AND substr(sent_at, 1, 10) = ?",
                    (target_date_iso,)
                )
                row = cursor.fetchone()
                return int(row[0]) if row else 0
        except Exception as e:
            Logger.error(f"Error counting today's sent emails: {e}")
            return 0

    def get_daily_sent_counts(self, days: int = 7) -> List[int]:
        """Item 37 (UI/UX benchmark pass): real per-day send-volume counts
        for the last `days` calendar days (oldest first, today last) —
        combines both real send paths (email `message_logs`, status='sent';
        WhatsApp `messages`, status in sent/delivered/read), grouped by the
        `sent_at` column's own stored local date (both paths write
        `sent_at` via Python's local `datetime.now()`, not SQLite's UTC
        `CURRENT_TIMESTAMP` default -- confirmed directly in the code that
        writes each, so no timezone-conversion is needed here, unlike the
        `created_at`-based UTC/local bug already found and fixed elsewhere
        in this file for `get_email_stats_since`). Powers a real sparkline
        trend on the Campaigns dashboard instead of a single static number
        -- always real, already-logged data, never invented."""
        from datetime import date as _date, timedelta as _timedelta
        today = _date.today()
        day_keys = [(today - _timedelta(days=offset)).isoformat() for offset in range(days - 1, -1, -1)]
        counts = {key: 0 for key in day_keys}
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT substr(sent_at, 1, 10) AS day, COUNT(*) AS n FROM message_logs "
                    "WHERE status = 'sent' AND substr(sent_at, 1, 10) >= ? GROUP BY day",
                    (day_keys[0],)
                )
                for row in cursor.fetchall():
                    if row["day"] in counts:
                        counts[row["day"]] += int(row["n"] or 0)

                cursor.execute(
                    "SELECT substr(sent_at, 1, 10) AS day, COUNT(*) AS n FROM messages "
                    "WHERE status IN ('sent', 'delivered', 'read') AND substr(sent_at, 1, 10) >= ? "
                    "GROUP BY day",
                    (day_keys[0],)
                )
                for row in cursor.fetchall():
                    if row["day"] in counts:
                        counts[row["day"]] += int(row["n"] or 0)
        except Exception as e:
            Logger.error(f"Error getting daily sent counts: {e}")
        return [counts[key] for key in day_keys]

    # Delivery Tracking Operations
    def create_tracked_message(
        self,
        phone: str,
        message_text: str,
        status: str = "pending",
        sent_at: Optional[datetime] = None,
        delivered_at: Optional[datetime] = None,
        read_at: Optional[datetime] = None,
        error_reason: Optional[str] = None,
        whatsapp_message_id: Optional[str] = None,
    ) -> Optional[int]:
        """Create a tracked outbound message record."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO messages
                    (phone, message_text, status, sent_at, delivered_at, read_at, error_reason, whatsapp_message_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        phone,
                        message_text,
                        status,
                        sent_at.isoformat() if sent_at else None,
                        delivered_at.isoformat() if delivered_at else None,
                        read_at.isoformat() if read_at else None,
                        error_reason,
                        whatsapp_message_id,
                    )
                )
                conn.commit()
                return cursor.lastrowid
        except Exception as e:
            Logger.error(f"Error creating tracked message: {e}")
            return None

    def update_tracked_message(self, message_id: int, **fields: Any) -> bool:
        """Update tracked message fields by ID."""
        allowed_fields = {
            "phone",
            "message_text",
            "status",
            "sent_at",
            "delivered_at",
            "read_at",
            "error_reason",
            "whatsapp_message_id",
        }
        updates: List[str] = []
        values: List[Any] = []

        for key, value in fields.items():
            if key not in allowed_fields:
                continue
            if isinstance(value, datetime):
                value = value.isoformat()
            updates.append(f"{key} = ?")
            values.append(value)

        if not updates:
            return False

        values.append(message_id)

        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"UPDATE messages SET {', '.join(updates)} WHERE id = ?",
                    values,
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception as e:
            Logger.error(f"Error updating tracked message: {e}")
            return False

    def get_tracked_messages(self, statuses: Optional[List[str]] = None, limit: int = 100) -> List[Dict[str, Any]]:
        """Return tracked message rows as dictionaries."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM messages"
                params: List[Any] = []

                if statuses:
                    placeholders = ", ".join("?" for _ in statuses)
                    query += f" WHERE status IN ({placeholders})"
                    params.extend(statuses)

                query += " ORDER BY created_at DESC LIMIT ?"
                params.append(limit)

                cursor.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]
        except Exception as e:
            Logger.error(f"Error getting tracked messages: {e}")
            return []

    def get_tracked_message_stats(self) -> Dict[str, Any]:
        """Aggregate delivery tracking statistics."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT
                        SUM(CASE WHEN status IN ('sent', 'delivered', 'read') THEN 1 ELSE 0 END) AS sent_count,
                        SUM(CASE WHEN status IN ('delivered', 'read') THEN 1 ELSE 0 END) AS delivered_count,
                        SUM(CASE WHEN status = 'read' THEN 1 ELSE 0 END) AS read_count,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                        COUNT(*) AS total_count
                    FROM messages
                    """
                )
                row = cursor.fetchone()
                total = int(row["total_count"] or 0)
                delivered = int(row["delivered_count"] or 0)
                return {
                    "sent_count": int(row["sent_count"] or 0),
                    "delivered_count": delivered,
                    "read_count": int(row["read_count"] or 0),
                    "failed_count": int(row["failed_count"] or 0),
                    "delivery_rate": round((delivered / total) * 100, 2) if total else 0.0,
                    "total_count": total,
                }
        except Exception as e:
            Logger.error(f"Error getting tracked message stats: {e}")
            return {
                "sent_count": 0,
                "delivered_count": 0,
                "read_count": 0,
                "failed_count": 0,
                "delivery_rate": 0.0,
                "total_count": 0,
            }

    def get_message_stats_for_period(self, period: str = "today") -> Dict[str, Any]:
        """Return sent/read/failed counts filtered by period (today, week, month, all)."""
        clauses = {
            "today": "date(created_at) = date('now', 'localtime')",
            "week": "created_at >= datetime('now', '-7 days', 'localtime')",
            "month": "created_at >= datetime('now', '-30 days', 'localtime')",
            "all": "1=1",
        }
        where = clauses.get(period, clauses["today"])
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    f"""
                    SELECT
                        SUM(CASE WHEN status IN ('sent', 'delivered', 'read') THEN 1 ELSE 0 END) AS sent_count,
                        SUM(CASE WHEN status = 'read' THEN 1 ELSE 0 END) AS read_count,
                        SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) AS failed_count,
                        COUNT(*) AS total_count
                    FROM messages
                    WHERE {where}
                    """
                )
                row = cursor.fetchone()
                total = int(row["total_count"] or 0)
                sent = int(row["sent_count"] or 0)
                return {
                    "sent_count": sent,
                    "read_count": int(row["read_count"] or 0),
                    "failed_count": int(row["failed_count"] or 0),
                    "total_count": total,
                    "success_rate": round((sent / total) * 100, 1) if total else 0.0,
                }
        except Exception as exc:
            Logger.error(f"Period stats error: {exc}")
            return {"sent_count": 0, "read_count": 0, "failed_count": 0, "total_count": 0, "success_rate": 0.0}

    def get_recent_campaigns_summary(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Return recent campaigns with name, date, sent count, message
        template, and a real reconciled bounced_count — a campaign row with
        bounced=0 for every message just means "no bounce confirmed (yet)",
        not "confirmed zero bounces"; the UI is responsible for wording that
        honestly, not this query."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT c.id, c.name, c.sent_count, c.failed_count, c.created_at, c.message_template,
                           (SELECT COUNT(*) FROM message_logs ml
                            WHERE ml.campaign_id = c.id AND ml.bounced = 1) AS bounced_count
                    FROM campaigns c
                    ORDER BY c.created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
                return [dict(row) for row in cursor.fetchall()]
        except Exception as exc:
            Logger.error(f"Campaign summary error: {exc}")
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

    def set_setting_json(self, key: str, value: Any) -> bool:
        """Store structured setting data as JSON."""
        try:
            return self.set_setting(key, json.dumps(value))
        except Exception as e:
            Logger.error(f"Error setting JSON setting: {e}")
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

    def get_setting_json(self, key: str, default: Optional[Any] = None) -> Any:
        """Read structured setting data stored as JSON."""
        raw_value = self.get_setting(key, "")
        if not raw_value:
            return default

        try:
            return json.loads(raw_value)
        except json.JSONDecodeError:
            Logger.warning(f"Invalid JSON stored for setting {key}")
            return default
