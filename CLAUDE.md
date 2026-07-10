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
    setup_wizard.py          First-run setup wizard (Welcome → channel choice → per-channel
                              creds/connect/test-send) — see "Setup Wizard" below
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

## UX overhaul — 5-phase plan, one phase at a time

Direction locked 2026-07-11: a 5-phase UX pass (setup wizard → contact import validation →
AI content variations → bulletproof bulk send → app-wide polish), each phase on its own branch
off `main`, each proven with real execution (not claimed) before moving to the next.

### Phase 1 — First-run Setup Wizard (complete, branch `phase-1-setup-wizard`)

`src/ui/setup_wizard.py` — `SetupWizard(ctk.CTkToplevel)` / `show_setup_wizard(main_window, force_restart=False)`.

- Flow: Welcome → channel choice (Email/WhatsApp/Both) → per selected channel in sequence:
  credentials (Email only) → real test/connect → real test send → Done. "Both" walks the Email
  sequence then the WhatsApp sequence back-to-back rather than a combined form.
- Email step reuses `main_window`'s own `_em_*` StringVars directly (no separate storage) and
  a newly-extracted `main_window._test_smtp_connection(on_result=None)` — same method Settings'
  own "Test connection" button calls, so wizard and Settings can never drift apart.
- WhatsApp step calls `whatsapp_sender.initialize()` in a background thread (same pattern as
  the existing boot-time `_start_session_bootstrap`) — opens a real Chrome window for the user
  to scan a QR code; no async/QR-image callback exists in `WhatsAppSender`, so this is the only
  integration point available.
