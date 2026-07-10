# MessageCannon Pro — Code Rules

## Design System

**RULE: Koi bhi naya hex color kabhi nahi likhna. Sirf `src/ui/theme.py` ke tokens use karo.**

```python
from . import theme as T   # ya  from src.ui import theme as T
```

Available tokens:
| Token | Value | Use |
|---|---|---|
| `T.BG_MAIN` | `#0F1419` | App-level root background (darkest) |
| `T.BG_SURFACE` | `#2A4762` | Cards, panels — **1.92:1** vs BG_MAIN |
| `T.BG_INNER` | `#152C42` | Textboxes, deep nested (sunken inside cards) |
| `T.BG_BORDER` | `#3F5E84` | Borders, dividers — **1.45:1** vs BG_SURFACE |
| `T.BADGE_BG` | `#1F3A57` | Pills, chips, badge backgrounds |
| `T.NAV_INACTIVE` | `#18304A` | Inactive sidebar button background |
| `T.ACCENT` | `#6366F1` | Buttons bg, active nav — **use as fg_color only, NOT text_color on cards** |
| `T.ACCENT_HOVER` | `#4F46E5` | Hover state of ACCENT |
| `T.TEXT_HEAD` | `#E2E8F0` | Headings, values — **7.83:1** on BG_SURFACE |
| `T.TEXT_MUTED` | `#AEBBC8` | Labels, descriptions — **4.94:1** on BG_SURFACE (WCAG AA) |
| `T.TEXT_DIM` | `#7B8FA0` | Timestamps, metadata — use on BG_MAIN only |
| `T.SUCCESS` | `#10B981` | Positive states |
| `T.DANGER` | `#EF4444` | Destructive actions — use as fg_color only, NOT text_color on cards |
| `T.DANGER_HOVER` | `#DC2626` | Hover state of DANGER |
| `T.DANGER_ON_BADGE` | `#FF7B7B` | Red text **on BADGE_BG only** — 4.65:1 (T.DANGER gives 3.10:1 — FAIL) |

## What NOT to touch

- `CARD_STYLE_TEMPLATES` in `card_creator_tab.py` — these are HTML output colors for marketing cards, not app UI.
- `THEME_COLOR_PAIRS` dict in `main_window.py` — theme mapping keys, not widget attributes.
- `APP_PRESETS` accents in `card_creator_tab.py` — card branding values.

## Sidebar

Nav items are defined **once** at lines ~444-475 in `main_window.py`. Never add a second list.

## Python path

App runs via: `C:\Users\HAROON TRADERS\AppData\Local\Programs\Python\Python314\python.exe`
Venv at `.venv` may point to stale Python 3.13 path — always use Python314 directly if venv fails.

## Architecture

Entry point: `src/main.py` → builds `MainWindow` (`src/ui/main_window.py`, ~2870 lines). This one file owns the sidebar nav, Dashboard/Compose/Contacts/History/Cards/Settings views, and the real email/WhatsApp send logic — it is the center of gravity of the app.

```
src/
  main.py                    entry point, splash screen, dev/frozen-exe import bootstrap
  ui/
    main_window.py           THE app shell: nav, views, live email+WhatsApp send workers
    card_creator_tab.py      HTML card builder (Card Creator V2) — see "Card Creator" below
    campaigns_tab.py         read-only campaign history list (build_campaigns_view)
    reports_chart.py         matplotlib pie chart (read vs unread), embedded via FigureCanvasTkAgg
    theme.py                 SINGLE SOURCE for all colors — see Design System above
    email_tab.py             DEAD — legacy ttk.Frame tab, never imported by main_window.py
    main_window.py.backup    stray backup file, not imported, safe to ignore
  core/                      live business logic used by main_window.py
    whatsapp_sender.py       LIVE — Selenium/WhatsApp Web automation, delivery status polling
    contact_manager.py       LIVE — import_from_file() wraps modules/data_importer.py, validates + saves to DB
    email_sender.py          DEAD — not imported anywhere; real email sending is inline in main_window.py
    scheduler.py             campaign scheduling (schedule package)
  modules/
    data_importer.py         LIVE — UniversalDataImporter, used by both contact_manager.py and Card Creator's bulk-send dialog
    email_sender.py          DEAD — only used by the dead email_tab.py
    license_manager.py       mostly not wired in
  database/db_manager.py     SQLite — DatabaseManager, schema in DEFAULT_SCHEMA_SQL
  models/__init__.py         dataclasses: Contact, MessageLog, Campaign, Template, Settings; MessageStatus enum
  session_manager.py         persists the Chrome/WhatsApp Web session so users don't re-scan QR each launch
  delivery_tracker.py        background polling (5s) of WhatsApp message delivery status → messages table
  utils/                     constants, validators, logger, paths, license_manager
```

