# MessageCannon User Guide

## Getting Started

### Installation

1. **Download & Install**
   - Download `MessageCannon_Setup.exe`
   - Run the installer
   - Follow the installation wizard
   - Launch from the desktop shortcut

2. **First Launch**
   - You'll see a compliance warning about WhatsApp usage
   - Read carefully and agree to proceed
   - This is shown only on first launch

### Importing Contacts

1. Click **Import Contacts** in the left panel
2. Select your Excel (.xlsx) or CSV file
3. Ensure your file has these columns:
   - `phone` (required): Phone number in format +92XXXXXXXXXX or 03XXXXXXXXXX
   - `name` (optional): Contact name
   - Any other columns become custom fields

4. Review the preview (first 20 rows)
5. Click Import

### Composing Messages

1. Choose a template or write custom message
2. Use variables for personalization:
   - `{name}` - Contact name
   - `{phone}` - Phone number
   - `{amount}` - Amount (custom field)
   - `{date}` - Date (custom field)
   - `{due_date}` - Due date (custom field)

3. Watch the character counter (WhatsApp limit: 65,536)
4. Preview before sending

### Sending Messages

1. **Configure Settings:**
   - Set message delay (10-60 seconds)
   - Enable/disable random jitter
   - Set maximum messages per session (max 50)

2. **Confirm Consent:**
   - Check "✓ Recipient Consent" before sending
   - This ensures you have permission from recipients

3. **Send Campaign:**
   - Click "Start Send"
   - Monitor progress in real-time
   - You can Pause or Stop at any time

4. **View Results:**
   - See success/failure counts
   - Check message logs
   - Export report if needed

## Safety Features

### Why These Limits?

- **30-second default delay**: WhatsApp may flag rapid messages as spam
- **±5 second jitter**: Makes sending pattern less obvious
- **50-message session limit**: Protects account from temporary blocks
- **Consent checkbox**: Legal requirement in many countries
- **QR code login**: Never stores passwords

## Common Use Cases

### Fee Reminder (Schools/Coaching)

```
Dear {name}, your fee of {amount} is due on {due_date}. 
Please complete your payment to continue your enrollment.
```

### Appointment Reminder (Clinics)

```
Dear {name}, this is a reminder about your appointment 
on {date} at {time}. Please reach 5 minutes early.
```

### Promotional Offer (Businesses)

```
Special offer for {name}! Get 20% off this week. 
Don't miss out. Call {phone} to order now.
```

## Troubleshooting

### Messages Not Sending

1. Check internet connection
2. Verify WhatsApp Web is accessible
3. Ensure phone numbers are in correct format
4. Check if account is temporarily blocked

### Phone Number Validation Error

**Format needed:** +92XXXXXXXXXX (10 digits after country code)

**Auto-correction handles:**
- Adding +92 if you provide 03xxxxxxxxxx
- Removing spaces and dashes
- Normalizing common formats

### Character Limit Warning

Warning appears after 2000 characters because WhatsApp may split long messages across multiple SMS.

## Advanced Features

### Scheduling Messages

1. Go to Schedule tab
2. Choose date and time
3. Optional: Set recurring (daily/weekly/monthly)
4. Confirm

### Exporting Reports

1. Send a campaign
2. Click "Export" in right panel
3. Choose PDF or Excel format
4. Save to desired location

### Template Library

1. Save frequently used templates
2. Add category tags
3. Quickly load for future campaigns

## Legal Notes

✓ You must have explicit consent from recipients  
✓ Do not use for spam or harassment  
✓ Comply with local telemarketing laws  
✓ WhatsApp may block accounts that violate their terms  

## Contact & Support

- **Email:** farazgoal@gmail.com
- **Website:** [portfolio link]
- **GitHub:** github.com/farazgoal-boop

---

Built with ❤️ for Pakistani businesses
