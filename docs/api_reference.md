# MessageCannon API Reference

## Core Modules

### Contact Manager

```python
from src.core.contact_manager import ContactManager

cm = ContactManager()

# Import from file
count, errors = cm.import_from_file("contacts.xlsx")

# Get all contacts
contacts = cm.get_all_contacts()

# Search contacts
results = cm.search_contacts("Ahmed")

# Export contacts
cm.export_contacts("export.csv", contacts)

# Detect issues
issues = cm.detect_issues(contacts)
```

### Message Processor

```python
from src.core.message_processor import MessageProcessor

mp = MessageProcessor()

# Substitute variables
message, success = mp.substitute_variables(
    "Hello {name}, your amount is {amount}",
    contact
)

# Validate template
is_valid, warnings = mp.validate_template(message)

# Get variables
vars = mp.get_template_variables(template)

# Process batch
logs = mp.process_batch(template, contacts)
```

### WhatsApp Sender

```python
from src.core.whatsapp_sender import WhatsAppSender

sender = WhatsAppSender()

# Send messages
result = sender.send_messages(
    contacts=contacts,
    messages=messages,
    delay=30,
    use_jitter=True,
    max_messages=50,
    progress_callback=lambda i, t, m: print(f"{i}/{t}")
)

# Pause/Resume/Stop
sender.pause_sending()
sender.resume_sending()
sender.stop_sending()

# Get status
status = sender.get_status()
progress = sender.get_progress(100)
```

### Export Manager

```python
from src.core.export_manager import ExportManager

em = ExportManager()

# Export as PDF
em.export_campaign_pdf(campaign, logs, "report.pdf")

# Export as Excel
em.export_campaign_excel(campaign, logs, "report.xlsx")
```

## Data Models

### Contact

```python
from src.models import Contact

contact = Contact(
    phone="+923001234567",
    name="Ahmed Khan",
    tags=["VIP", "Premium"],
    custom_fields={"amount": "5000", "due_date": "2026-05-25"}
)

# Convert to dict
data = contact.to_dict()

# Create from dict
contact = Contact.from_dict(data)
```

### Campaign

```python
from src.models import Campaign

campaign = Campaign(
    name="Fee Reminder",
    message_template="Dear {name}, your fee is due",
    total_contacts=100,
    message_delay=30,
    use_jitter=True
)

# Convert to dict
data = campaign.to_dict()
```

### MessageLog

```python
from src.models import MessageLog, MessageStatus

log = MessageLog(
    contact_phone="+923001234567",
    contact_name="Ahmed Khan",
    message_text="Hello Ahmed",
    status=MessageStatus.SENT
)

# Check status
if log.status == MessageStatus.SENT:
    print("Message sent successfully")
```

## Database Operations

```python
from src.database.db_manager import DatabaseManager

db = DatabaseManager()

# Add contacts
contact_id = db.add_contact(contact)

# Batch add
count = db.add_contacts_batch(contacts)

# Get contacts
contacts = db.get_contacts(limit=50, offset=0)

# Search
results = db.search_contacts("Ahmed")

# Count
total = db.get_contact_count()

# Add campaign
campaign_id = db.add_campaign(campaign)

# Get campaigns
campaigns = db.get_campaigns(limit=10)

# Message logs
db.add_message_log(log)
logs = db.get_message_logs(campaign_id)

# Templates
db.add_template(template)
templates = db.get_templates()

# Settings
db.set_setting("theme", "dark")
theme = db.get_setting("theme", "dark")
```

## Utilities

### Validators

```python
from src.utils.validators import PhoneValidator, DataValidator

# Validate phone
is_valid = PhoneValidator.is_valid_pakistan_format("+923001234567")

# Normalize phone
phone, error = PhoneValidator.normalize_phone("03001234567")

# Detect duplicates
dupes = PhoneValidator.detect_duplicates(phone_list)

# Validate email
is_valid = DataValidator.is_valid_email("test@example.com")

# Validate message length
is_valid, msg = DataValidator.validate_message_length(text)

# Validate CSV headers
is_valid, error = DataValidator.is_valid_csv_headers(headers, required)

# Validate variables
is_valid, invalid_vars = DataValidator.validate_template_variables(
    message, 
    ["{name}", "{amount}"]
)
```

### Logger

```python
from src.utils.logger import Logger

Logger.debug("Debug message")
Logger.info("Info message")
Logger.warning("Warning message")
Logger.error("Error message")
Logger.critical("Critical message")

# Or use convenience function
from src.utils.logger import get_logger
logger = get_logger()
```

### Helpers

```python
from src.utils.helpers import *

# Get app directories
app_dir = get_app_data_dir()
config_dir = get_config_dir()
db_path = get_database_path()

# JSON operations
save_json({"key": "value"}, "config.json")
data = load_json("config.json")

# Format/utilities
formatted = format_timestamp(datetime.now())
truncated = truncate_string("Long text", max_length=50)
display = format_phone_display("+923001234567")
humanized = humanize_number(1500000)
eta = calculate_eta(current=50, total=100, elapsed_seconds=30)

# First launch check
if is_first_launch():
    mark_first_launch_complete()
```

### License Manager

```python
from src.utils.license_manager import LicenseManager

# Check license
license_info = LicenseManager.check_license()
# Returns: {"status": "trial", "days_remaining": 14, "is_trial": true, "is_valid": true}

# Activate license
result = LicenseManager.activate_license("MessageCannon-key-hash")
# Returns: {"success": true, "message": "License activated successfully"}
```

---

For more details, see the docstrings in the source code.
