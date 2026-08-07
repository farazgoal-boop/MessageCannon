# MessageCannon Pro — Getting Started Guide

Version 1.5.0 · Support: farazgoal@gmail.com · Generated 2026-08-07

> **A note on screenshots:** this guide is written to be followed with the real app open next to it. Sections marked "📸 Screenshot needed" describe exactly what to capture — those images weren't captured automatically for this pass (see the top of `docs/user_manual_content.py` for why), so Faraz should add his own screenshot for each one before sharing this guide externally.

---

## Welcome to MessageCannon Pro

MessageCannon Pro helps you send personalized WhatsApp messages and branded emails to your customers, students, patients, or clients — all from your own computer. There's no cloud account, no monthly subscription, and your contacts never leave your device.

This guide walks through everything from installing the app to sending your first real campaign. You don't need any technical background — if you can use email and WhatsApp on your phone, you can use this app.

> 💡 **Tip:** Keep this guide handy the first few times you use the app. Once you're comfortable, you can always get a quick refresher from the built-in Guided Tour — see the section on that below.

---

## 1. Installing MessageCannon Pro

Download the installer for your computer from the link Faraz gave you, then follow the steps for your operating system below.

### Windows

1. Download MessageCannon_Setup.exe
2. Double-click it to run the installer
3. If Windows shows a blue "Windows protected your PC" warning, click "More info" then "Run anyway" — this appears because the installer isn't yet digitally signed, not because anything is wrong
4. The installer doesn't need an administrator password — it installs to your own user folder
5. When it finishes, launch MessageCannon Pro from the Start Menu or the desktop shortcut

> 💡 **Tip:** To update later, you don't need to repeat this — the app checks for new versions on its own and can install them with one click (see the sidebar's update badge, described later in this guide).

### macOS

1. Download MessageCannonPro-mac.dmg
2. Double-click it to open the disk image window
3. Drag "MessageCannon Pro" into the Applications folder shown in that same window
4. The first time only: go to Applications, right-click the app, and choose "Open" — then click "Open" again in the dialog that appears. This one-time step is required because the app isn't yet notarized by Apple; double-clicking normally will refuse to open it
5. After that first launch, you can open it normally by double-clicking

### Linux

Debian/Ubuntu-based systems (.deb):

- Open a terminal and run: sudo dpkg -i MessageCannonPro-linux-<version>.deb
- Launch it from your applications menu, or type messagecannon-pro in a terminal

Any other distribution (AppImage):

- chmod +x MessageCannonPro-linux-<version>.AppImage
- ./MessageCannonPro-linux-<version>.AppImage

> 📸 **Screenshot needed:** The installer running on your own screen (Windows SmartScreen warning + "Run anyway", or the macOS Applications drag step) — whichever operating system you install on.

---

## 2. First Launch: License & Setup Wizard

### License activation

The first time you open MessageCannon Pro, it runs in a free 3-day trial — every feature works during the trial, so you can try everything before deciding.

Once the trial ends, you'll see an "Activate MessageCannon" screen. This is a one-time step:

1. The screen shows a Request Code that's unique to your computer — click "Copy" next to it
2. Send that code to Faraz (farazgoal@gmail.com) the way you normally would (email, WhatsApp, etc.)
3. He'll reply with an Activation Code made specifically for your computer
4. Paste that Activation Code into the "Enter activation code" box and press Enter
5. The app unlocks immediately — no restart needed

> 💡 **Tip:** The activation code only works on the computer that generated the request code. If you ever move to a new computer, just generate a new request code there and ask for a fresh activation code — no need to "transfer" anything.

> 📸 **Screenshot needed:** The "Activate MessageCannon" screen showing the Request Code field and the "Enter activation code" box.

### The Setup Wizard

Right after your first launch, a Setup Wizard walks you through connecting the two ways MessageCannon Pro can send messages: Email and WhatsApp. You can set up one or both — whichever you plan to use.

### Connecting Email

If you choose Email, the wizard asks for your email provider's sending details (this is the same information Settings uses later, so you only ever enter it once):

