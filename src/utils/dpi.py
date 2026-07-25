"""Windows per-monitor DPI awareness.

Root cause found while fixing the Setup Wizard sizing bug (live user
testing): this app never declared itself DPI-aware to Windows, so on any
scaled display (confirmed on this dev machine at 125%) Windows silently
bitmap-stretches the whole rendered window -- a `geometry("640x720")`
request renders at a real 800x900 physical pixels, while
`winfo_screenwidth()/winfo_screenheight()` keep reporting the *virtualized*,
un-scaled screen size Windows presents to non-DPI-aware apps. Any sizing or
centering math that mixes those two -- exactly what `_size_and_center()` and
`main.py`'s `_center_window()` do -- is comparing numbers in different units,
which is what actually let content/buttons render off the visible desktop
on the reporter's machine, not just a wizard-specific layout bug.

Must run before the first Tk/Toplevel is created in the process -- Windows
only honors a DPI-awareness declaration made before any window exists.
"""

from __future__ import annotations

import sys


def ensure_dpi_awareness() -> None:
    if sys.platform != "win32":
        return
    try:
        import ctypes
        try:
            # PROCESS_PER_MONITOR_DPI_AWARE -- correct scaling on whichever
            # monitor the window ends up on, not just the primary one.
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            # Older Windows without shcore -- system-DPI-aware fallback.
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass
