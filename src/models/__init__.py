"""
Data Models for MessageCannon Application
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum


class MessageStatus(Enum):
    """Message delivery status."""
    PENDING = "pending"
    SENDING = "sending"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"
    FAILED_RETRY = "failed_retry"


@dataclass
class Contact:
    """Contact data model."""
    
    id: Optional[int] = None
    phone: str = ""
    email: str = ""
    name: str = ""
    tags: List[str] = field(default_factory=list)
    custom_fields: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['tags'] = ','.join(self.tags)
        data['created_at'] = self.created_at.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Contact':
        """Create from dictionary."""
        contact = cls()
        contact.id = data.get('id')
        contact.phone = data.get('phone', '')
        contact.email = data.get('email', '')
        contact.name = data.get('name', '')
        contact.tags = data.get('tags', '').split(',') if data.get('tags') else []
        contact.custom_fields = data.get('custom_fields', {})
        
        if isinstance(data.get('created_at'), str):
            contact.created_at = datetime.fromisoformat(data['created_at'])
        
        return contact


@dataclass
class MessageLog:
    """Message sending log entry."""
    
    id: Optional[int] = None
    campaign_id: Optional[int] = None
    contact_phone: str = ""
    contact_email: str = ""
    contact_name: str = ""
    subject: str = ""
    message_text: str = ""
    status: MessageStatus = MessageStatus.PENDING
    sent_at: Optional[datetime] = None
    error_message: Optional[str] = None
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'campaign_id': self.campaign_id,
            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,
            'contact_name': self.contact_name,
            'subject': self.subject,
            'message_text': self.message_text,
            'status': self.status.value,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
        }
        return data


@dataclass
class Campaign:
    """Campaign data model."""
    
    id: Optional[int] = None
    name: str = ""
    message_template: str = ""
    total_contacts: int = 0
    sent_count: int = 0
    failed_count: int = 0
    message_delay: int = 30
    use_jitter: bool = True
    scheduled_time: Optional[datetime] = None
    is_recurring: bool = False
    recurrence_pattern: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'message_template': self.message_template,
            'total_contacts': self.total_contacts,
            'sent_count': self.sent_count,
            'failed_count': self.failed_count,
            'message_delay': self.message_delay,
            'use_jitter': self.use_jitter,
            'scheduled_time': self.scheduled_time.isoformat() if self.scheduled_time else None,
            'is_recurring': self.is_recurring,
            'recurrence_pattern': self.recurrence_pattern,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }
        return data


@dataclass
class Template:
    """Message template data model."""
    
    id: Optional[int] = None
    name: str = ""
    category: str = ""  # e.g., "Fee Reminder", "Appointment"
    message_text: str = ""
    description: Optional[str] = None
    is_default: bool = False
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = {
            'id': self.id,
            'name': self.name,
            'category': self.category,
            'message_text': self.message_text,
            'description': self.description,
            'is_default': self.is_default,
            'created_at': self.created_at.isoformat(),
        }
        return data


@dataclass
class Settings:
    """Application settings data model."""
    
    theme: str = "dark"  # "dark" or "light"
    language: str = "en"  # "en" or "ur"
    notifications_enabled: bool = True
    delay_preset: str = "normal"  # "fast", "normal", "safe", "custom"
    custom_delay: int = 30
    use_jitter: bool = True
    auto_backup_enabled: bool = True
    backup_frequency: str = "weekly"  # "daily", "weekly", "monthly"
    license_key: Optional[str] = None
    portable_mode: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Settings':
        """Create from dictionary."""
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