| Field | What to enter |
|---|---|
| Provider | Gmail, Outlook, Yahoo, or Custom — picking a provider auto-fills the Host and Port for you |
| Username | Your full email address |
| Password | Your email password, or an App Password (Gmail and Yahoo require this — see below) |
| Sender Name | The name recipients see, e.g. "Green Valley School" |

### Gmail — App Password (required)

Gmail blocks your normal password for apps like this one. You need to create a separate App Password once:

1. Go to myaccount.google.com in your browser
2. Click Security, then turn on 2-Step Verification if it isn't on already
3. Still on the Security page, find and click "App passwords"
4. Choose "Mail" as the app, generate the password, and copy the 16-character code shown
5. Paste that code as your Password in the wizard (or in Settings later) — not your normal Gmail password

> 💡 **Tip:** Yahoo Mail works the same way — turn on 2-step verification, then generate an app password. Outlook usually works with your normal password unless you have extra security turned on.

Click "Test Connection" in the wizard — a real, live check against your email account. A green confirmation means it's ready to send; a clear error message explains what to fix if not.

### Connecting WhatsApp

If you choose WhatsApp, the wizard opens a real Chrome browser window showing a WhatsApp Web QR code — the exact same screen you'd see opening web.whatsapp.com yourself.

1. On your phone, open WhatsApp
2. Go to Settings → Linked Devices → Link a Device
3. Point your phone's camera at the QR code on your computer screen
4. Once linked, the wizard shows a real connected status and lets you send a test message to confirm everything works

> 💡 **Tip:** This connection is remembered — you won't need to scan the QR code again on future launches unless you log out or the session expires. You can reconnect anytime from Settings → System Experience → "Connect WhatsApp".

> 📸 **Screenshot needed:** The Setup Wizard's WhatsApp step showing the real QR code in the opened Chrome window.

---

## 3. Importing Your Contacts

Open Contacts from the left sidebar, then click "Import Contacts" and choose a file — Excel (.xlsx), CSV, or an HTML table.

### What your file needs

- Column headers in the first row
- At least a phone column (for WhatsApp) or an email column (for email) — a contact needs one or the other, not necessarily both
- Any extra column you add (amount, due_date, class, flat_no — anything) becomes a personalization variable you can use in your messages, described in the next section

| name | phone | email | amount | due_date |
|---|---|---|---|---|
| Ahmad Ali | 03001234567 | ahmad@example.com | 25,000 | 5 Jan |
| Sara Khan | 03119876543 | sara@example.com | 18,000 | 7 Jan |
| Usman Raza | +923331122334 |  | 30,000 | 10 Jan |

Phone numbers are cleaned up automatically — spaces and dashes are removed, and a local Pakistani number like 03001234567 is converted to +923001234567 for you. If a number can't be understood, the import review screen tells you exactly why (missing country code, too short, contains letters, etc.) instead of just silently rejecting it.

### The import review screen

Before anything is saved, MessageCannon Pro shows you a full preview: how many contacts are ready, how many are duplicates already in your list, and how many have a problem — each with its own clear reason. For duplicates, you choose whether to Skip them or Merge (fill in any blank details on the existing contact without overwriting anything you already have).

Nothing is saved to your contact list until you confirm — you can always cancel and fix your file first.

> 📸 **Screenshot needed:** The import review screen showing the ready/duplicate/invalid counts and a few example rows with their status.

---

## 4. Composing Your First Message

Open Compose from the sidebar. Choose the WhatsApp or Email tab at the top, depending on which you want to send.

### Personalizing with variables

Instead of typing a contact's name into every message by hand, use the "Insert variable ▾" dropdown above the message box. Pick Name, Amount, Date, or any custom column from your import file, and it's inserted as a small highlighted tag right where your cursor is. When the message actually sends, each tag is swapped for that specific contact's own real value.

Example: "Hi {name}, your fee of {amount} is due on {due_date}." becomes "Hi Ahmad Ali, your fee of 25,000 is due on 5 Jan." for Ahmad, and the correct personal values for everyone else, automatically.

### Writing with AI

Click "Generate with AI" and describe what you want in a sentence or two — e.g. "a friendly reminder about the monthly fee, due in 5 days." The AI drafts three genuinely different versions (not just three reworded copies of the same idea) that you can review, edit, and pick from before sending.

