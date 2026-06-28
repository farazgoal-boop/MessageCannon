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
