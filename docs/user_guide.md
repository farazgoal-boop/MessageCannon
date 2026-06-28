# MessageCannon Pro — User Guide

Version 1.0.0 | Support: farazgoal@gmail.com

---

## Table of Contents

1. [Installation](#installation)
2. [First Launch & Activation](#first-launch--activation)
3. [Settings — SMTP & Safety](#settings--smtp--safety)
4. [Contacts Manager](#contacts-manager)
5. [WhatsApp Campaigns (Compose)](#whatsapp-campaigns-compose)
6. [Email Campaigns (Compose)](#email-campaigns-compose)
7. [Card Creator](#card-creator)
8. [Campaign History](#campaign-history)
9. [Reports & Analytics](#reports--analytics)
10. [Troubleshooting](#troubleshooting)

---

## Installation

### Windows (Recommended)

1. Run **MessageCannonPro-Setup.exe**
2. Choose install folder (default: `C:\Users\YourName\AppData\Local\Programs\MessageCannon Pro`)
3. No administrator rights required
4. Launch from desktop shortcut or Start Menu

### macOS

1. Open **MessageCannonPro-Mac-1.0.0.dmg**
2. Drag **MessageCannon Pro.app** → Applications folder
3. First launch: right-click the app → **Open** → confirm the security prompt
4. Subsequent launches: double-click normally

### Linux (.deb — Ubuntu/Debian)

```bash
sudo dpkg -i messagecannon-pro_1.0.0_amd64.deb
```

Then launch from your applications menu or run:
```bash
messagecannon-pro
```

---

## First Launch & Activation

On first launch you will see a splash screen, then the main app opens.

**Trial Mode:** You get 3 days to try all features without a license key.

**Activating:**
1. Go to **Settings** (left sidebar, bottom)
2. Scroll to **License & Activation**
3. Enter your license key in the text field
4. Click **Activate**

If the key is accepted, the sidebar badge changes from "Trial" to "Pro".

---

## Settings — SMTP & Safety

### Email SMTP Setup

Go to **Settings → Email — SMTP**.

| Field | What to enter |
|---|---|
| **Provider** | Choose Gmail, Outlook, or Custom |
| **Host** | SMTP server address (e.g. `smtp.gmail.com`) |
| **Port** | `587` for TLS (recommended), `465` for SSL |
| **Username** | Your full email address (e.g. `you@gmail.com`) |
| **Password** | Your email password or App Password |
| **Sender name** | Name shown in recipient's inbox |
| **Sender email** | The From address (usually same as Username) |
| **Delay (sec)** | Seconds between each email sent |

**Important:** For Gmail, your regular password will not work. You need an App Password:
1. Go to [myaccount.google.com](https://myaccount.google.com) → Security
2. Turn on **2-Step Verification**
3. Go to **App Passwords** → choose Mail → Generate
4. Use that 16-character password in the Password field

Click **Test connection** to verify before running a campaign.

### Campaign Safety Settings

| Setting | What it does |
|---|---|
| **Delay between messages** | Minimum pause between WhatsApp messages (10–120 sec) |
| **Daily limit** | Maximum messages sent per day across all campaigns |
| **Random jitter** | Adds ±5 sec randomness to the delay (less detectable) |
| **Consent required** | When ON, you must check a box before sending (legal protection) |

---

## Contacts Manager

### Importing Contacts

1. Click **Contacts** in the left sidebar
2. Click **Import Contacts**
3. Select an Excel (.xlsx), CSV, or HTML file

**Required column:** `phone` (at least one of these column names: `phone`, `Phone`, `mobile`, `number`)

**Optional columns:** `name`, `email`, `amount`, `date`, `custom1`, `custom2`, and any others (they become template variables)

**Phone formats accepted:**
- `+92XXXXXXXXXX` (international)
- `03XXXXXXXXXX` (Pakistan local — auto-converted)
- Numbers with spaces or dashes (auto-cleaned)

### Searching & Filtering

Use the search box to filter by name or phone number in real time.

### Exporting

Click **Export CSV** to save all contacts to a spreadsheet.

---

## WhatsApp Campaigns (Compose)

### Setup

1. Click **Compose** in the left sidebar
2. Select **WhatsApp** from the channel toggle at the top

### Writing Your Message

Use **{variables}** for personalization:

| Variable | Replaced with |
|---|---|
| `{name}` | Contact's name |
| `{phone}` | Contact's phone number |
| `{amount}` | Custom field: amount |
| `{date}` | Custom field: date |
| `{due_date}` | Custom field: due date |
| `{flat_no}` | Custom field: flat/unit number |
| `{custom1}` | First custom column from your import |
| `{custom2}` | Second custom column |

**Example message:**
```
Dear {name}, your fee of Rs {amount} is due on {due_date}.
Please pay at the office before closing time.
```

### Sending

1. Select contacts (checkboxes in the contacts panel)
2. Write your message in the editor
3. Check the preview (right side) to see messages for first 3 contacts
4. Click **Start** to begin
5. A QR code will appear — scan it with your phone in WhatsApp → Linked Devices
6. Sending begins automatically

### During Send

- **Pause/Resume** — temporarily pause without stopping the campaign
- **Stop** — ends the campaign immediately
- Progress bar and status line show real-time count

---

## Email Campaigns (Compose)

### Setup

1. Click **Compose** → select **Email** channel
2. Verify SMTP is configured (green chip shows "Connected")

### Writing the Email

- **Subject** — supports `{name}` and other variables
- **Body** — HTML editor. Write HTML directly or paste from a template
- Variables work the same as WhatsApp (`{name}`, `{amount}`, etc.)

**Quick HTML template:**
```html
<p>Dear <strong>{name}</strong>,</p>
<p>Your invoice of <strong>Rs {amount}</strong> is attached.</p>
<p>Please pay by <strong>{due_date}</strong>.</p>
<p>Thank you,<br>My Business</p>
```

### Sending

1. Select contacts (they need an `email` column in your import)
2. Click **Start**
3. Emails are sent one by one with the configured delay

---

## Card Creator

The Card Creator lets you build professional HTML marketing cards visually, then send them by email or share the link.

### Getting Started

1. Click **Cards** in the left sidebar

### App Identity

At the top, set:
- **App / Business Name** — shown in the card header
- **App Icon URL** — URL to your logo image
- **Tagline** — short slogan under the name
- **Card Template** — choose a pre-made color scheme (CopilotPremium, Midnight, etc.)

### Adding Sections

Click any section type button to add it to the card:

| Section | Purpose |
|---|---|
| **Banner Image** | Full-width hero image (enter image URL) |
| **YouTube Video** | Embed a YouTube video by URL |
| **Text Block** | Paragraph of text with size options (small/medium/large/heading) |
| **Features List** | Bullet list of product features |
| **Pricing** | Price block with optional original price (strikethrough) |
| **Links / Buttons** | Clickable CTA buttons (Buy, WhatsApp, LinkedIn, etc.) |
| **Contact Info** | Name, phone, email, social links |

### Reordering Sections

Each section has **↑ ↓** buttons to move it up or down. Click **✕** to remove a section.

Toggle **Show** checkbox to hide a section without deleting it.

### Live Preview

The right panel shows a real-time preview of the card as you edit. Click **↻ Refresh** to force a reload. Click **⛶ Full Screen** to open in your browser.

### Saving & Sharing

- **Save HTML** — saves the card as a `.html` file you can email or host
- **Open Browser** — opens the current card in your default browser
- **Bulk Send** — sends the card as an HTML email to your imported contacts

### Send Summary

Below the preview, the Send Summary panel shows:
- **Total contacts** loaded for bulk send
- **Sent** — successfully delivered
- **Read** / **Unread** — based on email tracking (when available)
- Activity log shows real-time send progress

---

## Campaign History

Click **History** (or **Campaigns** in the sidebar) to see all past email campaigns.

Each row shows:
- Campaign name and date
- Sent count and failed count
- Status badge

Click **Duplicate** to load a campaign's template back into the Compose tab, ready to re-send.

Click **Export CSV** to download the full history as a spreadsheet.

---

## Reports & Analytics

Click **Reports** in the left sidebar.

### Stats Cards

- **Sent Today** — messages sent in the last 24 hours
- **Delivery Rate** — percentage of successful sends
- **Active Session** — WhatsApp session status

### Charts

The pie chart shows **Read vs Unread** ratio for email campaigns.

### Export

1. Choose a **Period** (today / this week / this month / all time)
2. Choose **Format** (CSV or PDF)
3. Click **Export Report**

---

## Troubleshooting

### App doesn't open

- Reinstall from the latest `MessageCannonPro-Setup.exe`
- Check for anti-virus blocking the exe (add an exception)

### WhatsApp — QR code doesn't appear

- Make sure Google Chrome is installed
- Chrome version must match ChromeDriver. The app auto-downloads the right ChromeDriver via `webdriver_manager`.
- If Chrome updated recently, restart the app to trigger a driver update

### WhatsApp — "Session not created" error on startup

This is a ChromeDriver/Chrome version mismatch. Fix:
1. Check your Chrome version: `chrome://settings/help`
2. Restart the app — `webdriver_manager` will re-download the matching driver

### Email — Error 11003 (connection failed)

Your **Host** field has the wrong value. Common mistake: putting your email address in Host.

Correct settings for Gmail:
- Host: `smtp.gmail.com`
- Port: `587`
- Username: `yourname@gmail.com`
- Password: 16-character App Password (not your Gmail password)

### Email — Authentication failed

- You are using your normal Gmail password. Switch to an App Password (see Settings section above).
- Make sure 2-Step Verification is ON in your Google account.

### Contacts not importing

- Make sure the file has a column named `phone`, `Phone`, `mobile`, or `number`
- Check that phone numbers are numeric (no extra text in the column)
- Try saving the file as CSV (comma separated) if Excel import fails

### Messages show wrong variable (shows `{name}` literally)

The contact's row is missing the `name` column or the column is empty. Check your imported file has a `name` column with values filled in.

---

## Contact & Support

**Muhammad Faraz**
- Email: farazgoal@gmail.com
- Portfolio: [muhammad-faraz-dev.netlify.app](https://muhammad-faraz-dev.netlify.app)

For bugs or feature requests, email with subject line: **MessageCannon Pro — Support**

---

*MessageCannon Pro v1.0.0 — Built for Pakistani businesses*
