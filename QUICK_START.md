# MessageCannon - Quick Start Guide

## 🚀 Run the Application RIGHT NOW

```bash
# Step 1: Open terminal in MessageCannon directory
cd d:\my apps\MessageCannon

# Step 2: Install dependencies (one-time only)
pip install -r requirements.txt

# Step 3: Run the app
python src/main.py
```

**That's it!** The application will launch with the CustomTkinter UI.

---

## ⚙️ First Time Setup

1. **License Check**: App will check for trial license
2. **First-Run Warning**: Read WhatsApp policy compliance notice
3. **Theme Selection**: Choose Dark or Light theme
4. **Welcome**: Main UI appears with 3-column layout

---

## 🎯 Test Workflow (2 minutes)

### 1. Import Test Contacts
```
Left Panel → "Import Contacts"
→ Select: tests/sample_contacts.csv
→ 10 sample contacts loaded
→ Verify phone numbers are formatted correctly
```

### 2. Create Test Message
```
Center Panel → "New Message"
→ Template: "Fee Reminder"
→ Verify variables: {name}, {amount}, {due_date}
→ Preview shows personalized messages
```

### 3. Send Test Message
```
Right Panel → "Send Campaign"
→ Check "I have consent from all recipients"
→ Click "Start Sending"
→ Watch progress bar
→ Verify delay is working (30s between messages)
→ Check status log
```

### 4. View Report
```
Menu → "Analytics"
→ See campaign summary
→ Export as PDF/Excel
→ Verify all messages logged
```

---

## 🔨 Build Standalone EXE

**For Windows Distribution:**

```bash
# Run build script
build.bat

# Wait for PyInstaller to complete
# Result: dist/MessageCannon.exe (single file, no Python needed)

# Test EXE
dist/MessageCannon.exe
```

**File Size:** ~150-200 MB (includes Python runtime)

---

## 📦 Create Portable Version

**For USB Distribution:**

```bash
# Run portable build
portable_build.bat

# Result: MessageCannon_Portable/ folder
# Can run from USB drive on any Windows PC
# No installation required
```

**File Size:** ~180-220 MB

---

## 🔧 Common Tasks

### Change Theme
```
File → Settings → Theme
→ Choose Dark or Light
→ Restart app to apply
```

### Add Custom Delay
```
File → Settings → Sending Options
→ Delay: 15-60 seconds (default 30)
→ Enable Jitter: ±5 seconds random variation
→ Save & restart
```

### Export Campaign Report
```
Analytics → Select Campaign
→ Export as PDF or Excel
→ File saved to: Documents/MessageCannon/reports/
```

### Create Custom Template
```
Templates → New Template
→ Name: "My Template"
→ Category: "Business"
→ Message: "Hello {name}, your {custom1} is ready"
→ Save
```

### View Message History
```
History → Search by:
→ Date range
→ Contact name
→ Campaign name
→ Status (Success/Failed)
```

---

## 📊 Database Locations

**Database File:**
```
C:\Users\{YourUsername}\AppData\Local\MessageCannon\messagecannon.db
```

**Backups:**
```
C:\Users\{YourUsername}\AppData\Local\MessageCannon\backups/
```

**Logs:**
```
C:\Users\{YourUsername}\AppData\Local\MessageCannon\logs/messagecannon.log
```

**Settings:**
```
C:\Users\{YourUsername}\AppData\Local\MessageCannon/settings.json
```

---

## 🐛 Troubleshooting

### App won't start
```
1. Check Python version: python --version (must be 3.8+)
2. Reinstall dependencies: pip install -r requirements.txt --force-reinstall
3. Check logs: C:\Users\{You}\AppData\Local\MessageCannon\logs\
```

### WhatsApp QR scan fails
```
1. Make sure you're logged OUT of WhatsApp Web (web.whatsapp.com)
2. Close all Chrome/Edge windows
3. Try again - QR modal should appear
4. Scan with your phone
```

### Contacts won't import
```
1. Check CSV format: phone, name, amount (columns must exist)
2. Verify phone numbers start with +92 or 03
3. Check for special characters in names
4. See logs for detailed error
```

### Messages stuck on "Sending"
```
1. Click "Pause" then "Resume"
2. If still stuck, click "Cancel" and try again
3. Check WhatsApp Web session (may be disconnected)
4. Rescan QR code if needed
```

---

## 🎓 File Structure Quick Reference

**Where to Find Things:**

| What | Where |
|------|-------|
| Main UI code | `src/ui/main_window.py` |
| WhatsApp sending | `src/core/whatsapp_sender.py` |
| Database | `src/database/db_manager.py` |
| Phone validation | `src/utils/validators.py` |
| Settings | `src/utils/constants.py` |
| Themes | `src/assets/themes/` |
| Templates | `src/assets/templates/` |
| Tests | `tests/test_core.py` |
| Docs | `docs/` |

---

## 💡 Pro Tips

✅ **Always use templates** for consistency across campaigns

✅ **Enable jitter** for more natural delays (less spam-like)

✅ **Export reports** after each campaign for record-keeping

✅ **Test with 1-2 contacts** before sending to large lists

✅ **Check logs regularly** to monitor message status

✅ **Keep backup of contacts** - export as CSV monthly

✅ **Review WhatsApp guidelines** (in docs/) before using

---

## 📞 Support

- **GitHub Issues:** Report bugs here
- **Email:** farazgoal@gmail.com
- **Documentation:** `docs/` folder

---

## 🎯 Next Steps

1. ✅ Run `python src/main.py` → Test UI
2. ✅ Import test contacts → Verify data handling
3. ✅ Create sample campaign → Test core logic
4. ✅ Run `build.bat` → Create EXE
5. ✅ Test EXE on clean PC → Verify distribution
6. ✅ Read docs/ → Understand compliance
7. ✅ Consider commercial license → Monetize

---

**Ready to go!** 🚀

Start with: `python src/main.py`
