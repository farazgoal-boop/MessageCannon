# Application Constants

APP_NAME = "MessageCannon Pro"
APP_VERSION = "1.4.0"
DEVELOPER = "Muhammad Faraz"
SUPPORT_EMAIL = "farazgoal@gmail.com"

# Default delays (seconds)
DEFAULT_MESSAGE_DELAY = 30
MIN_MESSAGE_DELAY = 10
MAX_MESSAGE_DELAY = 60
JITTER_RANGE = 5  # ±5 seconds

# Session limits
MAX_MESSAGES_PER_SESSION = 50
MAX_RETRY_ATTEMPTS = 1
RETRY_DELAY = 60  # seconds

# Real bounce/NDR reconciliation: how long after a campaign completes to
# automatically run one real IMAP bounce check, in milliseconds. Real hard
# bounces from major providers (Gmail, Outlook) typically arrive within
# seconds to a couple of minutes; a manual "Check for Bounces" action is
# always available too, for slower providers or a later re-check.
BOUNCE_AUTO_CHECK_DELAY_MS = 180_000  # 3 minutes

# UI Configuration
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750

# Color Scheme — Dark Premium Dashboard
COLOR_PRIMARY    = "#0d9488"       # Teal primary accent
COLOR_SECONDARY  = "#0f766e"       # Darker teal
COLOR_ACCENT     = "#14b8a6"       # Light teal highlight

# Sidebar (dark navy — unchanged)
SIDEBAR_BG       = "#1e2530"
SIDEBAR_HOVER    = "#252e3d"
SIDEBAR_ACTIVE   = "#1e3a5c"
SIDEBAR_TEXT     = "#94a3b8"
SIDEBAR_TEXT_ON  = "#ffffff"

# Top bar
TOPBAR_BG        = "#0d1521"       # Dark top bar
TOPBAR_BORDER    = "#1e3347"

# Content area
CONTENT_BG       = "#0a1118"       # Deep dark bg
CARD_BG          = "#101a24"       # Card surface
CARD_BG_INNER    = "#0c131b"       # Textbox / inner area
CARD_BORDER      = "#1e3347"       # Card border

# Text
TEXT_PRIMARY     = "#e5e7eb"       # Primary light text
TEXT_MUTED       = "#94a3b8"       # Muted text
TEXT_ACCENT      = "#5eead4"       # Teal accent text

# Inputs
INPUT_BG         = "#2a3142"
INPUT_BORDER     = "#3d4555"
INPUT_TEXT       = "#e5e7eb"

# Badges — uniform muted teal
BADGE_BG         = "#152535"
BADGE_TEXT       = "#5eead4"

# Stat card colours (dashboard)
STAT_TEAL        = "#0d9488"
STAT_BLUE        = "#2563eb"
STAT_ORANGE      = "#ea580c"
STAT_PURPLE      = "#7c3aed"

# ── Disciplined button color system ──────────────────────────────────────────
BTN_PRIMARY      = "#4f46e5"   # Indigo — all primary actions
BTN_PRIMARY_HVR  = "#4338ca"
BTN_DANGER       = "#991b1b"   # Red — destructive only (Stop, Reset, Delete)
BTN_DANGER_HVR   = "#7f1d1d"
BTN_NEUTRAL      = "#1e2d3d"   # Dark slate — secondary/utility
BTN_NEUTRAL_HVR  = "#253548"

# Legacy aliases (kept for other imports)
COLOR_SUCCESS    = "#4f46e5"
COLOR_WARNING    = "#4f46e5"
COLOR_DANGER     = "#991b1b"
COLOR_INFO       = "#1e2d3d"
COLOR_DARK_BG    = "#0a1118"
COLOR_LIGHT_BG   = "#101a24"
COLOR_DARK_TEXT  = "#e5e7eb"
COLOR_LIGHT_TEXT = "#94a3b8"

# Phone validation
PAKISTAN_COUNTRY_CODE = "+92"
PAKISTAN_PHONE_PATTERN = r"^\+92\d{10}$"

# Template variables
TEMPLATE_VARIABLES = [
    "{name}",
    "{phone}",
    "{amount}",
    "{date}",
    "{due_date}",
    "{flat_no}",
    "{custom1}",
    "{custom2}",
]

# Trial settings
TRIAL_DAYS = 3
PAID_PASSKEY = "3march2013"

# Database
DB_FILENAME = "messagecannon.db"
DB_LOCATION = "%APPDATA%/MessageCannon Pro"

# File extensions
ALLOWED_IMPORT_FORMATS = [".xlsx", ".xls", ".csv"]
PROJECT_FILE_EXTENSION = ".msgcannon"

# WhatsApp Web
WHATSAPP_WEB_URL = "https://web.whatsapp.com/"

# Message limits
MAX_MESSAGE_LENGTH = 65536
CHAR_LIMIT_WARNING = 2000