> 💡 **Tip:** AI features need your own API key from Anthropic or Google Gemini, entered once in Settings → AI Cards. Google Gemini has a genuine free tier — no card required — so you can try this without any cost. Settings has a "Get an API key →" link that takes you straight to the right sign-up page.

For email, an "✨ Optimize" button next to the Subject field suggests three alternative subject lines with a short reason for each (urgency, curiosity, personalization) — pick whichever fits.

### Checking your message before sending

Compose shows a live preview using one of your real, already-imported contacts, so you can see exactly what a recipient will actually receive — not a placeholder. For email, it also warns you about anything that commonly gets flagged as spam (words like "free", "act now", a subject line that's too short) before you send, not after.

> 📸 **Screenshot needed:** The Compose screen with a message written using a couple of "Insert variable" tags, and the live preview panel showing the personalized result.

---

## 5. Creating a Marketing Card

Open Cards from the sidebar to design a real, standalone marketing card — a small branded webpage-style card with an image, price, and a working "Buy Now" button, that you can send by email or WhatsApp.

### Building a card

1. Pick a starting point from the template gallery (SaaS Product, Service Business, E-commerce, Event/Webinar, or Custom) — or load one you saved before
2. Fill in your app/product name, tagline, and upload your own logo by dragging an image onto the drop zone (or click to browse)
3. Add sections in any order — a banner image, a short description, a features list, pricing with an optional discount, and your own contact details
4. For the price section, set "Button Text" (defaults to "Buy Now") and your real "Purchase Link URL" — this becomes an actual clickable button in the finished card, not just a picture
5. Watch the Live Card Preview update as you type

You can also let AI suggest a matching color style and draft feature bullets from a short brief, the same way it drafts message copy in Compose.

Liked what you built? Click "Save as My Template" to reuse the same identity and style for future cards.

### Sending the card

Click "📩 Insert into Compose" — this is the real, working way to send a card. For email, it loads the finished card straight into Compose ready to send as a genuine visual HTML email (gradients, image, and the real Buy Now button all intact). For WhatsApp, it's converted into a clear plain-text message with your real purchase link included, since WhatsApp itself can't display a styled card.

> 📸 **Screenshot needed:** The Card Creator with a finished card in the Live Card Preview panel, showing a real image, price, and Buy Now button.

---

## 6. Sending a Campaign Safely

When you click "Start" on a real campaign, MessageCannon Pro always shows a confirmation summary first — how many people will receive it, the delay between each message, an estimated finish time, and (for email) the exact subject line and a preview of the first few real messages — so you always know exactly what's about to go out before it does.

### Why sending slowly matters

Both WhatsApp and email providers actively watch for accounts that send too many messages too quickly, and can temporarily or permanently restrict an account that looks like it's spamming. MessageCannon Pro has several built-in protections, already turned on by default:

| Setting | What it does | Default |
|---|---|---|
| Delay between messages | How many seconds to wait before sending the next one | 30 seconds |
| Random jitter | Adds a small random amount to that delay, so messages don't go out at perfectly even intervals (which itself looks automated) | On |
| Daily send limit | The maximum total messages sent in one day, across every campaign | 50 per day |
| Email warm-up ramp | For the first 14 days on a new email account, gradually raises your daily cap instead of allowing the full limit from day one | On |

> ⚠️ **Caution:** Unofficial WhatsApp automation at high volume (hundreds or thousands of messages a day) on a personal number carries a real risk of that number being banned by WhatsApp — this is a WhatsApp policy matter, not something any app can fully prevent. Keep daily volume conservative and treat a connected number as replaceable, not permanent.

You can adjust the delay and daily limit in Settings → Campaign Safety, but the built-in minimums exist to protect your accounts — lowering them significantly increases your real risk of being blocked.

### During and after sending

While a campaign is running, you'll see live progress — how many sent, how many failed, and an estimated time remaining. You can pause and resume at any point. If anything fails partway through, a report afterward lists exactly which contacts failed and why, with a one-click "Retry Failed Only" button so you don't have to resend to everyone again.

> 📸 **Screenshot needed:** The pre-send confirmation dialog showing recipient count, delay, estimated time, and a real message preview.

---

## 7. Checking Delivery & Bounce Results

"Sent" only means your email provider or WhatsApp accepted the message for delivery — it doesn't guarantee the recipient actually received it. MessageCannon Pro checks for real bounces on email campaigns and gives you an honest picture instead of just assuming everything worked.

### How bounce checking works

A few minutes after an email campaign finishes, the app checks your real inbox (read-only — it never deletes or changes anything) for bounce notifications, and matches each one back to the exact contact it belongs to. You can also trigger this manually anytime from the "🔍 Check for Bounces" button in a campaign's report or in the History screen.

### Reading the results

| Result | What it means |
|---|---|
| Sent | Your provider accepted the message — the honest baseline, not proof of delivery |
| Bounced | Confirmed, from a real bounce notification in your inbox — this address genuinely failed |
| Delivered (assumed) | Sent minus confirmed bounces — a reasonable assumption, not a fact, since email has no built-in "read receipt" for delivery the way WhatsApp does |

A contact whose address bounces is automatically flagged so future campaigns won't keep emailing a dead address — you can clear that flag from the Contacts screen if the address was fixed or the bounce was a mistake.

### History screen

Every past campaign is listed in History with its real sent, failed, and bounced counts, and a "Duplicate" button to reuse the same message and recipient list as a starting point for a new campaign.

> 📸 **Screenshot needed:** A campaign report showing the Sent / Bounced / Delivered (assumed) breakdown after a real bounce check.

---

## 8. Getting a Refresher: The Guided Tour

Whenever you want a quick walkthrough of the app again — for yourself later on, or to show someone else on your team — click the "?" button in the top-right header, right next to the Settings gear icon. You can also find a "🧭 Take a Tour" button inside Settings → System Experience.

The tour opens a short series of cards, one for each major part of the app (Campaigns, Contacts, Compose, Cards, delivery tracking, Settings, and updates), with the real matching item in the sidebar highlighted so it's always clear exactly what's being described. Use Next/Back to move through it, or Skip to close it anytime.

> 💡 **Tip:** The tour always starts fresh from the beginning every time you open it — there's nothing to reset, and running it again never loses any of your real data or settings.

> 📸 **Screenshot needed:** The Guided Tour open on one of its steps, with the highlighted ring visible around the matching sidebar item.

---

## 9. Troubleshooting Common Issues

| What you see | What it usually means | What to do |
|---|---|---|
| "Authentication failed" when testing email | Your email password isn't accepted — Gmail/Yahoo need an App Password, not your normal one | Generate an App Password (see "Connecting Email" above) and use that instead |
| Email "Connection refused" or times out | Wrong host/port, or a firewall/antivirus is blocking the connection | Double-check Host and Port against your provider's settings; try port 465 if 587 doesn't work |
| WhatsApp QR code never appears | Chrome may not be installed, or a previous session is stuck | Make sure Google Chrome is installed, then click "Connect WhatsApp" in Settings to try again |
| WhatsApp says connected, but a contact says they never got the message | The number may be invalid, or WhatsApp itself silently failed to deliver it | Check the campaign report for that contact's specific status; confirm the number is correct and active on WhatsApp |
| Contacts won't import | The file is missing a phone or email column, or every row failed validation | Open the import review screen — it lists the exact reason for every skipped row, not just a total count |
| A message shows {name} literally instead of the contact's real name | That contact's row has a blank value for that column | Check your import file — a blank cell has nothing to substitute |
| "Trial Expired" / can't activate | Your activation code doesn't match this computer's request code | Copy the Request Code shown on screen and send it to Faraz for a fresh matching activation code |
| Update won't download or install | No internet connection, or no installer is available yet for your operating system | Check your connection and try again; use "View on GitHub" to download manually if needed |
| "Can't auto-detect IMAP settings" when checking for bounces | Bounce checking only recognizes Gmail, Outlook, and Yahoo automatically | Contact support for help configuring bounce checking with a custom email provider |

Still stuck? Reach out to farazgoal@gmail.com — include a screenshot of the exact message you're seeing if you can, it makes it much faster to help.
