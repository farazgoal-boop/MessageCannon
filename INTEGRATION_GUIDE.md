# MessageCannon Pro — Integration Guide
# How to plug in the new Email + Data Import modules

## 1. File Structure

Place these new files into your existing project:

```
MessageCannon/
├── src/
│   ├── main.py                       ← EXISTING (edit as shown below)
│   ├── modules/
│   │   ├── data_importer.py          ← NEW ✅
│   │   ├── email_sender.py           ← NEW ✅
│   │   └── license_manager.py        ← NEW ✅
│   └── ui/
│       └── email_tab.py              ← NEW ✅
```

## 2. Install new dependencies

Add to requirements.txt:
```
openpyxl>=3.1.2
```

Run:
```
pip install openpyxl
```

All other modules (smtplib, csv, html.parser) are Python built-ins — no extra installs.

## 3. Edit main.py — add 3 blocks

### Block A: License check at startup
Find your main window creation code and add BEFORE mainloop():

```python
from modules.license_manager import require_license

# ... existing window setup ...

if not require_license(root):
    exit()          # no valid license, exit

root.mainloop()
```

### Block B: Add Email tab to notebook
Find where you add tabs to your ttk.Notebook and add:

```python
from ui.email_tab import EmailTab

# ... existing tabs ...

email_tab = EmailTab(notebook)
notebook.add(email_tab, text="📧 Email")
```

### Block C: Upgrade existing CSV import to use UniversalDataImporter
Find your existing import button handler and replace the CSV-only logic with:

```python
from modules.data_importer import UniversalDataImporter

def import_contacts(self):
    path = filedialog.askopenfilename(
        title="Import Contacts",
        filetypes=[
            ("All supported", "*.csv *.xls *.xlsx *.html *.htm"),
            ("CSV",   "*.csv"),
            ("Excel", "*.xls *.xlsx"),
            ("HTML",  "*.html *.htm"),
        ]
    )
    if not path:
        return
    
    importer = UniversalDataImporter()
    result   = importer.import_file(path)
    
    # result.contacts  → list of dicts with name, email, phone, custom_*
    # result.total     → int
    # result.skipped   → int
    # result.errors    → list of strings
    
    self.contacts = result.contacts
    self.refresh_contact_list()   # your existing UI update
    
    if result.errors:
        messagebox.showwarning("Import Warnings", "\n".join(result.errors[:5]))
    
    messagebox.showinfo("Import Complete", result.summary())
```

## 4. Generate License Keys (seller side)

When a customer pays $89, run this on your machine:

```python
from src.modules.license_manager import LicenseManager

key = LicenseManager.generate_key(
    email="customer@example.com",
    tier="single",
    days=36500     # ~100 years = lifetime license
)
print(key)
# Output: XXXX-XXXX-XXXX-XXXX
# Send this to the customer by email.
```

⚠️ IMPORTANT: Change _SECRET in license_manager.py before shipping.
   Use a long random string only you know.

## 5. Build EXE with new modules

No changes to build.bat needed — PyInstaller picks up new modules automatically.

Just rebuild:
```
build.bat
```

## 6. What each new file does

| File | What it adds |
|------|-------------|
| data_importer.py | Read CSV / Excel / HTML → unified contact list |
| email_sender.py  | SMTP bulk email, HTML templates, tracking pixels |
| email_tab.py     | Full email campaign tab UI for your tkinter app |
| license_manager.py | $89 license keys, activation dialog, offline validation |

## 7. Upgrade your pricing now

With Email + WhatsApp + Universal Import, your app is worth $89.

Suggested new pricing table for README:

| Package         | Price                    |
|-----------------|--------------------------|
| Single License  | $89 USD / Rs 25,000 PKR  |
| 5-Pack          | $299 USD / Rs 85,000 PKR |
| Agency (10-pack)| $499 USD                 |

## 8. What to sell in your marketing

"MessageCannon Pro is the ONLY tool that lets Pakistani businesses send both
WhatsApp AND Email campaigns from one app, import contacts from ANY file format
(CSV, Excel, HTML), with built-in professional HTML email templates — for a
one-time payment of $89."
