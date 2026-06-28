# MessageCannon Pro

**Professional bulk messaging for WhatsApp and Email — desktop app, no cloud, no subscriptions.**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen.svg)]()
[![License: Commercial](https://img.shields.io/badge/License-Commercial-orange.svg)]()
[![CustomTkinter](https://img.shields.io/badge/UI-CustomTkinter%205.2-informational.svg)](https://github.com/TomSchimansky/CustomTkinter)

---

## What it does

MessageCannon Pro lets you send personalized WhatsApp messages and branded HTML emails to hundreds of contacts at once — all from your own machine. No cloud account needed. Your contacts never leave your computer.

**Who uses it:**

| Business type | Use case |
|---|---|
| Schools & coaching centers | Monthly fee reminders, exam notifications |
| Clinics & hospitals | Appointment reminders, prescription follow-ups |
| Real estate agencies | New property alerts, rental updates |
| E-commerce businesses | Order confirmations, promotions, re-engagement |
| Marketing agencies | Client campaign delivery |
| Event organizers | Invitations, tickets, event updates |

---

## Features

### Messaging

| Module | Description |
|---|---|
| **WhatsApp Campaigns** | Send personalized messages via WhatsApp Web using your own phone number. Adjustable delay, random jitter, daily send cap. |
| **Email Campaigns** | SMTP-based HTML email with variable substitution. Works with Gmail, Outlook, Yahoo, and any custom SMTP server. |
| **Message Templates** | `{name}`, `{amount}`, `{due_date}`, `{flat_no}` and any custom column from your contact file — auto-substituted per recipient. |

### Card Creator

Visual HTML card builder with live preview. Add sections in any order:

- **Banner Image** — full-width hero from any image URL
- **YouTube Video** — embedded player by URL
- **Text Block** — paragraph with size control (small / medium / large / heading)
- **Features List** — bullet list of selling points
- **Pricing** — price with optional crossed-out original price
- **Links / Buttons** — WhatsApp chat, LinkedIn, website, custom CTAs
- **Contact Info** — name, phone, email, social handles

Send the finished card as an HTML email to all contacts, or open it in the browser.

### Contact Management

- Import from **Excel (.xlsx)**, **CSV**, or **HTML** tables
- Auto-normalize Pakistan local numbers (`03xx` → `+92`)
- Detect and skip duplicate or invalid numbers at import time
- Search and filter contacts in real time
- Export all contacts as CSV

### Analytics & Reporting

- Live delivery rate during active campaigns
- Sent today / this week counters
- Read vs Unread pie chart for email campaigns
- Export reports as **PDF** or **CSV** for any time period

---

## Install

### Windows — Setup installer (recommended)

1. Download **`MessageCannonPro-Setup.exe`**
2. Run it — no administrator rights required (installs to your user folder)
3. Launch from the desktop shortcut
4. Enter your license key on first run

### macOS — DMG

1. Download **`MessageCannonPro-mac.dmg`**
2. Open the DMG, drag **MessageCannon Pro** into Applications
3. **First launch only:** right-click the app → **Open** → click Open in the security dialog
   *(Gatekeeper blocks unsigned apps on double-click — right-click bypasses this once)*
4. Subsequent launches: double-click normally

### Linux — .deb package (Ubuntu / Debian)

```bash
sudo dpkg -i MessageCannonPro-linux-1.0.0.deb
messagecannon-pro
```

Or find it in your applications menu after install.

### Linux — AppImage (any distro)

```bash
chmod +x MessageCannonPro-linux-1.0.0.AppImage
./MessageCannonPro-linux-1.0.0.AppImage
```

---

## Quick setup — Gmail

Gmail blocks your regular password for third-party apps. You need an **App Password**:

1. Go to **myaccount.google.com → Security**
2. Enable **2-Step Verification** (required)
3. Go to **App Passwords** → select **Mail** → click **Generate**
4. Copy the 16-character password
5. In MessageCannon: **Settings → SMTP**
   - Host: `smtp.gmail.com`
   - Port: `587`
   - Username: `youraddress@gmail.com`
   - Password: the 16-character App Password *(not your normal Gmail password)*
6. Click **Test Connection** to confirm

Other providers:

| Provider | Host | Port |
|---|---|---|
| Outlook / Hotmail | `smtp.office365.com` | `587` |
| Yahoo Mail | `smtp.mail.yahoo.com` | `587` |
| Zoho Mail | `smtp.zoho.com` | `587` |

---

## Quick setup — WhatsApp

Requires Google Chrome installed on your computer. No API, no business account needed.

1. Go to **Compose → WhatsApp**
2. Write your message using `{name}`, `{amount}` etc.
3. Select contacts from the list
4. Click **Start**
5. Scan the QR code with WhatsApp on your phone → **Linked Devices → Link a Device**

Sending starts automatically after you scan.

---

## System requirements

| | Windows | macOS | Linux |
|---|---|---|---|
| OS | Windows 10 / 11 (64-bit) | macOS 12 Monterey+ | Ubuntu 20.04+ / Debian 11+ |
| Chrome | Required for WhatsApp | Required for WhatsApp | Required for WhatsApp |
| Python | Not needed (installer) | Not needed (DMG) | Not needed (.deb/.AppImage) |
| RAM | 512 MB minimum | 512 MB minimum | 512 MB minimum |
| Disk | ~200 MB | ~200 MB | ~200 MB |

---

## Contact import format

Minimum — just a phone column:

| phone |
|---|
| 03001234567 |
| +923001234567 |

Full example with all variables:

| name | phone | email | amount | due_date | flat_no |
|---|---|---|---|---|---|
| Ahmad Ali | 03001234567 | ahmad@example.com | 25,000 | 5 Jan | A-101 |
| Sara Khan | 03119876543 | sara@example.com | 18,000 | 7 Jan | B-204 |

Any extra column you add becomes available as `{column_name}` in your message.

---

## Message template variables

| Variable | Comes from column | Example |
|---|---|---|
| `{name}` | `name` | Ahmad Ali |
| `{phone}` | `phone` | +923001234567 |
| `{amount}` | `amount` | 25,000 |
| `{due_date}` | `due_date` | 5 Jan |
| `{flat_no}` | `flat_no` | A-101 |
| `{email}` | `email` | ahmad@example.com |
| `{anything}` | any column name | that row's value |

---

## Build from source

```bash
git clone https://github.com/farazgoal-boop/MessageCannon.git
cd MessageCannon
pip install -r requirements.txt
python src/main.py          # run directly
```

### Windows EXE + installer

```batch
build\build_windows.bat
```

Requires [Inno Setup 6](https://jrsoftware.org/isinfo.php) (free) for the `.exe` installer.
Produces: `dist\MessageCannon Pro.exe` and `dist\MessageCannonPro-Setup.exe`.

### macOS DMG

```bash
bash build/build_mac.sh
```

Produces `MessageCannonPro-mac.dmg`.

### Linux .deb + AppImage

```bash
bash build/build_linux.sh
```

Produces `.deb` and `.AppImage` in the project root.

### Automated CI (GitHub Actions)

Push a version tag to trigger builds for Mac and Linux automatically:

```bash
git tag v1.0.0
git push origin v1.0.0
```

Workflow: `.github/workflows/build-mac-linux.yml`

---

## Safety & compliance

MessageCannon Pro is designed for opt-in, legitimate business communication:

- Built-in minimum 10-second delay between WhatsApp messages
- Random ±5 second jitter to avoid robotic send patterns
- Configurable daily send cap
- Consent checkbox — must be checked before a campaign starts
- All contact data stored locally on your machine only

You are responsible for compliance with WhatsApp Terms of Service and local anti-spam regulations.

---

## Documentation

- [User Guide](docs/user_guide.md) — complete step-by-step manual for every feature

---

## License & pricing

| Package | Price |
|---|---|
| Single PC License | Rs 8,000 PKR / $29 USD |
| 5-PC Team Pack | Rs 25,000 PKR / $99 USD |

One-time payment. Lifetime updates included.

---

## Contact & support

**Muhammad Faraz** — Full Stack Developer
- Email: [farazgoal@gmail.com](mailto:farazgoal@gmail.com)
- Portfolio: [muhammad-faraz-dev.netlify.app](https://muhammad-faraz-dev.netlify.app)
- Bug reports / feature requests: email with subject **MessageCannon Pro — Support**

---

*Built in Pakistan. Works everywhere.*
