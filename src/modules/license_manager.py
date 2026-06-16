"""
MessageCannon Pro - License Key System
Simple offline license validation.
Keys are: XXXX-XXXX-XXXX-XXXX (base32 encoded, HMAC-signed)
"""

import hashlib
import hmac
import base64
import json
import time
import os
import re
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox

# ── Your private secret — CHANGE THIS before shipping ─────────────────────────
_SECRET = b"MC_PRO_SECRET_FARAZ_2025_CHANGE_THIS"


class LicenseManager:
    """
    Generates and validates license keys.
    Store activated license in %APPDATA%/MessageCannon/license.json
    """

    STORAGE = Path(os.environ.get("APPDATA", Path.home())) / "MessageCannon" / "license.json"

    # ─── Key generation (seller side) ─────────────────────────────────────────

    @staticmethod
    def generate_key(email: str, tier: str = "single", days: int = 36500) -> str:
        """
        Generate a license key for a customer.
        Run this on your machine (or a small Flask server) when someone pays.
        tier: "single" | "5pack" | "enterprise"
        """
        payload = {
            "email": email.lower().strip(),
            "tier":  tier,
            "exp":   int(time.time()) + days * 86400,
        }
        payload_bytes = json.dumps(payload, sort_keys=True).encode()
        encoded       = base64.b32encode(payload_bytes).decode().rstrip("=")
        sig           = hmac.new(_SECRET, encoded.encode(), hashlib.sha256).hexdigest()[:8].upper()

        # Build readable key: PAYLOAD broken into 4-char chunks + SIG at end
        chunks = [encoded[i:i+4] for i in range(0, min(len(encoded), 12), 4)]
        chunks.append(sig[:4])
        return "-".join(chunks)

    # ─── Key validation (app side) ─────────────────────────────────────────────

    @staticmethod
    def validate_key(key: str) -> tuple[bool, str, dict]:
        """
        Returns (valid: bool, message: str, payload: dict)
        """
        key = key.strip().upper().replace(" ", "")
        parts = key.split("-")
        if len(parts) < 4:
            return False, "Invalid key format.", {}

        sig_given = parts[-1]
        encoded   = "".join(parts[:-1])

        # Verify signature
        expected_sig = hmac.new(
            _SECRET, encoded.encode(), hashlib.sha256).hexdigest()[:8].upper()[:4]

        if not hmac.compare_digest(sig_given[:4], expected_sig[:4]):
            return False, "Invalid license key.", {}

        # Decode payload
        try:
            padded  = encoded + "=" * (-len(encoded) % 8)
            payload = json.loads(base64.b32decode(padded).decode())
        except Exception:
            return False, "Corrupted key.", {}

        # Check expiry
        if payload.get("exp", 0) < time.time():
            return False, "License key has expired.", {}

        return True, "License valid ✅", payload

    # ─── Activation storage ────────────────────────────────────────────────────

    @classmethod
    def activate(cls, key: str) -> tuple[bool, str]:
        valid, msg, payload = cls.validate_key(key)
        if not valid:
            return False, msg
        cls.STORAGE.parent.mkdir(parents=True, exist_ok=True)
        with open(cls.STORAGE, "w") as f:
            json.dump({"key": key, "payload": payload}, f, indent=2)
        return True, f"Activated for {payload.get('email')} ({payload.get('tier')} license)"

    @classmethod
    def is_activated(cls) -> tuple[bool, dict]:
        if not cls.STORAGE.exists():
            return False, {}
        try:
            data = json.loads(cls.STORAGE.read_text())
            valid, _, payload = cls.validate_key(data.get("key", ""))
            return valid, payload
        except Exception:
            return False, {}

    @classmethod
    def deactivate(cls):
        if cls.STORAGE.exists():
            cls.STORAGE.unlink()


# ─── Activation Dialog ────────────────────────────────────────────────────────

class LicenseDialog(tk.Toplevel):
    """Show on startup if not activated. Blocks main window."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("MessageCannon Pro — Activate License")
        self.resizable(False, False)
        self.grab_set()                 # modal
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.result = False             # True if activated

        ttk.Label(self, text="MessageCannon Pro", font=("Arial", 18, "bold")).pack(pady=(24,4))
        ttk.Label(self, text="Enter your license key to continue",
                  foreground="gray").pack(pady=(0,16))

        frame = ttk.Frame(self, padding=20)
        frame.pack()

        ttk.Label(frame, text="License Key:").grid(row=0, column=0, sticky="w")
        self.key_var = tk.StringVar()
        key_entry = ttk.Entry(frame, textvariable=self.key_var, width=36,
                              font=("Courier New", 12))
        key_entry.grid(row=0, column=1, padx=(8,0))
        key_entry.focus()

        ttk.Label(frame, text="Email:").grid(row=1, column=0, sticky="w", pady=(8,0))
        self.email_var = tk.StringVar()
        ttk.Entry(frame, textvariable=self.email_var, width=36).grid(
            row=1, column=1, padx=(8,0), pady=(8,0))

        self.msg_label = ttk.Label(self, text="", foreground="red")
        self.msg_label.pack()

        btn_row = ttk.Frame(self, padding=(0,0,0,16))
        btn_row.pack()
        ttk.Button(btn_row, text="Activate", command=self._activate, width=16).pack(
            side="left", padx=4)
        ttk.Button(btn_row, text="Buy License ($89)",
                   command=self._buy).pack(side="left", padx=4)

        ttk.Label(self, text="Contact: farazgoal@gmail.com",
                  font=("Arial", 9), foreground="gray").pack(pady=(0,12))

        self.center()

    def center(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw   = self.winfo_screenwidth()
        sh   = self.winfo_screenheight()
        self.geometry(f"+{(sw-w)//2}+{(sh-h)//2}")

    def _activate(self):
        key = self.key_var.get().strip()
        if not key:
            self.msg_label.config(text="Please enter a license key.")
            return
        ok, msg = LicenseManager.activate(key)
        if ok:
            messagebox.showinfo("Activated!", msg, parent=self)
            self.result = True
            self.destroy()
        else:
            self.msg_label.config(text=msg)

    def _buy(self):
        import webbrowser
        webbrowser.open("https://muhammad-faraz-dev.netlify.app")

    def _on_close(self):
        if messagebox.askyesno("Quit", "No license — exit MessageCannon Pro?",
                               parent=self):
            self.master.destroy()


def require_license(root: tk.Tk) -> bool:
    """
    Call at app startup.
    Returns True if license is valid, shows dialog if not.
    """
    activated, payload = LicenseManager.is_activated()
    if activated:
        return True

    dialog = LicenseDialog(root)
    root.wait_window(dialog)
    return dialog.result
