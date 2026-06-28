"""Application entry point with startup branding helpers."""

import os
import sys
import tkinter as tk
from pathlib import Path

import customtkinter as ctk
from PIL import Image
from src.ui import theme as T


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


def _bootstrap_import_path() -> None:
    """Ensure `src` imports work in dev and in PyInstaller frozen EXE."""
    if getattr(sys, "frozen", False):
        meipass = Path(getattr(sys, "_MEIPASS", ""))
        if meipass.exists():
            root = str(meipass)
            if root not in sys.path:
                sys.path.insert(0, root)
        return

    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))


_bootstrap_import_path()

from src.ui.main_window import MainWindow
from src.utils.constants import APP_NAME, APP_VERSION
from src.utils.logger import Logger


def _runtime_asset_path(*parts: str) -> Path:
    base_path = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base_path.joinpath(*parts)


def _configure_window_icon(app: MainWindow) -> None:
    ico_path = _runtime_asset_path("assets", "icons", "app.ico")
    png_path = _runtime_asset_path("assets", "icons", "app.png")

    try:
        if ico_path.exists():
            app.iconbitmap(default=str(ico_path))
    except Exception as exc:
        Logger.warning(f"Could not apply ICO window icon: {exc}")

    try:
        if png_path.exists():
            icon_image = tk.PhotoImage(file=str(png_path))
            app.iconphoto(True, icon_image)
            app._window_icon_ref = icon_image
    except Exception as exc:
        Logger.warning(f"Could not apply PNG window icon: {exc}")


def _center_window(window: tk.Toplevel, width: int, height: int) -> None:
    window.update_idletasks()
    screen_width = window.winfo_screenwidth()
    screen_height = window.winfo_screenheight()
    x_pos = max((screen_width - width) // 2, 0)
    y_pos = max((screen_height - height) // 2, 0)
    window.geometry(f"{width}x{height}+{x_pos}+{y_pos}")


def _show_startup_splash(app: MainWindow) -> None:
    splash = ctk.CTkToplevel(app)
    splash.title(f"{APP_NAME} Loading")
    splash.overrideredirect(True)
    splash.attributes("-topmost", True)
    splash.configure(fg_color=T.BG_MAIN)

    shell = ctk.CTkFrame(splash, fg_color=T.BG_SURFACE, corner_radius=24,
                         border_width=1, border_color=T.BG_BORDER)
    shell.pack(fill="both", expand=True, padx=2, pady=2)
    shell.grid_columnconfigure(1, weight=1)

    logo_path = _runtime_asset_path("assets", "icons", "app.png")
    logo = None
    if logo_path.exists():
        try:
            logo = ctk.CTkImage(light_image=Image.open(logo_path), dark_image=Image.open(logo_path), size=(80, 80))
        except Exception as exc:
            Logger.warning(f"Could not load splash image: {exc}")

    ctk.CTkLabel(
        shell,
        text="" if logo is not None else "MC",
        image=logo,
        width=88,
        height=88,
        corner_radius=22,
        fg_color=T.BG_INNER,
        font=ctk.CTkFont(size=28, weight="bold"),
    ).grid(row=0, column=0, rowspan=3, padx=(24, 16), pady=24)

    ctk.CTkLabel(shell, text=APP_NAME, font=ctk.CTkFont(size=30, weight="bold"),
                 text_color=T.TEXT_HEAD).grid(
        row=0, column=1, padx=(0, 24), pady=(26, 4), sticky="w"
    )
    ctk.CTkLabel(
        shell,
        text="Premium Messaging Workspace",
        text_color=T.ACCENT,
        font=ctk.CTkFont(size=13, weight="bold"),
    ).grid(row=1, column=1, padx=(0, 24), sticky="w")
    ctk.CTkLabel(
        shell,
        text="Preparing sessions, analytics, and campaign controls...",
        text_color=T.TEXT_MUTED,
    ).grid(row=2, column=1, padx=(0, 24), pady=(4, 10), sticky="w")

    progress = ctk.CTkProgressBar(shell, progress_color=T.SUCCESS)
    progress.grid(row=3, column=0, columnspan=2, padx=24, pady=(0, 12), sticky="ew")
    progress.set(0.78)

    ctk.CTkLabel(
        shell,
        text=f"Version {APP_VERSION}",
        text_color=T.TEXT_DIM,
    ).grid(row=4, column=0, columnspan=2, padx=24, pady=(0, 22), sticky="w")

    splash._logo_ref = logo
    _center_window(splash, 520, 220)

    def reveal_main_window() -> None:
        if splash.winfo_exists():
            splash.destroy()
        app.deiconify()
        app.lift()
        app.focus_force()

    app.after(1100, reveal_main_window)


def main():
    """Main application entry point."""
    try:
        Logger.info("=" * 50)
        Logger.info(f"{APP_NAME} v{APP_VERSION} Starting...")
        Logger.info("=" * 50)

        app = MainWindow()
        _configure_window_icon(app)
        app.withdraw()
        _show_startup_splash(app)
        app.mainloop()

        Logger.info(f"{APP_NAME} application closed")

    except Exception as e:
        Logger.critical(f"Fatal error: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
