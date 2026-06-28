# MessageCannon Pro — Complete User Guide

**Version 1.0.0**
Support: farazgoal@gmail.com | Portfolio: muhammad-faraz-dev.netlify.app

---

## Table of Contents

1. [Installation](#1-installation)
2. [First Launch & License Activation](#2-first-launch--license-activation)
3. [The Main Interface](#3-the-main-interface)
4. [Settings — SMTP, Safety & Theme](#4-settings--smtp-safety--theme)
5. [Contacts Manager](#5-contacts-manager)
6. [WhatsApp Campaigns](#6-whatsapp-campaigns)
7. [Email Campaigns](#7-email-campaigns)
8. [Card Creator](#8-card-creator)
9. [Campaign History](#9-campaign-history)
10. [Reports & Analytics](#10-reports--analytics)
11. [Data Backup & Recovery](#11-data-backup--recovery)
12. [Troubleshooting](#12-troubleshooting)
13. [Frequently Asked Questions](#13-frequently-asked-questions)
14. [WhatsApp Safety Tips](#14-whatsapp-safety-tips)

---

## 1. Installation

### Windows (Setup installer — recommended for most users)

1. Download **`MessageCannonPro-Setup.exe`**
2. Double-click to run the installer
3. If Windows shows a blue "Windows protected your PC" warning, click **More info → Run anyway** (this appears because the app is not code-signed by Microsoft)
4. Choose an install folder or accept the default (`C:\Users\YourName\AppData\Local\Programs\MessageCannon Pro`)
5. No administrator password required — installs to your own user account
6. When the installer finishes, it offers to launch the app immediately

**To uninstall:** Start Menu → search "MessageCannon Pro" → right-click → Uninstall.
When uninstalling, the app asks if you want to keep your contacts and campaign data. Click **Yes** to keep them.

---

### macOS

1. Download **`MessageCannonPro-mac.dmg`**
2. Double-click the DMG file to mount it — a window opens showing the app
3. Drag **MessageCannon Pro** into the **Applications** folder shown in the same window
4. Eject the DMG (drag it to Trash or press Cmd+E)
5. **First launch only:** go to Applications, **right-click** the app → click **Open** → click **Open** again in the dialog that appears
   - This is a one-time step. macOS blocks apps from unverified developers on double-click; right-click bypasses it permanently for that app
6. After the first launch, you can open it normally by double-clicking

**To uninstall:** Drag MessageCannon Pro from Applications to Trash.

---

### Linux — .deb package (Ubuntu, Debian, Linux Mint)

Open a terminal and run:

```bash
sudo dpkg -i MessageCannonPro-linux-1.0.0.deb
```

After install, launch from your applications menu (look under Office or Internet) or type in the terminal:

```bash
messagecannon-pro
```

**To uninstall:**

```bash
sudo dpkg -r messagecannon-pro
```

---

### Linux — AppImage (any distribution)

The AppImage is a self-contained file that runs on any modern Linux without installation:

```bash
chmod +x MessageCannonPro-linux-1.0.0.AppImage
./MessageCannonPro-linux-1.0.0.AppImage
```

No install required. To add it to your app launcher, right-click and look for "Add to Applications" in your file manager, or create a `.desktop` file manually.

---

### Run from source code (developers)

```bash
git clone https://github.com/farazgoal-boop/MessageCannon.git
cd MessageCannon
pip install -r requirements.txt
python src/main.py
```

Python 3.11 or newer required.

---

## 2. First Launch & License Activation

### Splash screen

On first launch you will see a brief splash screen while the app loads. This is normal.

### Trial mode

Without a license key, the app runs in **Trial Mode** for 3 days. All features are available during the trial. The sidebar shows a "Trial" badge.

### Activating your license

1. Click **Settings** in the left sidebar (gear icon at the bottom)
2. Scroll down to the **License & Activation** section
3. Type or paste your license key into the field
4. Click **Activate**
5. If accepted, the sidebar badge changes from "Trial" to "Pro"

If activation fails:
- Check that you are connected to the internet
- Make sure the key is entered exactly as provided (no extra spaces)
- Contact farazgoal@gmail.com if the key does not work

### License is per-machine

One license key activates one computer. If you move to a new computer, contact support for a transfer.

---

## 3. The Main Interface

The app has two main areas:

**Left sidebar** — navigation between all sections of the app. Click any item to switch.

| Sidebar item | What it opens |
|---|---|
| Dashboard (home icon) | Overview: sent today, delivery rate, session status |
| Compose | Write and send WhatsApp or email campaigns |
| Contacts | Import, view, and manage your contact list |
| Cards | Card Creator — build and send HTML marketing cards |
| History | Past campaigns with per-campaign delivery logs |
| Reports | Charts and exportable analytics |
| Settings | SMTP, safety limits, theme, license |

**Right area** — the content for whatever section is selected.

### Switching themes

Click the **sun / moon icon** at the top of the sidebar to switch between Dark and Light mode. The app remembers your choice.

---

## 4. Settings — SMTP, Safety & Theme

Go to **Settings** (gear icon, bottom of sidebar).

---

### Email SMTP Setup

This section connects MessageCannon to your email account so it can send emails on your behalf.

| Field | What to enter |
|---|---|
| **Host** | Your email provider's SMTP server address |
| **Port** | `587` for TLS (recommended), `465` for SSL |
| **Username** | Your full email address (e.g. `you@gmail.com`) |
| **Password** | Your email password or App Password (see below) |
| **Sender Name** | The name recipients see in their inbox (e.g. "My Business") |
| **Sender Email** | The address shown as From (usually the same as Username) |
| **Delay (sec)** | Seconds to wait between each outgoing email |

After filling in all fields, click **Test Connection**. A green confirmation message means it works. A red error means something is wrong — see the Troubleshooting section.

---

#### Gmail — App Password setup (required)

Gmail does not allow your normal password for third-party software. You must create a separate App Password:

**Step 1** — Enable 2-Step Verification

1. Open [myaccount.google.com](https://myaccount.google.com) in your browser
2. Click **Security** in the left menu
3. Under "How you sign in to Google", click **2-Step Verification**
4. Follow the prompts to turn it on (usually takes 2 minutes)

**Step 2** — Generate an App Password

1. Still on the Security page, click **App passwords** (you may need to scroll down)
   - If you do not see "App passwords", your account may be managed by a school or company. Contact your admin.
2. In the "Select app" dropdown, choose **Mail**
3. In "Select device", choose **Windows Computer** (or any option — it does not affect the password)
4. Click **Generate**
5. A 16-character password appears in a yellow box — copy it now (you cannot see it again)

**Step 3** — Enter it in MessageCannon

- Host: `smtp.gmail.com`
- Port: `587`
- Username: `yourname@gmail.com`
- Password: paste the 16-character code (with or without spaces — both work)

---

#### Outlook / Hotmail

- Host: `smtp.office365.com`
- Port: `587`
- Username: `yourname@outlook.com`
- Password: your normal Outlook password (or an App Password if you have 2FA enabled)

---

#### Yahoo Mail

1. Go to your Yahoo account security settings
2. Enable 2-Step Verification
3. Generate an App Password
4. Use:
   - Host: `smtp.mail.yahoo.com`
   - Port: `587`

---

### Campaign Safety Settings

These settings protect your accounts from being flagged as spam or getting banned.

| Setting | What it does | Recommended |
|---|---|---|
| **Delay between messages** | Minimum pause (seconds) between each WhatsApp message | 15–30 seconds |
| **Random jitter** | Adds random extra seconds to the delay so messages do not arrive at perfectly equal intervals | Leave ON |
| **Daily send limit** | Maximum total messages sent per day across all campaigns | 200–300 for safety |
| **Consent checkbox** | When ON, you must check a box before any campaign starts | Leave ON |

**Why delays matter:** WhatsApp monitors send patterns. Sending too fast (under 10 seconds between messages) raises red flags and can cause a temporary or permanent ban. The built-in minimum is 10 seconds — do not go lower.

---

### Reset Session

The **Reset Session** button in Settings clears the saved WhatsApp login. Use this if:
- Your WhatsApp session expired and the QR code does not appear
- You want to log in with a different phone number
- WhatsApp is showing an error on open

After resetting, the next campaign will ask you to scan a QR code again.

---

## 5. Contacts Manager

Click **Contacts** in the sidebar.

---

### Preparing your contact file

MessageCannon imports contacts from **Excel (.xlsx)**, **CSV (.csv)**, or **HTML** files.

**Rules:**
- The file must have column headers in the first row
- At least one of these columns must exist: `phone`, `Phone`, `mobile`, `Mobile`, `number`, `Number`
- An `email` column is needed for email campaigns

**Phone number formats accepted:**
- `+923001234567` (international format)
- `03001234567` (Pakistan local — automatically converted to +92)
- `3001234567` (without leading zero — also accepted)
- Numbers with spaces: `0300 123 4567` — spaces are removed automatically
- Numbers with dashes: `0300-123-4567` — dashes are removed automatically

**Minimum file (WhatsApp only):**

| phone |
|---|
| 03001234567 |
| 03219876543 |

**Complete file (all features):**

| name | phone | email | amount | due_date | flat_no |
|---|---|---|---|---|---|
| Ahmad Ali | 03001234567 | ahmad@example.com | 25,000 | 5 Jan | A-101 |
| Sara Khan | 03119876543 | sara@example.com | 18,000 | 7 Jan | B-204 |
| Usman Raza | +923331122334 | | 30,000 | 10 Jan | C-305 |

**Adding custom columns:** Any column you add becomes a `{variable}` in your messages. For example, a column called `school_name` can be used as `{school_name}` in your WhatsApp template.

---

### Importing contacts

1. Click **Import Contacts**
2. Select your Excel or CSV file
3. The app reads the file and shows how many contacts were imported and how many were skipped (with reasons)
4. Contacts are saved to the local database automatically

**Common import errors:**

| Error | What it means | Fix |
|---|---|---|
| "No valid contacts found" | File has no phone or email column | Add a column named `phone` or `email` |
| "Invalid phone number" | Phone number cannot be parsed | Check for non-numeric characters in the phone column |
| Row skipped | Row has no phone AND no email | Add at least one — or delete the row |
| Duplicate entry | Same phone already in database | No action needed — duplicates are skipped automatically |

---

### Searching contacts

Type in the **Search** box at the top of the contact list to filter in real time. The search looks in the name and phone number fields.

---

### Exporting contacts

Click **Export CSV** to download all your contacts as a spreadsheet. Useful for backup or editing.

---

### Deleting contacts

Click the checkbox next to a contact and press Delete, or right-click for options (depending on your version).

---

## 6. WhatsApp Campaigns

Click **Compose** in the sidebar, then make sure the **WhatsApp** channel is selected at the top.

---

### Before you start

- Google Chrome must be installed on your computer (any recent version)
- Your phone must have internet access to scan the QR code
- You need contacts loaded (see Contacts section)

---

### Writing your message

Type your message in the text editor. Use `{variables}` for personalization — each variable is replaced with the value from that contact's row in your file.

**Available variables:**

| Variable | Replaced with |
|---|---|
| `{name}` | Contact's name |
| `{phone}` | Their phone number |
| `{amount}` | Value from the `amount` column |
| `{due_date}` | Value from the `due_date` column |
| `{flat_no}` | Value from the `flat_no` column |
| `{email}` | Their email address |
| `{anything}` | Any column name from your import file |

**Example messages:**

Fee reminder for a school:
```
Dear {name},

This is a reminder that your fee of Rs {amount} is due on {due_date}.

Please visit the accounts office before the due date to avoid a late fee.

Thank you,
ABC Academy
```

Property update for real estate:
```
Hello {name},

A new property matching your requirements is available in {area}.
Size: {size} | Price: Rs {price}

Reply to this message or call us for a viewing appointment.
```

Appointment reminder for a clinic:
```
Dear {name},

You have an appointment on {date} at {time}.

Please arrive 10 minutes early. For rescheduling, reply to this message.

Dr. Faraz Clinic
```

---

### Selecting recipients

The contacts panel on the left side of the Compose screen shows your imported contacts. Check the boxes next to the ones you want to include in this campaign, or click **Select All**.

---

### Previewing messages

The **Preview** panel (right side) shows how your message will look for the first few contacts. This lets you verify variables are substituting correctly before you send.

If a variable appears literally (e.g. `{name}` shows as `{name}` and not "Ahmad"), it means that contact's file had no value in the `name` column.

---

### Starting the campaign

1. Make sure contacts are selected and your message is written
2. Check the **I confirm recipients have opted in** box (required)
3. Click **Start**
4. A Chrome browser window opens showing WhatsApp Web with a QR code

**Scanning the QR code:**
1. Open WhatsApp on your phone
2. Tap the three dots (Android) or Settings (iPhone)
3. Tap **Linked Devices**
4. Tap **Link a Device**
5. Point your camera at the QR code on the screen

The QR code scan takes about 5 seconds. After scanning, WhatsApp Web connects and sending begins automatically.

---

### During sending

The progress bar and status line show how many messages have been sent and how many remain.

| Button | What it does |
|---|---|
| **Pause** | Temporarily pauses sending. Click Resume to continue. |
| **Stop** | Stops the campaign permanently. Cannot be resumed after stopping. |

The app waits the delay you set between each message. This is normal and intentional.

---

### After sending

The campaign is logged in **History** automatically. You can see per-contact delivery status there.

**The Chrome window:** After sending finishes, the browser window stays open (WhatsApp Web session remains logged in for faster starts next time). You can close it manually, or leave it open.

---

### WhatsApp session persistence

The app saves your WhatsApp Web login between sessions. You only need to scan the QR code:
- The very first time you use the app
- After you click Reset Session in Settings
- If your WhatsApp session expires (usually after 14 days of no use on that device)
- If you manually log out from WhatsApp on your phone

---

## 7. Email Campaigns

Click **Compose** in the sidebar, then select the **Email** channel at the top.

---

### Before you start

- SMTP must be configured in Settings (the chip at the top shows "Connected" in green)
- Contacts must have an `email` column in their imported file

---

### Writing the email

**Subject line**
The subject supports variables: `{name}`, `{amount}`, etc.
Example: `Fee Reminder — {name} — {due_date}`

**Email body**
The body uses HTML. You do not need to know HTML — simple tags work fine:
- `<p>Text here</p>` — a paragraph
- `<b>bold</b>` or `<strong>bold</strong>` — bold text
- `<br>` — a line break
- `<a href="https://example.com">Click here</a>` — a link

Variables (`{name}`, `{amount}`, etc.) work in the body exactly like WhatsApp messages.

**Simple plain-text style:**
```html
<p>Dear {name},</p>

<p>Your fee of <strong>Rs {amount}</strong> is due on <strong>{due_date}</strong>.</p>

<p>Please pay at the office or via bank transfer before the due date.</p>

<p>Thank you,<br>
ABC Academy<br>
Tel: 0300-0000000</p>
```

**Styled email:**
```html
<div style="font-family: Arial, sans-serif; max-width: 600px; margin: auto;">
  <div style="background-color: #1a3a5c; color: white; padding: 20px; text-align: center;">
    <h2>ABC Academy</h2>
  </div>
  <div style="padding: 30px;">
    <p>Dear <strong>{name}</strong>,</p>
    <p>Your fee payment of <strong>Rs {amount}</strong> is due on <strong>{due_date}</strong>.</p>
    <p>Please contact the accounts office if you have any questions.</p>
  </div>
  <div style="background-color: #f0f0f0; padding: 15px; text-align: center; font-size: 12px; color: #666;">
    This email was sent to {email}
  </div>
</div>
```

---

### Sending

1. Select the contacts you want to email (they must have an email address — contacts without one are automatically skipped)
2. Check the consent checkbox
3. Click **Start**
4. Emails are sent one by one with the delay you configured in Settings

There is no QR code for email — it sends immediately using your SMTP credentials.

---

## 8. Card Creator

Click **Cards** in the sidebar.

The Card Creator lets you build a professional HTML marketing card visually and then:
- Send it as an HTML email to all your contacts
- Open it in your browser to share as a file or screenshot

---

### Setting up the card identity

At the top of the editor, fill in:

| Field | Purpose |
|---|---|
| **App / Business Name** | Your business name, shown as the card header |
| **App Icon URL** | URL to your logo (hosted image — e.g. from your website or Google Drive) |
| **Tagline** | Short description under your name (e.g. "Pakistan's #1 Property Consultants") |
| **Card Template** | Color scheme — choose from the pre-made themes (Midnight, Ocean, etc.) |

---

### Adding sections

Each button in the "Add Section" area adds a new block to the card. Sections stack vertically in the order you add them. You can reorder them after.

#### Banner Image
Displays a full-width image at the top of the card.
- Enter an image URL (must be a direct link to an image file, e.g. ending in `.jpg` or `.png`)
- You can host images on Imgur, your own website, or Google Photos (set to public)

#### YouTube Video
Embeds a YouTube video the recipient can play in their email (if supported) or browser.
- Paste the YouTube URL (either the full URL or just the video ID)
- The preview updates automatically when you type the URL

#### Text Block
A paragraph of text. Use for descriptions, important notes, or body content.
- **Size options:** Small (fine print), Medium (normal body), Large (emphasis), Heading (title style)
- Keep headings short — use them to separate sections visually

#### Features List
A bullet-point list. Best for:
- Product features ("24/7 support", "Free delivery", etc.)
- Course curriculum items
- Property features (4 beds, 3 baths, garden, etc.)

Enter each feature on its own line.

#### Pricing
A prominent price display.

| Field | Purpose |
|---|---|
| **Price** | The current price (e.g. `Rs 25,000/month`) |
| **Original Price** | Optional — shown as strikethrough above the price (for discounts) |
| **Label** | Optional tag (e.g. "Limited Offer", "Most Popular") |

#### Links / Buttons
Clickable call-to-action buttons. One button per entry.

| Button type | Use |
|---|---|
| WhatsApp | Opens a WhatsApp chat with your number pre-filled |
| Website | Opens a URL in the browser |
| LinkedIn | Links to your LinkedIn profile |
| Email | Opens the user's email client |
| Phone | Taps to call |
| Custom | Any label and URL you specify |

#### Contact Info
Your contact details displayed at the bottom of the card.
- Name, title, phone, email, social handles
- These do not create clickable links by default — use the Links section for that

---

### Reordering and removing sections

Each section has three controls on the right side:

| Button | Action |
|---|---|
| **↑** | Move this section up (swap with the one above) |
| **↓** | Move this section down |
| **✕** | Delete this section permanently |

The **Show** checkbox next to a section hides it from the card without deleting it. Useful for temporarily removing a section while building.

---

### Live preview

The right side of the screen shows a real-time preview of the card in an HTML viewer.

- The preview updates automatically as you type (with a short delay)
- Click **↻ Refresh** to force an immediate update
- Click **⛶ Full Screen** (or Open Browser) to view the card in your default browser at full size

---

### Saving the card

- **Save HTML** — downloads the card as a `.html` file. You can:
  - Email it as an attachment
  - Open it in any browser (no internet connection required to view a saved card)
  - Host it on a website and share the link

---

### Sending the card by email

1. Make sure you have contacts imported with email addresses
2. Click **Bulk Send**
3. A dialog appears — choose whether to send to all contacts or a selection
4. Click **Send**

The card is sent as an inline HTML email. Recipients see the full card directly in their email app.

---

### Send summary panel

Below the card preview, the **Send Summary** section shows:
- **Total** — how many contacts are loaded for bulk send
- **Sent** — successfully delivered
- **Read / Unread** — based on email open tracking (when available)
- **Activity log** — live updates during sending showing each contact as it is processed

---

## 9. Campaign History

Click **History** (or **Campaigns**) in the sidebar.

This screen shows every email campaign that was run, with:
- Campaign name and creation date
- How many emails were sent
- How many failed
- Status badge (Completed, Partial, Failed)

### Viewing details

Click a campaign row to expand it and see per-contact delivery status.

### Duplicating a campaign

Click **Duplicate** next to any campaign to load that campaign's subject, body, and template back into the Compose tab — ready to re-send to a new contact list without retyping.

### Exporting history

Click **Export CSV** to download the full campaign history as a spreadsheet. Useful for reporting to clients or management.

---

## 10. Reports & Analytics

Click **Reports** in the sidebar.

---

### Stats cards at the top

| Card | What it shows |
|---|---|
| **Sent Today** | Total messages sent in the last 24 hours (WhatsApp + Email combined) |
| **Delivery Rate** | Percentage of sends that succeeded |
| **Active Session** | Whether a WhatsApp session is currently connected |

---

### Charts

**Read vs Unread pie chart** — shows how many email recipients opened the email versus those who received it but did not open. This requires email tracking to be enabled (standard HTML email pixel tracking).

**Timeline chart** (if shown) — messages sent per day over the selected period.

---

### Exporting a report

1. Select a **Period**: Today, This Week, This Month, or All Time
2. Select **Format**: CSV (spreadsheet) or PDF (formatted document)
3. Click **Export Report**
4. Choose where to save the file

---

## 11. Data Backup & Recovery

All your contacts and campaign history are stored in a local database file on your computer.

**Database location:**
- Windows: `C:\Users\YourName\AppData\Local\MessageCannon Pro\data\`
- macOS: `~/Library/Application Support/MessageCannon Pro/data/`
- Linux: `~/.local/share/messagecannon-pro/data/`

**Backing up:** Copy the entire `data` folder to a USB drive or cloud storage (Dropbox, Google Drive, OneDrive).

**Restoring:** Copy the backed-up `data` folder back to the same location. Close the app before replacing files.

**Tip:** Export your contacts as CSV regularly from the Contacts screen. CSV files are a simple backup that can also be re-imported if needed.

---

## 12. Troubleshooting

---

### App will not open

**Windows:**
- If Windows Defender SmartScreen blocks it: click "More info" → "Run anyway"
- If antivirus quarantined it: add MessageCannon Pro to your antivirus exceptions list
- Try right-clicking the `.exe` → Run as administrator (one time only — future runs do not need this)

**macOS:**
- Make sure you right-clicked and chose Open the first time (see Installation section)
- If it still does not open: System Preferences → Security & Privacy → General → click "Open Anyway"

---

### WhatsApp — QR code does not appear

1. Make sure Google Chrome is installed (download from google.com/chrome)
2. The app downloads a ChromeDriver that matches your Chrome version automatically. If Chrome updated recently, restart the app to trigger a fresh driver download.
3. If the Chrome window opens but shows an error: go to Settings → Reset Session, then try again.
4. Check that you have an internet connection.

---

### WhatsApp — "Session not created" error

This usually means the ChromeDriver version does not match your Chrome version.

1. Check your Chrome version: open Chrome → address bar → type `chrome://settings/help`
2. Restart MessageCannon Pro — the driver auto-updater will download the matching version
3. If it still fails: manually delete the `webdriver` folder inside the app data folder and restart

---

### WhatsApp — messages sent but recipient did not receive

- The recipient may have blocked you
- The phone number may not be registered on WhatsApp
- Your WhatsApp account may have been temporarily restricted (too many messages too fast)

Check the History screen — failed deliveries are logged there with an error reason.

---

### Email — Error 11003

This error means the app could not connect to the mail server. Most common cause: the **Host** field contains your email address instead of the server address.

Correct:
- Host: `smtp.gmail.com` (not `yourname@gmail.com`)
- Port: `587`

---

### Email — "Authentication failed" or "Invalid credentials"

You are using your normal Gmail password. Gmail does not allow this for third-party apps.

Solution: Generate an App Password (see Section 4 — Gmail App Password setup).

Make sure:
- 2-Step Verification is enabled on your Google account
- You are copying the App Password correctly (it is 16 characters, sometimes shown with spaces — both formats work)

---

### Email — "Connection refused" or "timeout"

- Port 587 is blocked by your network/ISP. Try port 465.
- If on a corporate network, the firewall may block outgoing SMTP. Ask your IT admin to allow outgoing connections on port 587.
- Temporarily disable your antivirus or firewall and try again to isolate the issue.

---

### Contacts not importing

| Symptom | Fix |
|---|---|
| "No valid contacts found" | Add a `phone` or `email` column with that exact header name |
| Numbers import as 0 or blank | Excel is treating the column as a number — format the column as Text before saving |
| All rows skipped | File may have data starting on row 2+ without headers — add a header row |
| Excel file not working | Save as CSV (File → Save As → CSV) and import the CSV instead |

---

### Messages show `{name}` literally instead of the contact's name

The `name` column is missing or empty for that contact. Open your import file, add the name values, and re-import.

---

### App freezes when closing (X button)

This was fixed in the current version. If you are on an older version:
- Wait up to 10 seconds — it is shutting down WhatsApp Web in the background
- If it is still frozen after 30 seconds, use Task Manager (Windows) or Force Quit (macOS) to close it

---

### The card preview is blank or not updating

1. Click **↻ Refresh** in the preview panel
2. If the preview area shows an error: click **Open Browser** to view the card directly in your browser instead

---

## 13. Frequently Asked Questions

**Q: Does MessageCannon Pro use the official WhatsApp API?**
No. It uses WhatsApp Web automation (Selenium + Chrome). This means it works with your personal or business WhatsApp number without requiring an API account. It also means WhatsApp's Terms of Service prohibit automation — use responsibly with appropriate delays and only for opted-in contacts.

**Q: Can I send to contacts who have not given me their number?**
No. Only send to people who have willingly shared their contact information with you and expect to hear from you. Sending unsolicited messages is against WhatsApp rules and may be illegal in your jurisdiction.

**Q: How many messages can I send per day?**
This depends on your WhatsApp account's age and history. A new number should start very slow (50–100/day). An established number can handle 200–300/day safely. Going higher without warming up the account risks a ban.

**Q: Will WhatsApp ban my number?**
If you use the app responsibly (proper delays, opted-in contacts, reasonable daily limits), the risk is low. See Section 14 for specific safety tips.

**Q: Can I use the same license on multiple computers?**
No. One license = one computer. Contact farazgoal@gmail.com for multi-PC pricing.

**Q: Does the app need an internet connection to run?**
Yes, for: WhatsApp sending, email sending, and license verification. The contacts database and card editor work offline.

**Q: Can I import contacts from my phone's contact list?**
Export your phone contacts as a VCF or CSV file from your phone, then import that file into MessageCannon.

**Q: Can I schedule messages to send at a specific time?**
The current version does not have a built-in scheduler. Start the campaign manually when you are ready to send.

**Q: My email goes to spam. What can I do?**
- Make sure your email content does not look spammy (avoid excessive CAPS, many exclamation marks, "click here" as the only link text)
- Send from a domain email address (yourname@yourbusiness.com) instead of Gmail — domain-based senders have better deliverability
- Start with a small test batch before sending to your full list
- Ask recipients to mark your emails as "Not Spam" after the first send

**Q: Can I attach files to emails?**
The current version sends HTML email without attachments. For PDFs or invoices, include a download link in the email body.

**Q: Where are my contacts stored?**
On your own computer only. MessageCannon Pro does not upload your contacts to any server.

---

## 14. WhatsApp Safety Tips

Using WhatsApp for bulk messaging carries inherent risk of account restrictions. Follow these guidelines to minimize that risk:

### Use appropriate delays

| Account age | Recommended delay | Daily limit |
|---|---|---|
| New number (< 1 month) | 30–60 seconds | 50–80 |
| 1–6 months old | 20–30 seconds | 100–150 |
| Established (6+ months) | 15–20 seconds | 200–300 |

Never set the delay below 10 seconds. The built-in minimum is 10 seconds for this reason.

### Send to opted-in contacts only

Only message people who have:
- Given you their number directly (in person, on a form, etc.)
- Expressed interest in receiving updates from you
- Not asked to be removed from your list

### Keep messages personal and relevant

Avoid:
- Sending identical messages to everyone (use `{name}` at minimum)
- Sending promotional content people did not ask for
- Including multiple links or media in one message
- All-caps text or excessive exclamation marks

### Watch for warning signs

If WhatsApp shows any of these, stop sending immediately:
- "Too many messages" notification
- Your messages are not being delivered (single grey tick only)
- Recipients report getting a "spam" warning when your message arrives

### Use jitter

Keep the **Random Jitter** setting turned ON. It makes delays slightly random, mimicking human behavior.

### Do not send at odd hours

Sending at 3 AM in your recipients' timezone is a red flag. Send during normal business hours (9 AM to 8 PM).

### Warm up a new number

If using a new WhatsApp number for campaigns, do not start with bulk sending. Use it normally for 2–4 weeks (regular conversations) before starting any campaigns. Gradually increase volume over 2 weeks.

---

## Contact & Support

**Muhammad Faraz** — Full Stack Developer
Email: farazgoal@gmail.com
Portfolio: muhammad-faraz-dev.netlify.app

For support, email with the subject line: **MessageCannon Pro — Support**

Include:
- Your operating system (Windows 10/11, macOS version, Linux distro)
- What you were doing when the problem occurred
- Any error message shown on screen (screenshot is helpful)

Response time: 1–2 business days.

---

*MessageCannon Pro v1.0.0 — Built for Pakistani businesses*