- Progress persists in the existing `ui_preferences` settings blob (`setup_wizard_completed`,
  `setup_wizard_skipped`, `setup_wizard_channels`, `setup_wizard_channel_index`,
  `setup_wizard_substep`) via `main_window._save_wizard_progress(**kwargs)`. Closing the wizard
  mid-flow just persists wherever it was — next launch resumes at that exact substep instead of
  restarting (verified). "Skip for now" sticks (wizard won't auto-reopen) but surfaces a
  dismissible "Finish setup" banner on the Campaigns/Dashboard view
  (`MainWindow._refresh_setup_banner()`, called both at view-build time and live after Skip,
  since the view is only constructed once at startup). Settings has a "Re-run Setup Wizard"
  button (System Experience card) for redoing setup anytime, unrelated to the auto-open logic.
- Verified end-to-end via a programmatic driver (direct method/button-command invocation +
  screenshot capture, not mouse simulation — mouse-click automation proved unreliable in this
  sandbox): fresh auto-open, real SMTP failure surfaced from an actual Gmail connection attempt
  with wrong credentials (not a mock), resume-after-close-mid-wizard, skip-persists +
  banner-appears-live. **Not verified by Claude**: a successful SMTP send (needs real
  credentials) and the WhatsApp QR-scan step (needs a phone) — left for the user to confirm
  live, per their own choice.

### Theme system — Warm Ivory added (complete, branch `phase-2-contact-import`)

`theme.py` now supports a third named palette ("dark"/"light"/"warm_ivory") via a module-level
`__getattr__` resolving against `theme.get_palette()`/`set_palette()`, so every existing `T.TOKEN`
call site is unchanged. Dark<->Light<->System still uses CTk's fast native in-place tuple
resolution (no rebuild). Entering/leaving Warm Ivory triggers a full sidebar+content rebuild
(`MainWindow._rebuild_ui_for_theme`) since CTk's binary appearance mode has no way to represent
a 3rd state on already-built widgets — this is a deliberate, documented tradeoff (see theme.py's
module docstring), not a bug. Verified via screenshots: all three palettes render correctly and
round-trip cleanly.

### Phase 2 — Contact Import review flow (complete, branch `phase-2-contact-import`)

Replaced the old "pick a file, get a bare count" import with a real review flow:
`src/ui/contact_import_review.py` (`ContactImportReviewDialog`) — drag-and-drop (via
`tkinterdnd2`, attached to the CTk root through `TkinterDnD._require(self)`, new dependency) or
Browse, a scrollable per-row preview table with color-coded status pills and a specific reason
per row, a duplicate resolution choice (Skip/Merge — see below for why not literally
"Merge/Skip/Keep Both"), and an accurate completion summary.

New engine in `core/contact_manager.py`: `analyze_import()` (pure — parses + classifies, never
touches the DB) and `commit_import()` (writes only what the user approved). New `db_manager.py`
helpers: `get_existing_phones()`, `update_contact_by_phone()` (merge — existing data always wins,
only fills blanks).

**Real bugs found and fixed while verifying with a deliberately messy test CSV** (not just noted —
fixed at the root cause, per standing instructions):
1. `data_importer.py`'s `_clean_phone`/`_clean_email` were silently discarding malformed values
   before any validator ever saw them, so "specific reason" was impossible — they were nulling
   the very data needed to explain the rejection. Fixed to pass values through unjudged; real
   validation (with a reason) now happens exactly once, in `PhoneValidator`/`DataValidator`.
2. `PhoneValidator.normalize_phone()` only had two generic error strings. Added
   `_describe_phone_error()` for specific reasons (missing country code, too short, too long,
   invalid characters).
3. **The live production database's `contacts.phone` column is `NOT NULL` — an older, already-
   deployed schema than the aspirational `phone TEXT UNIQUE` (no NOT NULL) in `db_manager.py`'s
   own `CREATE TABLE IF NOT EXISTS`, which only applies to brand-new installs.** This means
   email-only contacts have probably never actually saved in this app, ever — the old
   `import_from_file` path passed `phone=None` for them, which the real DB always rejected via a
   silently-caught `IntegrityError`, with zero explanation ever shown to the user. Confirmed a
   real orphaned row from this exact failure mode already sitting in the live DB. Considered an
   email-derived placeholder phone value as a workaround, but rejected it: `contact.phone` is
   used as the literal WhatsApp send target and gets substituted into `{phone}` in real message
   templates elsewhere in the app (`main_window.py`, `core/whatsapp_sender.py`) — a fake
   placeholder would leak into the Contacts list display, search, and real outgoing messages.
   Chose the honest fix instead: a phone number is required to import a contact, and email-only
   rows are now clearly flagged "invalid" with that exact reason — a real improvement over the
   previous silent failure, not a new limitation. **A proper schema migration (rebuild the
   `contacts` table without the NOT NULL constraint) would let email-only contacts work
   end-to-end, but was judged too risky to do inline against a live production database in this
   pass — flagging it as a known follow-up, not doing it silently.**
4. `commit_import`'s merge logic had new-value-wins priority backwards — it would have let an
   imported row silently overwrite a real existing contact's name/email, contradicting the UI's
   own "never overwrites" promise. Caught by testing the merge path against a real existing
   contact before shipping (not just synthetic data) and fixed to existing-wins,
   fill-blanks-only, before it ever reached a real merge.

Verified end-to-end with a deliberately messy CSV (duplicates, bad phone, bad email, empty row,
email-only row) via a programmatic driver + screenshots: correct classification counts, correct
per-row reasons, correct duplicate detection against both the file and the real DB, correct
skip/merge behavior (merge tested against a real contact and confirmed non-destructive), accurate
completion summary. All test rows cleaned up from the real database afterward.

### Phase 3 — AI-Generated Marketing Content (branch `phase-3-ai-content`)

Compose screen already had more infrastructure than the spec assumed — reused rather than
rebuilt: `_refresh_preview()` already rendered live preview against real selected contacts via
`MessageProcessor.substitute_variables`; `MessageProcessor.validate_template()` already did
WhatsApp length validation; `{variable}` insert buttons already existed. New work built on top:

- `src/ui/ai_compose_dialog.py` (`AIComposeDialog`) — shared by both WhatsApp and Email compose
  panels. User gives a brief, `ai_service.generate_message_variations()` (new function) returns
  3 genuinely different variations (not reworded copies of one idea — the prompt explicitly
  requires different angle/tone/structure), shown as cards the user can edit before picking.
  Told exactly which `{variable}` names are available (from the first selected contact's
  `custom_fields`) so it never invents variables that don't exist in the imported data.
- Variable highlighting: `{variable}` tokens get a distinct accent color inside both the
  WhatsApp `CTkTextbox` and the raw-tk email body, via `Text.tag_add`/`tag_config` on regex
  matches — re-applied on every keystroke alongside the existing live preview refresh.
- Inline warnings, updated live: WhatsApp reuses `MessageProcessor.validate_template()`
  (already existed). Email got two new `DataValidator` methods —
  `check_spam_trigger_words()` and `check_subject_length()` — since nothing already checked
  those.
- "Save as Template" — new dialog (name + category) wired to `db.add_template()`
  (already existed, was just never exposed from Compose).
- Found and fixed a latent bug while wiring this in: `_em_subj_var.trace_add()` was being
  re-registered every time `_build_compose_view()` runs, but that StringVar is created once in
  `__init__` and outlives UI rebuilds (e.g. the Warm Ivory theme's rebuild) — repeated theme
  switches would have silently stacked duplicate trace callbacks. Guarded with a one-time flag.

Not built: a dedicated template library/search screen (spec's own "if more than a handful of
templates exist" framing made this conditional/lower-priority; the existing Template dropdown
already lists everything, just without search — flagging as a deferred nice-to-have, not
silently dropped).

Verified via a programmatic driver + screenshots (network layer mocked — no real Anthropic key
available in this environment, everything else is the real UI code path, not simulated):
variable highlighting confirmed in both the WhatsApp `CTkTextbox` and the raw-tk email body,
WhatsApp character-count warning, email subject-length + spam-word warnings correctly triggered
on deliberately bad test input ("hi" subject + "click here now for a 100% free cash bonus!!!
Act now!" body → correctly flagged all three), the AI variations dialog rendering + "Use this"
correctly loading a picked variation back into the editor for both channels, and the Save-as-
Template dialog rendering with the right pre-filled category. **Not verified**: an actual
successful AI generation against the real Anthropic API (needs your key) and delivery of a real
message (needs real SMTP/WhatsApp session, already covered by Phase 1).

Phases 4-5 (bulletproof bulk send, app-wide polish) and the signature transition animation not
yet started.
