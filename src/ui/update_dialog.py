"""Update-available dialog, shown from the sidebar update badge.

No third-party dependency, same pattern as confirm_dialogs.py/send_dialogs.py.
Download + silent-install is Windows-only (see core/update_checker.py's
can_silent_install() docstring for why) — other platforms always fall back to
"View on GitHub" with no loss of function, just no one-click apply.
"""

from __future__ import annotations

import threading
import webbrowser

import customtkinter as ctk

from . import theme as T
from .toast import show_toast
from .window_utils import center_on_parent
from ..core.update_checker import UpdateInfo, can_silent_install, download_asset


class UpdateDialog(ctk.CTkToplevel):
    def __init__(self, main_window, info: UpdateInfo, current_version: str):
        super().__init__(main_window)
        self.main_window = main_window
        self.info = info
        self.title("Update available")
        # Item 29 follow-up (2026-07-28) real visual pass: the previous
        # layout stretched a CTkTextbox to fill all leftover vertical space
        # (grid_rowconfigure(1, weight=1)) -- with typically short real
        # release notes, that read as a large, mostly-empty grey rectangle,
        # which is exactly what looked like a generic system dialog rather
        # than a premium one. Notes box is now a fixed, content-sized height
        # instead of stretch-filling, and the dialog height was recomputed
        # to match (no leftover dead space below the footer either).
        center_on_parent(self, 500, 420, main_window)
        self.resizable(False, False)
        self.transient(main_window)
        self.grab_set()
        self.configure(fg_color=T.BG_MAIN)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        self.bind("<Escape>", lambda _e: self.destroy())

        self.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(self, text=f"⬆  MessageCannon Pro {info.tag} is available",
                     font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=T.TEXT_HEAD, wraplength=456, justify="left"
                     ).grid(row=0, column=0, padx=22, pady=(20, 10), sticky="w")

        # Two-cell "stats" card -- same visual language as
        # SendConfirmationDialog's recipients/delay/ETA strip (the
        # established pattern for "key facts at a glance" inside a dialog)
        # instead of the previous two bare, differently-weighted labels.
        version_card = ctk.CTkFrame(self, fg_color=T.BG_SURFACE, corner_radius=12,
                                     border_width=1, border_color=T.BG_BORDER)
        version_card.grid(row=1, column=0, padx=22, pady=(0, 14), sticky="ew")
        version_card.grid_columnconfigure((0, 1), weight=1, uniform="verinfo")
        for col, (label, value) in enumerate([
            ("Installed", f"v{current_version}"),
            ("Available", info.tag),
        ]):
            cell = ctk.CTkFrame(version_card, fg_color="transparent")
            cell.grid(row=0, column=col, padx=16, pady=14, sticky="w")
            ctk.CTkLabel(cell, text=label, text_color=T.TEXT_MUTED,
                         font=ctk.CTkFont(size=11)).pack(anchor="w")
            ctk.CTkLabel(cell, text=value, text_color=T.TEXT_HEAD,
                         font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w")

        ctk.CTkLabel(self, text="Release notes", text_color=T.TEXT_HEAD,
                     font=ctk.CTkFont(size=12, weight="bold")).grid(
            row=2, column=0, padx=22, pady=(0, 4), sticky="w")
        notes_box = ctk.CTkTextbox(self, fg_color=T.BG_INNER, text_color=T.TEXT_MUTED,
                                    border_width=1, border_color=T.BG_BORDER,
                                    corner_radius=10, wrap="word", height=120,
                                    font=ctk.CTkFont(size=12))
        notes_box.grid(row=3, column=0, padx=22, pady=(0, 14), sticky="ew")
        notes_box.insert("1.0", info.release_notes or "No release notes provided.")
        notes_box.configure(state="disabled")

        self._status_var = ctk.StringVar(value="")
        ctk.CTkLabel(self, textvariable=self._status_var, text_color=T.TEXT_MUTED,
                     font=ctk.CTkFont(size=11), wraplength=456, justify="left"
                     ).grid(row=4, column=0, padx=22, pady=(0, 4), sticky="w")

        self._progress = ctk.CTkProgressBar(self, progress_color=T.ACCENT)
        self._progress.set(0)
        self._progress.grid(row=5, column=0, padx=22, pady=(0, 10), sticky="ew")
        self._progress.grid_remove()

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=6, column=0, padx=22, pady=(0, 20), sticky="ew")
        footer.grid_columnconfigure(0, weight=1)

        # Item 27 button-hierarchy pass: three real tiers instead of two
        # identically-styled BADGE_BG buttons sitting next to a primary one.
        # "Later" is the least important action (pure dismiss) -> a ghost/
        # ext-link style, transparent until hovered. "View on GitHub" is a
        # real but secondary action (a fallback, per Item 3's own framing,
        # never the primary/expected path) -> the outline-secondary style
        # already established by History's "Duplicate" button and Compose's
        # Pause/Resume (fg_color=BG_INNER + a real border + ACCENT_TEXT,
        # which measures real WCAG-passing contrast against BG_INNER/
        # BG_SURFACE, unlike plain T.ACCENT as text_color). "Download &
        # Install" stays the one filled ACCENT primary action -- unchanged,
        # it was already correct.
        ctk.CTkButton(footer, text="Later", width=80, fg_color="transparent",
                      hover_color=T.BADGE_BG, text_color=T.TEXT_MUTED,
                      command=self.destroy).grid(row=0, column=0, sticky="w")

        ctk.CTkButton(footer, text="View on GitHub", width=150,
                      fg_color=T.BG_INNER, hover_color=T.BG_BORDER,
                      border_width=1, border_color=T.BG_BORDER,
                      text_color=T.ACCENT_TEXT,
                      command=lambda: webbrowser.open(info.release_url)
                      ).grid(row=0, column=1, sticky="e", padx=(0, 8))

        # CTkButton's built-in disabled state only dims text_color, not
        # fg_color (confirmed by reading ctk_button.py) — an accent-fg button
        # left disabled would still look fully clickable. Pick muted colors
        # up front for the no-asset-available case instead of relying on
        # CTk's disabled look to communicate it.
        can_install_here = bool(info.asset_url) and can_silent_install()
        self._install_btn = ctk.CTkButton(
            footer, text="Download & Install", height=38, corner_radius=8,
            fg_color=T.ACCENT if can_install_here else T.NAV_INACTIVE,
            hover_color=T.ACCENT_HOVER if can_install_here else T.NAV_INACTIVE,
            text_color=T.TEXT_HEAD if can_install_here else T.TEXT_MUTED,
            font=ctk.CTkFont(size=13, weight="bold"),
            command=self._start_download,
        )
        self._install_btn.grid(row=0, column=2, sticky="e")

        if not can_install_here:
            self._install_btn.configure(state="disabled")
            reason = ("No Windows installer is attached to this release yet."
                      if not info.asset_url else
                      "One-click install is only available on Windows — use "
                      "\"View on GitHub\" to download for this platform.")
            self._status_var.set(reason)

    def _start_download(self) -> None:
        self._install_btn.configure(state="disabled")
        self._progress.grid()
        self._status_var.set(f"Downloading {self.info.asset_name}...")

        def on_progress(frac: float) -> None:
            self.after(0, lambda: self._progress.set(frac))

        def worker() -> None:
            try:
                path = download_asset(self.info.asset_url, self.info.asset_name, on_progress)
            except Exception as exc:
                # `exc` is deleted by Python at the end of the `except` block
                # even though this lambda closes over it -- self.after()
                # always defers to the next Tk idle tick, which runs after
                # that deletion, so referencing `exc` there raises a NameError
                # that Tk's callback handler silently swallows (prints to
                # stderr, never shown to the user). Same bug Item 3 of the
                # Live Testing Findings pass fixed at 10 other call sites;
                # this file predates that sweep and was missed. Capture the
                # message into a plain variable first instead.
                message = str(exc)
                self.after(0, lambda: self._on_download_failed(message))
                return
            self.after(0, lambda: self._on_download_succeeded(path))

        threading.Thread(target=worker, daemon=True).start()

    def _on_download_failed(self, message: str) -> None:
        self._status_var.set("Download failed — you can try again or use \"View on GitHub\".")
        self._install_btn.configure(state="normal")
        self._progress.grid_remove()
        show_toast(self.main_window, f"Update download failed: {message}", kind="error")

    def _on_download_succeeded(self, installer_path: str) -> None:
        # Accurate, not aspirational: the installer runs /VERYSILENT, which
        # skips Inno Setup's own post-install "launch app" step (setup.iss's
        # [Run] entry has Flags: skipifsilent) — MessageCannon does not
        # relaunch itself. Closing now is a real, necessary step (Inno Setup
        # can't overwrite the running .exe otherwise), but the user has to
        # reopen the app by hand once the install finishes in the background.
        self._status_var.set("Downloaded. Closing MessageCannon to install — reopen it afterward.")
        self.main_window.after(600, lambda: self.main_window._apply_downloaded_update(installer_path))
        self.destroy()


def show_update_dialog(main_window, info: UpdateInfo, current_version: str) -> None:
    UpdateDialog(main_window, info, current_version)
