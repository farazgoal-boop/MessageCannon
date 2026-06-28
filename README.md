# MessageCannon Pro

**Professional bulk messaging — WhatsApp + Email + branded HTML cards**

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20macOS%20%7C%20Linux-brightgreen.svg)]()
[![License: Commercial](https://img.shields.io/badge/License-Commercial-orange.svg)]()

---

## What is MessageCannon Pro?

MessageCannon Pro is a desktop application for sending personalized bulk messages via WhatsApp Web and Email (SMTP). It runs entirely on your own machine — no cloud, no monthly fees, no third-party servers handle your contacts.

**Who uses it:**
- Schools and coaching centers (fee reminders)
- Clinics (appointment reminders)
- Real estate agents (property alerts)
- E-commerce businesses (order updates, promotions)
- Marketing agencies (client campaigns)

---

## Features

| Module | What it does |
|---|---|
| **WhatsApp Campaigns** | Send personalized messages via WhatsApp Web (Selenium). Adjustable delay, jitter, daily limit. |
| **Email Campaigns** | SMTP-based bulk email with HTML templates. Supports Gmail App Passwords and any SMTP provider. |
| **Card Creator** | Visual drag-and-drop HTML card builder. Add banner images, YouTube videos, text, pricing, links. Send cards by email or share via browser. |
| **Contacts Manager** | Import from Excel/CSV/HTML. Filter, search, tag contacts. |
| **Campaign History** | Full delivery log. Export reports as PDF or CSV. |
| **Reports & Analytics** | Live delivery rate, read vs unread pie chart, timeline. |
| **Settings** | Rate limits, theme (Dark/Light), SMTP config, license. |

---

## Quick Start

### Windows (installer)
1. Download `MessageCannonPro-Setup.exe`
2. Run the installer — no admin required, installs per-user
3. Launch from desktop shortcut
4. On first run: enter your license key

### macOS
1. Download `MessageCannonPro-Mac-1.0.0.dmg`
2. Open the DMG, drag **MessageCannon Pro.app** to Applications
3. Right-click → Open (first launch only, to allow unsigned app)

### Linux (.deb)
```bash
sudo dpkg -i messagecannon-pro_1.0.0_amd64.deb
messagecannon-pro
```

### Run from source
```bash
git clone https://github.com/farazgoal/MessageCannon.git
cd MessageCannon
pip install -r requirements.txt
python -m src.main
```

---

## Email — Gmail Setup

Gmail requires an **App Password** (your normal password will not work):

1. Go to [myaccount.google.com](https://myaccount.google.com) → Security
2. Enable **2-Step Verification** if not already on
3. Go to **App Passwords** → Select "Mail" → Generate
4. Copy the 16-character password into MessageCannon Settings → SMTP → Password
5. Set **Host** to `smtp.gmail.com`, **Port** `587`

---

## Build from Source

### Windows
```batch
build\build_windows.bat
```
Produces `dist\MessageCannon Pro.exe` and (if Inno Setup installed) `dist\MessageCannonPro-Setup.exe`.

### macOS
```bash
bash build/build_mac.sh
```
Produces `dist/MessageCannon Pro.app` and `dist/MessageCannonPro-Mac-1.0.0.dmg`.

### Linux
```bash
bash build/build_linux.sh
```
Produces `dist/messagecannon-pro` (portable binary) and `dist/messagecannon-pro_1.0.0_amd64.deb`.

### All platforms (auto-detect)
```bash
python build/build_all.py
```

**Build dependencies:**
```bash
pip install -r build/requirements_build.txt
```

---

## System Requirements

| | Windows | macOS | Linux |
|---|---|---|---|
| **OS** | Windows 10/11 (64-bit) | macOS 12+ | Ubuntu 20.04+ / Debian 11+ |
| **Chrome** | Required for WhatsApp | Required | Required |
| **Python** | Not required (installer) | Not required (DMG) | Not required (.deb) |
| **RAM** | 512 MB | 512 MB | 512 MB |

---

## Documentation

- [User Guide](docs/user_guide.md) — step-by-step for all features
- [WhatsApp Compliance](docs/whatsapp_guidelines.md) — avoid bans
- [API Reference](docs/api_reference.md) — for developers

---

## Safety & Compliance

MessageCannon Pro is built for **legitimate business communication**:
- Built-in minimum 10-second delay between messages
- Random jitter to avoid pattern detection
- Recipient consent checkbox (required before send)
- Daily send limit with configurable cap
- All data stays on your machine

Users are responsible for complying with WhatsApp Terms of Service and local anti-spam laws.

---

## License & Pricing

| Package | Price |
|---|---|
| Single License | Rs 8,000 PKR / $29 USD |
| 5-Pack | Rs 25,000 PKR / $99 USD |

One-time payment. Lifetime updates included.
Contact: [farazgoal@gmail.com](mailto:farazgoal@gmail.com)

---

**Muhammad Faraz** — Full Stack Developer  
[muhammad-faraz-dev.netlify.app](https://muhammad-faraz-dev.netlify.app)
