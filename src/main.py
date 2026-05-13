"""
MessageCannon - Professional WhatsApp Bulk Messaging Application
Entry point for the application.
"""

import os
import sys
from pathlib import Path


def _ensure_tcl_tk_paths() -> None:
    """Set Tcl/Tk env vars for Windows venvs when Python cannot locate init.tcl."""
    if os.environ.get("TCL_LIBRARY") and os.environ.get("TK_LIBRARY"):
        return

    candidate_bases = [Path(sys.base_prefix), Path(sys.executable).resolve().parent.parent]
    for base in candidate_bases:
        tcl_dir = base / "tcl" / "tcl8.6"
        tk_dir = base / "tcl" / "tk8.6"
        if tcl_dir.exists() and tk_dir.exists():
            os.environ.setdefault("TCL_LIBRARY", str(tcl_dir))
            os.environ.setdefault("TK_LIBRARY", str(tk_dir))
            return


_ensure_tcl_tk_paths()

try:
    from src.ui.main_window import MainWindow
    from src.utils.logger import Logger
except ModuleNotFoundError:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    from src.ui.main_window import MainWindow
    from src.utils.logger import Logger


def main():
    """Main application entry point."""
    try:
        Logger.info("=" * 50)
        Logger.info("MessageCannon v1.0.0 Starting...")
        Logger.info("=" * 50)
        
        app = MainWindow()
        app.mainloop()
        
        Logger.info("MessageCannon application closed")
    
    except Exception as e:
        Logger.critical(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
