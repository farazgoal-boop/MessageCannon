# Application Constants

APP_NAME = "MessageCannon Pro"
APP_VERSION = "1.0.0"
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

# UI Configuration
WINDOW_WIDTH = 1100
WINDOW_HEIGHT = 750

# Color Scheme (professional dark slate + WhatsApp greens)
COLOR_PRIMARY = "#0B3F3A"          # Top bar / brand strip
COLOR_SECONDARY = "#165A53"        # Secondary actions
COLOR_ACCENT = "#2ECB73"           # Accent green
COLOR_DARK_BG = "#101922"          # Main dark surface
COLOR_LIGHT_BG = "#F2F6F8"         # Light surface background
COLOR_DARK_TEXT = "#EDF5F2"        # Primary text on dark
COLOR_LIGHT_TEXT = "#9CB1C0"       # Muted text on dark
COLOR_WARNING = "#FF6B6B"          # Warning red
COLOR_SUCCESS = "#2DBD6E"          # Success green
COLOR_INFO = "#56B4E9"             # Informational blue

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
DB_LOCATION = "~/.messagecannon"

# File extensions
ALLOWED_IMPORT_FORMATS = [".xlsx", ".xls", ".csv"]
PROJECT_FILE_EXTENSION = ".msgcannon"

# WhatsApp Web
WHATSAPP_WEB_URL = "https://web.whatsapp.com/"

# Message limits
MAX_MESSAGE_LENGTH = 65536
CHAR_LIMIT_WARNING = 2000
