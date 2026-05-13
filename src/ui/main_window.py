"""
Main application window for MessageCannon.
"""

import customtkinter as ctk
from typing import Optional, Callable
import threading
import os
import sys
import time
from tkinter import filedialog, messagebox
from pathlib import Path




def _ensure_tcl_tk_paths() -> None:
    """Set Tcl/Tk env vars early so direct UI imports work on Windows."""
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
from ..core.contact_manager import ContactManager
from ..core.message_processor import MessageProcessor
from ..core.whatsapp_sender import WhatsAppSender
from ..core.export_manager import ExportManager
from ..database.db_manager import DatabaseManager
from ..utils.logger import Logger
from ..utils.constants import (
    APP_NAME, APP_VERSION,
    WINDOW_WIDTH, WINDOW_HEIGHT,
    COLOR_PRIMARY, COLOR_SECONDARY, COLOR_ACCENT,
    COLOR_DARK_BG, COLOR_LIGHT_BG,
    COLOR_DARK_TEXT, COLOR_LIGHT_TEXT,
    COLOR_WARNING, COLOR_SUCCESS
)
from ..utils.helpers import is_first_launch, mark_first_launch_complete
from ..utils.license_manager import LicenseManager


class MainWindow(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        """Initialize main window."""
        super().__init__()
        
        # Configuration
        self.title(f"{APP_NAME} v{APP_VERSION}")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.resizable(True, True)
        self.minsize(1024, 720)
        self._setup_window_branding()
        
        # Set theme
        self._load_theme()
        
        # Initialize managers
        self.contact_manager = ContactManager()
        self.message_processor = MessageProcessor()
        self.whatsapp_sender = WhatsAppSender()
        self.export_manager = ExportManager()
        self.db = DatabaseManager()
        
        # Check license
        self._check_license()
        
        # Create UI
        self._create_ui()
        self.campaign_running = False
        self._refresh_workflow_state()
        self.update_idletasks()
        self._center_window()
        self._startup_recover_until = time.monotonic() + 8
        self._ensure_window_visible()
        self.after(350, self._ensure_window_visible)
        self.after(1100, self._ensure_window_visible)
        self.bind("<Unmap>", self._on_window_unmap)

    def _ensure_window_visible(self) -> None:
        """Force a stable visible state after startup/layout completes."""
        try:
            self.deiconify()
            self.state("normal")
            self.lift()
            self.focus_set()
            self.attributes("-topmost", True)
            self.after(120, lambda: self.attributes("-topmost", False))
        except Exception:
            Logger.warning("Could not fully enforce startup window visibility")

    def _on_window_unmap(self, event=None) -> None:
        """Recover from unexpected startup minimization/hide race conditions."""
        if event is not None and event.widget is not self:
            return

        if time.monotonic() > self._startup_recover_until:
            return

        try:
            if self.state() == "iconic":
                self.after(160, self._ensure_window_visible)
        except Exception:
            Logger.warning("Window unmap recovery check failed")

    def _setup_window_branding(self) -> None:
        """Apply app icon and startup window defaults."""
        icon_path = Path(__file__).resolve().parents[1] / "assets" / "icons" / "app.ico"
        if icon_path.exists():
            try:
                self.iconbitmap(str(icon_path))
            except Exception:
                Logger.warning(f"Unable to set window icon: {icon_path}")

    def _load_theme(self) -> None:
        """Load the polished dark theme as the default app appearance."""
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

    def _center_window(self) -> None:
        """Center the window on screen."""
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x_offset = (screen_width - WINDOW_WIDTH) // 2
        y_offset = max((screen_height - WINDOW_HEIGHT) // 2 - 20, 0)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}+{x_offset}+{y_offset}")
    
    def _check_license(self) -> None:
        """Check application license."""
        license_info = LicenseManager.check_license()
        
        self.license_status = license_info['status']
        self.is_trial = license_info['is_trial']
        self.days_remaining = license_info['days_remaining']
        
        Logger.info(f"License status: {self.license_status}")
    
    def _show_first_launch_warning(self) -> None:
        """Show first launch warning about WhatsApp compliance."""
        from customtkinter import CTkToplevel
        
        dialog = CTkToplevel(self)
        dialog.title("Important: WhatsApp Compliance")
        dialog.geometry("500x400")
        dialog.resizable(False, False)
        
        # Center dialog
        dialog.transient(self)
        dialog.update_idletasks()
        screen_width = dialog.winfo_screenwidth()
        screen_height = dialog.winfo_screenheight()
        dialog_width = 500
        dialog_height = 400
        x_offset = (screen_width - dialog_width) // 2
        y_offset = (screen_height - dialog_height) // 2
        dialog.geometry(f"{dialog_width}x{dialog_height}+{x_offset}+{max(y_offset, 0)}")
        dialog.lift()
        dialog.attributes("-topmost", True)
        dialog.after(600, lambda: dialog.attributes("-topmost", False))
        dialog.protocol("WM_DELETE_WINDOW", lambda: (mark_first_launch_complete(), dialog.destroy()))
        
        # Title
        title = ctk.CTkLabel(
            dialog,
            text="⚠️ WhatsApp Compliance & Legal Notice",
            font=("Arial", 16, "bold"),
            text_color=COLOR_WARNING
        )
        title.pack(pady=20, padx=20)
        
        # Message
        message = ctk.CTkTextbox(
            dialog,
            width=450,
            height=280,
            state="normal"
        )
        message.pack(pady=10, padx=20, fill="both", expand=True)
        
        compliance_text = """MessageCannon is a legitimate business communication tool.

✓ You MUST have explicit recipient consent before sending messages
✓ Do NOT use this tool for spam or unsolicited messages
✓ Comply with local telemarketing and privacy laws
✓ Use built-in safety features (delays, limits, etc.)
✓ WhatsApp may block accounts that violate their terms

BY USING THIS APPLICATION, YOU AGREE:
- You have obtained proper consent from all recipients
- You will not use this for spamming or illegal purposes
- You accept full responsibility for your use of WhatsApp
- You understand WhatsApp may block your account if abused

This tool is designed for legitimate business needs:
• Tiffin services
• Real estate notifications
• Educational reminders
• Medical appointment reminders
• Customer service updates

Any violations of WhatsApp's terms are your responsibility."""
        
        message.insert("1.0", compliance_text)
        message.configure(state="disabled")
        
        # Agree button
        def on_agree():
            mark_first_launch_complete()
            dialog.destroy()
        
        agree_btn = ctk.CTkButton(
            dialog,
            text="I Understand & Agree",
            command=on_agree,
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SECONDARY
        )
        agree_btn.pack(pady=15)
    
    def _create_ui(self) -> None:
        """Create main UI layout."""
        # Configure grid
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)
        
        # Top Navigation Bar
        self._create_navigation_bar()
        
        # Main Content Frame (3-column layout)
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.grid(row=1, column=0, sticky="nsew", padx=12, pady=(10, 8))
        main_frame.grid_rowconfigure(0, weight=1)
        
        # Left Panel
        main_frame.grid_columnconfigure(0, weight=3, uniform="content")
        left_panel = ctk.CTkFrame(
            main_frame,
            fg_color=COLOR_DARK_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_PRIMARY
        )
        left_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6))
        self._create_left_panel(left_panel)
        
        # Center Panel
        main_frame.grid_columnconfigure(1, weight=5, uniform="content")
        center_panel = ctk.CTkFrame(
            main_frame,
            fg_color=COLOR_DARK_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_PRIMARY
        )
        center_panel.grid(row=0, column=1, sticky="nsew", padx=6)
        self._create_center_panel(center_panel)
        
        # Right Panel
        main_frame.grid_columnconfigure(2, weight=3, uniform="content")
        right_panel = ctk.CTkFrame(
            main_frame,
            fg_color=COLOR_DARK_BG,
            corner_radius=12,
            border_width=1,
            border_color=COLOR_PRIMARY
        )
        right_panel.grid(row=0, column=2, sticky="nsew", padx=(6, 0))
        self._create_right_panel(right_panel)
        
        # Status Bar
        self._create_status_bar()
    
    def _create_navigation_bar(self) -> None:
        """Create top navigation bar."""
        nav_frame = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, height=50)
        nav_frame.grid(row=0, column=0, sticky="ew")
        nav_frame.grid_propagate(False)
        
        # App Title
        title_label = ctk.CTkLabel(
            nav_frame,
            text=f"📁 {APP_NAME}",
            font=("Segoe UI", 18, "bold"),
            text_color=COLOR_DARK_TEXT
        )
        title_label.pack(side="left", padx=20, pady=10)

        subtitle_label = ctk.CTkLabel(
            nav_frame,
            text="Offline-first bulk WhatsApp campaigns",
            font=("Segoe UI", 10),
            text_color=COLOR_DARK_TEXT
        )
        subtitle_label.pack(side="left", padx=(0, 14), pady=10)
        
        # Menu buttons
        menu_actions = [
            ("📁 File", self._on_menu_file),
            ("📋 Rules", self._on_menu_rules),
            ("⚙️ Settings", self._on_menu_settings),
            ("🆘 Help", self._on_menu_help),
        ]
        for menu_item, action in menu_actions:
            btn = ctk.CTkButton(
                nav_frame,
                text=menu_item,
                width=96,
                height=30,
                fg_color=COLOR_SECONDARY,
                hover_color=COLOR_ACCENT,
                text_color=COLOR_DARK_TEXT,
                text_color_disabled="#D7E3DE",
                font=("Segoe UI", 10, "bold"),
                corner_radius=8,
                command=action
            )
            btn.pack(side="left", padx=5, pady=10)
    
    def _create_left_panel(self, parent: ctk.CTkFrame) -> None:
        """Create left panel (Contact Management)."""
        # Title
        title = ctk.CTkLabel(
            parent,
            text="📥 Contacts",
            font=("Segoe UI", 14, "bold"),
            text_color=COLOR_ACCENT
        )
        title.pack(pady=(14, 8), padx=14)

        card_text = ctk.CTkLabel(
            parent,
            text="Import, validate, tag, and review your recipient list before sending.",
            font=("Segoe UI", 9),
            text_color=COLOR_LIGHT_TEXT,
            wraplength=280,
            justify="left"
        )
        card_text.pack(pady=(0, 10), padx=14, anchor="w")
        
        # Buttons
        buttons_frame = ctk.CTkFrame(parent, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=14, pady=6)
        
        import_btn = ctk.CTkButton(
            buttons_frame,
            text="📂 Import",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_SECONDARY,
            text_color=COLOR_DARK_TEXT,
            text_color_disabled="#D7E3DE",
            height=34,
            corner_radius=8,
            font=("Segoe UI", 11, "bold"),
            command=self._on_import_contacts
        )
        import_btn.pack(fill="x", pady=3)
        
        export_btn = ctk.CTkButton(
            buttons_frame,
            text="📤 Export",
            fg_color=COLOR_SECONDARY,
            hover_color=COLOR_SECONDARY,
            text_color=COLOR_DARK_TEXT,
            text_color_disabled="#D7E3DE",
            height=34,
            corner_radius=8,
            font=("Segoe UI", 11, "bold"),
            command=self._on_export_contacts
        )
        export_btn.pack(fill="x", pady=3)
        
        # Contact list preview
        list_label = ctk.CTkLabel(
            parent,
            text="Recent Contacts",
            font=("Arial", 10, "bold"),
            text_color=COLOR_LIGHT_TEXT
        )
        list_label.pack(pady=(12, 6), padx=14)
        
        # Contact list box
        contacts = self.contact_manager.get_contacts_paginated(page=1, page_size=10)
        
        self.contacts_list_frame = ctk.CTkScrollableFrame(parent, fg_color="transparent")
        self.contacts_list_frame.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        self._populate_contacts_preview(contacts)
    
    def _create_center_panel(self, parent: ctk.CTkFrame) -> None:
        """Create center panel (Message Composer)."""
        # Title
        title = ctk.CTkLabel(
            parent,
            text="✏️ Compose Message",
            font=("Segoe UI", 14, "bold"),
            text_color=COLOR_ACCENT
        )
        title.pack(pady=(14, 8), padx=14)

        description = ctk.CTkLabel(
            parent,
            text="Use templates or write a custom message with variables like {name} and {amount}.",
            font=("Segoe UI", 9),
            text_color=COLOR_LIGHT_TEXT,
            wraplength=450,
            justify="left"
        )
        description.pack(pady=(0, 10), padx=14, anchor="w")
        
        # Template selector
        template_frame = ctk.CTkFrame(parent, fg_color="transparent")
        template_frame.pack(fill="x", padx=14, pady=6)
        
        template_label = ctk.CTkLabel(
            template_frame,
            text="Template:",
            font=("Segoe UI", 10),
            text_color=COLOR_DARK_TEXT
        )
        template_label.pack(side="left", padx=5)
        
        templates = ["Custom", "Fee Reminder", "Appointment", "Promotional"]
        template_combo = ctk.CTkComboBox(
            template_frame,
            values=templates,
            command=self._on_template_selected,
            width=200
        )
        template_combo.pack(side="left", padx=5, fill="x", expand=True)
        template_combo.set("Custom")
        
        # Message textarea
        message_label = ctk.CTkLabel(
            parent,
            text="Message Text:",
            font=("Segoe UI", 10),
            text_color=COLOR_DARK_TEXT
        )
        message_label.pack(pady=(12, 4), padx=14, anchor="w")
        
        self.message_textbox = ctk.CTkTextbox(
            parent,
            height=150,
            fg_color=COLOR_DARK_BG,
            text_color=COLOR_DARK_TEXT
        )
        self.message_textbox.pack(fill="both", expand=True, padx=14, pady=6)
        
        # Character counter
        char_frame = ctk.CTkFrame(parent, fg_color="transparent")
        char_frame.pack(fill="x", padx=14, pady=4)
        
        self.char_label = ctk.CTkLabel(
            char_frame,
            text="Characters: 0/65536",
            font=("Segoe UI", 9),
            text_color=COLOR_LIGHT_TEXT
        )
        self.char_label.pack(anchor="e")
        
        # Bind text changes
        self.message_textbox.bind("<KeyRelease>", self._on_message_changed)
        
        # Action buttons
        action_frame = ctk.CTkFrame(parent, fg_color="transparent")
        action_frame.pack(fill="x", padx=14, pady=(10, 14))
        
        preview_btn = ctk.CTkButton(
            action_frame,
            text="👁️ Preview",
            fg_color=COLOR_SECONDARY,
            hover_color=COLOR_PRIMARY,
            text_color=COLOR_DARK_TEXT,
            text_color_disabled="#D7E3DE",
            height=36,
            width=110,
            corner_radius=8,
            font=("Segoe UI", 11, "bold"),
            command=self._on_preview_messages
        )
        preview_btn.pack(side="left", padx=3)
        
        self.send_btn = ctk.CTkButton(
            action_frame,
            text="🚀 Send Campaign",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_ACCENT,
            text_color=COLOR_DARK_TEXT,
            text_color_disabled="#153429",
            height=36,
            width=170,
            corner_radius=8,
            font=("Segoe UI", 11, "bold"),
            command=self._on_send_campaign
        )
        self.send_btn.pack(side="right", padx=3)
    
    def _create_right_panel(self, parent: ctk.CTkFrame) -> None:
        """Create right panel (Sending Controls & Log)."""
        # Title
        title = ctk.CTkLabel(
            parent,
            text="⚙️ Controls",
            font=("Segoe UI", 14, "bold"),
            text_color=COLOR_ACCENT
        )
        title.pack(pady=(14, 8), padx=14)

        controls_description = ctk.CTkLabel(
            parent,
            text="Tune the sending rhythm, enforce consent, and monitor campaign delivery in real time.",
            font=("Segoe UI", 9),
            text_color=COLOR_LIGHT_TEXT,
            wraplength=260,
            justify="left"
        )
        controls_description.pack(pady=(0, 10), padx=14, anchor="w")
        
        # Delay settings
        delay_frame = ctk.CTkFrame(parent, fg_color="transparent")
        delay_frame.pack(fill="x", padx=14, pady=6)
        
        delay_label = ctk.CTkLabel(
            delay_frame,
            text="Message Delay (sec):",
            font=("Segoe UI", 9),
            text_color=COLOR_DARK_TEXT
        )
        delay_label.pack(anchor="w")
        
        self.delay_slider = ctk.CTkSlider(
            delay_frame,
            from_=10,
            to=60,
            number_of_steps=50,
            command=self._on_delay_changed
        )
        self.delay_slider.set(30)
        self.delay_slider.pack(fill="x", pady=3)
        
        self.delay_value_label = ctk.CTkLabel(
            delay_frame,
            text="30 seconds",
            font=("Segoe UI", 9),
            text_color=COLOR_LIGHT_TEXT
        )
        self.delay_value_label.pack(anchor="e")
        
        # Jitter toggle
        self.jitter_var = ctk.BooleanVar(value=True)
        jitter_check = ctk.CTkCheckBox(
            parent,
            text="🎲 Random Jitter (±5s)",
            variable=self.jitter_var,
            text_color=COLOR_DARK_TEXT
        )
        jitter_check.pack(padx=14, pady=(6, 4), anchor="w")
        
        # Consent checkbox
        self.consent_var = ctk.BooleanVar(value=False)
        consent_check = ctk.CTkCheckBox(
            parent,
            text="✓ Recipient Consent",
            variable=self.consent_var,
            command=self._on_consent_changed,
            text_color=COLOR_DARK_TEXT,
            checkbox_width=20,
            checkbox_height=20
        )
        consent_check.pack(padx=14, pady=4, anchor="w")
        
        # Control buttons
        control_frame = ctk.CTkFrame(parent, fg_color="transparent")
        control_frame.pack(fill="x", padx=14, pady=10)
        
        self.start_btn = ctk.CTkButton(
            control_frame,
            text="▶️ Start",
            fg_color=COLOR_SUCCESS,
            hover_color=COLOR_SECONDARY,
            text_color=COLOR_DARK_TEXT,
            text_color_disabled="#153429",
            height=34,
            width=88,
            corner_radius=8,
            font=("Segoe UI", 10, "bold"),
            command=self._on_start_send
        )
        self.start_btn.pack(side="left", padx=3)
        
        self.pause_btn = ctk.CTkButton(
            control_frame,
            text="⏸️ Pause",
            fg_color=COLOR_ACCENT,
            hover_color=COLOR_SECONDARY,
            text_color=COLOR_DARK_TEXT,
            text_color_disabled="#153429",
            height=34,
            width=88,
            corner_radius=8,
            font=("Segoe UI", 10, "bold"),
            command=self._on_pause_send
        )
        self.pause_btn.pack(side="left", padx=3)
        
        self.stop_btn = ctk.CTkButton(
            control_frame,
            text="⏹️ Stop",
            fg_color=COLOR_WARNING,
            hover_color=COLOR_SECONDARY,
            text_color=COLOR_DARK_TEXT,
            text_color_disabled="#4A1F1F",
            height=34,
            width=88,
            corner_radius=8,
            font=("Segoe UI", 10, "bold"),
            command=self._on_stop_send
        )
        self.stop_btn.pack(side="left", padx=3)
        
        # Progress
        progress_label = ctk.CTkLabel(
            parent,
            text="📊 Progress",
            font=("Segoe UI", 10, "bold"),
            text_color=COLOR_ACCENT
        )
        progress_label.pack(pady=(12, 6), padx=14, anchor="w")
        
        self.progress_bar = ctk.CTkProgressBar(parent, fg_color=COLOR_ACCENT)
        self.progress_bar.pack(fill="x", padx=14, pady=4)
        self.progress_bar.set(0)
        
        self.progress_label = ctk.CTkLabel(
            parent,
            text="Ready",
            font=("Segoe UI", 9),
            text_color=COLOR_LIGHT_TEXT
        )
        self.progress_label.pack(padx=14, anchor="w")
        
        # Status indicators
        status_frame = ctk.CTkFrame(parent, fg_color="transparent")
        status_frame.pack(fill="x", padx=14, pady=(10, 14))
        
        self.status_sent = ctk.CTkLabel(
            status_frame,
            text="✓ Sent: 0",
            font=("Segoe UI", 9),
            text_color=COLOR_SUCCESS
        )
        self.status_sent.pack(side="left", padx=5)
        
        self.status_failed = ctk.CTkLabel(
            status_frame,
            text="✗ Failed: 0",
            font=("Segoe UI", 9),
            text_color=COLOR_WARNING
        )
        self.status_failed.pack(side="left", padx=5)
    
    def _create_status_bar(self) -> None:
        """Create bottom status bar."""
        status_frame = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, height=30)
        status_frame.grid(row=2, column=0, sticky="ew")
        status_frame.grid_propagate(False)
        
        # Left status
        self.left_status = ctk.CTkLabel(
            status_frame,
            text="🟢 Ready",
            font=("Segoe UI", 9),
            text_color=COLOR_DARK_TEXT
        )
        self.left_status.pack(side="left", padx=10)
        
        # Center status
        self.center_status = ctk.CTkLabel(
            status_frame,
            text="Contacts: 0 | Messages: 0",
            font=("Segoe UI", 9),
            text_color=COLOR_DARK_TEXT
        )
        self.center_status.pack(side="left", expand=True)
        
        # Right status
        self.right_status = ctk.CTkLabel(
            status_frame,
            text="WhatsApp: 🔴 Disconnected",
            font=("Segoe UI", 9),
            text_color=COLOR_DARK_TEXT
        )
        self.right_status.pack(side="right", padx=10)

    def _populate_contacts_preview(self, contacts) -> None:
        """Refresh the left-panel contact preview list."""
        for widget in self.contacts_list_frame.winfo_children():
            widget.destroy()

        if contacts:
            for contact in contacts:
                contact_label = ctk.CTkLabel(
                    self.contacts_list_frame,
                    text=f"{contact.name}\n{contact.phone}",
                    font=("Segoe UI", 9),
                    text_color=COLOR_DARK_TEXT,
                    justify="left"
                )
                contact_label.pack(fill="x", pady=3, padx=5)
        else:
            empty_label = ctk.CTkLabel(
                self.contacts_list_frame,
                text="No contacts imported yet",
                text_color=COLOR_LIGHT_TEXT,
                font=("Segoe UI", 9)
            )
            empty_label.pack(pady=20)

    def _read_local_doc(self, relative_path: str) -> Optional[str]:
        """Read local documentation text from source or packaged paths."""
        candidates = [Path(__file__).resolve().parents[2] / relative_path]

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            candidates.insert(0, Path(meipass) / relative_path)

        for doc_path in candidates:
            if doc_path.exists():
                try:
                    return doc_path.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue

        return None

    def _show_text_dialog(self, title: str, body: str) -> None:
        """Show read-only text in an app dialog as a fallback."""
        dialog = ctk.CTkToplevel(self)
        dialog.title(title)
        dialog.geometry("760x520")
        dialog.transient(self)

        heading = ctk.CTkLabel(
            dialog,
            text=title,
            font=("Segoe UI", 14, "bold"),
            text_color=COLOR_ACCENT
        )
        heading.pack(pady=(12, 6), padx=14, anchor="w")

        text_box = ctk.CTkTextbox(dialog, fg_color=COLOR_DARK_BG, text_color=COLOR_DARK_TEXT)
        text_box.pack(fill="both", expand=True, padx=14, pady=(4, 12))
        text_box.insert("1.0", body)
        text_box.configure(state="disabled")

    def _on_menu_file(self) -> None:
        """Handle File menu click."""
        self._on_import_contacts()

    def _on_menu_rules(self) -> None:
        """Handle Rules menu click."""
        rules_text = self._read_local_doc("docs/whatsapp_guidelines.md")
        if not rules_text:
            rules_text = (
                "1. Only send to users with consent.\n"
                "2. Avoid bulk spam and repeated unsolicited messaging.\n"
                "3. Keep delay/jitter enabled for safer sending behavior.\n"
                "4. Respect local privacy and telecom laws.\n"
                "5. Stop campaigns immediately if users opt out.\n"
            )
        self._show_text_dialog("WhatsApp Rules", rules_text)
        self._set_status("📋 WhatsApp rules opened")

    def _on_menu_settings(self) -> None:
        """Handle Settings menu click."""
        self._center_window()
        self._set_status("⚙️ Window recentered")
        messagebox.showinfo("Settings", "Window position reset and workflow refreshed.")
        self._refresh_workflow_state()

    def _on_menu_help(self) -> None:
        """Handle Help menu click."""
        help_text = self._read_local_doc("docs/user_guide.md") or self._read_local_doc("README.md")
        if not help_text:
            help_text = (
                "MessageCannon Quick Help\n\n"
                "- File: Import contacts (CSV/XLSX).\n"
                "- Rules: Compliance guidelines.\n"
                "- Compose Message: Write template with variables like {name}.\n"
                "- Preview: See processed messages before send.\n"
                "- Send Campaign: Requires contacts, message, and consent.\n"
            )
        self._show_text_dialog("Help", help_text)
        self._set_status("🆘 Help opened")

    def _set_status(self, message: str) -> None:
        """Update primary status text in controls panel and footer."""
        self.progress_label.configure(text=message)
        self.left_status.configure(text=message)

    def _refresh_workflow_state(self) -> None:
        """Drive button enablement and status from current workflow state."""
        contacts = self.contact_manager.get_all_contacts()
        contact_count = len(contacts)
        message = self.message_textbox.get("1.0", "end").strip()
        has_message = len(message) > 0
        consent_given = self.consent_var.get()

        self.center_status.configure(text=f"Contacts: {contact_count} | Message: {'Ready' if has_message else 'Draft'}")

        # Keep controls interactive so users get immediate feedback on click.
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")

        if contact_count == 0:
            self.send_btn.configure(state="normal")
            self._set_status("⚠️ Import contacts to continue")
            return

        if not has_message:
            self.send_btn.configure(state="normal")
            self._set_status("✍️ Compose your message")
            return

        if not consent_given:
            self.send_btn.configure(state="normal")
            self._set_status("☑️ Confirm recipient consent")
            return

        self.send_btn.configure(state="normal")
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="normal")
        self.stop_btn.configure(state="normal")
        self._set_status("🟢 Campaign ready")
    
    # Event Handlers
    def _on_import_contacts(self) -> None:
        """Handle import contacts button."""
        file_path = filedialog.askopenfilename(
            title="Import Contacts",
            filetypes=[("Data Files", "*.csv *.xlsx *.xls"), ("All Files", "*.*")]
        )
        if not file_path:
            self._set_status("Import cancelled")
            return

        count, errors = self.contact_manager.import_from_file(file_path)
        self._populate_contacts_preview(self.contact_manager.get_contacts_paginated(page=1, page_size=10))

        if count > 0:
            self._set_status(f"✅ Imported {count} contacts")
            Logger.info(f"Imported {count} contacts")
            if errors:
                messagebox.showwarning(
                    "Import Completed With Warnings",
                    f"Imported: {count}\nSkipped rows: {len(errors)}\n\nFirst issues:\n" + "\n".join(errors[:5])
                )
            else:
                messagebox.showinfo("Import Successful", f"Imported {count} contacts successfully.")
        else:
            self._set_status("❌ Import failed")
            messagebox.showerror(
                "Import Failed",
                "No contacts imported.\n\n" + "\n".join(errors[:8]) if errors else "No valid contacts found."
            )
        self._refresh_workflow_state()
    
    def _on_export_contacts(self) -> None:
        """Handle export contacts button."""
        contacts = self.contact_manager.get_all_contacts()
        if not contacts:
            self._set_status("⚠️ No contacts to export")
            messagebox.showwarning("Export", "No contacts available to export.")
            self._refresh_workflow_state()
            return

        output_path = filedialog.asksaveasfilename(
            title="Export Contacts",
            defaultextension=".csv",
            filetypes=[("CSV Files", "*.csv")]
        )
        if not output_path:
            self._set_status("Export cancelled")
            self._refresh_workflow_state()
            return

        if self.contact_manager.export_contacts(output_path, contacts):
            self._set_status(f"📤 Exported {len(contacts)} contacts")
            messagebox.showinfo("Export Successful", f"Contacts exported to:\n{output_path}")
        else:
            self._set_status("❌ Export failed")
            messagebox.showerror("Export Failed", "Could not export contacts.")
        self._refresh_workflow_state()

    def _on_preview_messages(self) -> None:
        """Preview first few processed messages with variable substitution."""
        template = self.message_textbox.get("1.0", "end").strip()
        if not template:
            messagebox.showwarning("Preview", "Please write a message first.")
            self._set_status("✍️ Write message to preview")
            return

        contacts = self.contact_manager.get_all_contacts()
        if not contacts:
            messagebox.showwarning("Preview", "Import contacts to generate preview.")
            self._set_status("⚠️ Import contacts for preview")
            return

        preview_dialog = ctk.CTkToplevel(self)
        preview_dialog.title("Message Preview")
        preview_dialog.geometry("720x460")
        preview_dialog.transient(self)

        heading = ctk.CTkLabel(
            preview_dialog,
            text="Preview for first 3 contacts",
            font=("Segoe UI", 14, "bold"),
            text_color=COLOR_ACCENT
        )
        heading.pack(pady=(12, 6), padx=14, anchor="w")

        output = ctk.CTkTextbox(preview_dialog, fg_color=COLOR_DARK_BG, text_color=COLOR_DARK_TEXT)
        output.pack(fill="both", expand=True, padx=14, pady=(4, 12))

        for idx, contact in enumerate(contacts[:3], start=1):
            processed, _ = self.message_processor.substitute_variables(template, contact)
            output.insert(
                "end",
                f"[{idx}] {contact.name} ({contact.phone})\n{processed}\n\n{'-' * 60}\n\n"
            )

        output.configure(state="disabled")
        self._set_status("👁️ Preview generated")
    
    def _on_template_selected(self, template: str) -> None:
        """Handle template selection."""
        templates = {
            "Fee Reminder": "Dear {name}, your fee of {amount} is due on {due_date}. Please pay as soon as possible.",
            "Appointment": "Dear {name}, your appointment is scheduled for {date} at {time}. Please confirm.",
            "Promotional": "Special offer for {name}! Get 20% off this week only. Don't miss out!",
        }
        
        if template in templates:
            self.message_textbox.delete("1.0", "end")
            self.message_textbox.insert("1.0", templates[template])
        self._refresh_workflow_state()
    
    def _on_message_changed(self, event=None) -> None:
        """Handle message text change."""
        content = self.message_textbox.get("1.0", "end")
        char_count = len(content) - 1  # -1 for the newline
        self.char_label.configure(text=f"Characters: {char_count}/65536")
        self._refresh_workflow_state()

    def _on_consent_changed(self) -> None:
        """Handle consent checkbox change."""
        self._refresh_workflow_state()
    
    def _on_delay_changed(self, value: float) -> None:
        """Handle delay slider change."""
        delay_int = int(value)
        self.delay_value_label.configure(text=f"{delay_int} seconds")
    
    def _on_send_campaign(self) -> None:
        """Handle send campaign button."""
        # Check consent
        if not self.consent_var.get():
            Logger.warning("User must check consent before sending")
            self._set_status("☑️ Consent is required")
            messagebox.showwarning("Consent Required", "Please enable Recipient Consent before sending campaign.")
            return
        
        # Get message
        message = self.message_textbox.get("1.0", "end").strip()
        if not message:
            Logger.warning("Message cannot be empty")
            self._set_status("✍️ Message cannot be empty")
            messagebox.showwarning("Missing Message", "Please type your message before sending.")
            return
        
        # Get contacts
        contacts = self.contact_manager.get_all_contacts()
        if not contacts:
            Logger.warning("No contacts to send to")
            self._set_status("⚠️ No contacts found")
            messagebox.showwarning("No Contacts", "Please import contacts before starting campaign.")
            return
        
        Logger.info(f"Campaign send initiated: {len(contacts)} contacts")
        self.campaign_running = True
        self.progress_bar.configure(progress_color=COLOR_SUCCESS)
        self.progress_bar.set(0.08)
        self.right_status.configure(text="WhatsApp: 🟢 Active")
        self._set_status(f"🚀 Sending to {len(contacts)} contacts")
        messagebox.showinfo(
            "Campaign Started",
            f"Campaign initialized for {len(contacts)} contacts.\n\nUse Pause/Stop controls as needed."
        )
    
    def _on_start_send(self) -> None:
        """Handle start sending."""
        Logger.info("Start sending clicked")
        self._on_send_campaign()
    
    def _on_pause_send(self) -> None:
        """Handle pause sending."""
        Logger.info("Pause sending clicked")
        if not self.campaign_running:
            self._set_status("ℹ️ Start campaign first")
            messagebox.showinfo("Pause", "No active campaign to pause.")
            return
        self.progress_bar.configure(progress_color=COLOR_WARNING)
        self._set_status("⏸️ Campaign paused")
    
    def _on_stop_send(self) -> None:
        """Handle stop sending."""
        Logger.info("Stop sending clicked")
        if not self.campaign_running:
            self._set_status("ℹ️ No running campaign")
            return
        self.campaign_running = False
        self.progress_bar.set(0)
        self.progress_bar.configure(progress_color=COLOR_ACCENT)
        self.right_status.configure(text="WhatsApp: 🔴 Disconnected")
        self._set_status("⏹️ Campaign stopped")
        messagebox.showinfo("Campaign Stopped", "Campaign has been stopped successfully.")


def main():
    """Main entry point."""
    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()