Two build manifests exist (`setup.py` vs `requirements.txt`) with diverging dependency lists — `setup.py` includes stale deps (`pywhatkit`, `qrcode`, `python-dotenv`, `apscheduler`) not used by any live code path. Trust `requirements.txt`.

## Send pipelines — live vs dead code

**Before editing any send-related code, confirm you're editing the LIVE path, not one of the dead duplicates:**

| Feature | LIVE implementation | DEAD duplicates (do not wire these up, do not "fix" bugs in them — delete or ignore) |
|---|---|---|
| Email send | `main_window.py:_start_email_from_compose()` (~1439-1560) — inline `smtplib`, builds `Campaign` row, substitutes `{name}/{email}/{phone}/{sender}/<custom>`, logs every send to `message_logs` via `db.add_message_log()` | `core/email_sender.py` (`EmailSender`), `modules/email_sender.py` (`BulkEmailSender`), `ui/email_tab.py` |
| WhatsApp send | `core/whatsapp_sender.py` (`WhatsAppSender`), triggered from `main_window.py:_start_sending()` (~2627-2688) — opens `web.whatsapp.com/send?phone=...`, watches DOM check-mark icons for delivery status | none — this is the only implementation |
| Contact import | `core/contact_manager.py:import_from_file()` (24-90) → `modules/data_importer.py` (`UniversalDataImporter`) → saves to DB via `db.add_contacts_batch()` | Card Creator's bulk-send dialog calls `UniversalDataImporter` **directly**, bypassing `ContactManager`/the DB — imported contacts there are in-memory only |

## Card Creator — current state (important caveat)

`card_creator_tab.py` generates real HTML marketing cards (`generate_html()`, styles from `CARD_STYLE_TEMPLATES`, presets from `APP_PRESETS` — both off-limits, see above). **Its "Bulk Send" dialog (`_show_bulk_send`, ~1031-1194) does not actually send anything today**: for WhatsApp it builds a `wa.me/...?text=...` string and marks it "sent" without opening it; for email it checks `if email:` and marks "sent"/"skipped" without touching SMTP. Results go to an in-memory `self._send_log`, never the DB. Treat this as a UI mock, not a working feature, until it's explicitly wired to the real send pipelines above.

## Database schema (`database/db_manager.py`, `DEFAULT_SCHEMA_SQL`)

- `contacts` — id, phone (UNIQUE), email, name, tags, custom_fields (JSON text), created_at
- `campaigns` — id, name, message_template, total_contacts, sent_count, failed_count, message_delay, use_jitter, scheduled_time, is_recurring, recurrence_pattern, timestamps
- `message_logs` — id, campaign_id (FK), contact_phone/email/name, subject, message_text, status, sent_at, error_message, retry_count (email path)
- `messages` — id, phone, message_text, status, sent_at, delivered_at, read_at, error_reason, whatsapp_message_id (WhatsApp path)
- `templates` — id, name (UNIQUE), category, message_text, description, is_default
- `settings` — key/value (e.g. `smtp_settings` JSON blob)

## AI Cards (premium tier) — in development

Direction locked in 2026-07: AI-assisted card creation as an unlockable **premium tier on top of the existing app** (not a rebrand). Rules for this feature as it's built:

- **BYO API key only.** Never proxy or bundle an API key server-side. Key is entered by the user in Settings, stored locally (encrypted via `cryptography`, same pattern as license key handling in `utils/license_manager.py`), never logged, never leaves the device except in direct calls to the provider.
- **Scope**: AI generates card copy/design (headline, features, tagline, style pick) AND per-contact personalization of the outgoing message — real tailored phrasing using each imported contact's columns (not just `{name}` substitution), not just a single static card blasted to everyone.
- **Must send for real.** Any AI-generated card campaign must go through the LIVE send pipelines above (`_start_email_from_compose` / `WhatsAppSender`), not a new mock. Do not replicate the Card Creator bulk-send simulation pattern.
- Preserve the existing "no cloud, no subscription" positioning of the base app — the AI tier is opt-in and user-funded (their own API key), so the core product's privacy/pricing story stays intact.
