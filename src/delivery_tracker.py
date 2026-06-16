"""SQLite-backed delivery tracking and reporting for outbound messages."""

from __future__ import annotations

import csv
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .database.db_manager import DatabaseManager
from .utils.logger import Logger


class DeliveryTracker:
    """Manage message delivery states, stats, and exportable reports."""

    POLLABLE_STATUSES = {"sent", "delivered"}

    def __init__(self, reports_dir: Optional[Path] = None):
        self.db = DatabaseManager()
        self.reports_dir = (reports_dir or Path("./reports")).resolve()
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        self._monitor_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def create_message(
        self,
        phone: str,
        message_text: str,
        status: str = "pending",
        error_reason: Optional[str] = None,
        whatsapp_message_id: Optional[str] = None,
    ) -> Optional[int]:
        """Insert a tracked message row and return its ID."""
        sent_at = datetime.now() if status in {"sent", "delivered", "read"} else None
        delivered_at = datetime.now() if status in {"delivered", "read"} else None
        read_at = datetime.now() if status == "read" else None
        return self.db.create_tracked_message(
            phone=phone,
            message_text=message_text,
            status=status,
            sent_at=sent_at,
            delivered_at=delivered_at,
            read_at=read_at,
            error_reason=error_reason,
            whatsapp_message_id=whatsapp_message_id,
        )

    def update_status(self, message_id: int, new_status: str, error_reason: Optional[str] = None) -> bool:
        """Update message status and relevant timestamps."""
        now = datetime.now()
        payload: Dict[str, Any] = {"status": new_status}

        if new_status in {"sent", "delivered", "read"}:
            payload["sent_at"] = now
        if new_status in {"delivered", "read"}:
            payload["delivered_at"] = now
        if new_status == "read":
            payload["read_at"] = now
        if new_status == "failed":
            payload["error_reason"] = error_reason or "Unknown delivery failure"

        return self.db.update_tracked_message(message_id, **payload)

    def get_stats(self) -> Dict[str, Any]:
        """Return aggregate message delivery stats."""
        return self.db.get_tracked_message_stats()

    def get_recent_messages(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent tracked messages."""
        return self.db.get_tracked_messages(limit=limit)

    def export_report(self, format: str = "csv") -> Path:
        """Export tracked messages to the reports directory."""
        format_lower = format.lower()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        rows = self.db.get_tracked_messages(limit=5000)

        if format_lower == "csv":
            output_path = self.reports_dir / f"delivery_report_{timestamp}.csv"
            self._export_csv(output_path, rows)
            return output_path

        if format_lower == "pdf":
            output_path = self.reports_dir / f"delivery_report_{timestamp}.pdf"
            self._export_pdf(output_path, rows)
            return output_path

        raise ValueError("format must be 'csv' or 'pdf'")

    def start_monitoring(
        self,
        status_resolver: Callable[[Dict[str, Any]], Optional[str]],
        interval_seconds: int = 5,
    ) -> None:
        """Poll in-flight messages and apply any upgraded statuses."""
        self.stop_monitoring()
        self._stop_event.clear()

        def worker() -> None:
            Logger.info("Starting delivery monitor")
            while not self._stop_event.is_set():
                messages = self.db.get_tracked_messages(statuses=list(self.POLLABLE_STATUSES), limit=200)
                for message in messages:
                    try:
                        resolved_status = status_resolver(message)
                        if resolved_status and resolved_status != message.get("status"):
                            self.update_status(int(message["id"]), resolved_status)
                    except Exception as exc:
                        Logger.warning(f"Delivery status resolver failed: {exc}")
                self._stop_event.wait(interval_seconds)
            Logger.info("Delivery monitor stopped")

        self._monitor_thread = threading.Thread(target=worker, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self) -> None:
        """Stop any active background delivery polling thread."""
        self._stop_event.set()
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=1.5)
        self._monitor_thread = None

    def _export_csv(self, output_path: Path, rows: List[Dict[str, Any]]) -> None:
        fieldnames = [
            "id",
            "phone",
            "message_text",
            "status",
            "sent_at",
            "delivered_at",
            "read_at",
            "error_reason",
        ]
        with output_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            for row in rows:
                writer.writerow({key: row.get(key, "") for key in fieldnames})

    def _export_pdf(self, output_path: Path, rows: List[Dict[str, Any]]) -> None:
        pdf = canvas.Canvas(str(output_path), pagesize=A4)
        width, height = A4
        x_margin = 14 * mm
        y_position = height - 18 * mm
        pdf.setFont("Helvetica-Bold", 14)
        pdf.drawString(x_margin, y_position, "MessageCannon Delivery Report")
        y_position -= 10 * mm

        pdf.setFont("Helvetica", 9)
        for row in rows:
            if y_position < 18 * mm:
                pdf.showPage()
                pdf.setFont("Helvetica", 9)
                y_position = height - 18 * mm

            line = (
                f"#{row.get('id')} | {row.get('phone')} | {row.get('status')} | "
                f"sent={row.get('sent_at') or '-'} | delivered={row.get('delivered_at') or '-'} | "
                f"read={row.get('read_at') or '-'}"
            )
            pdf.drawString(x_margin, y_position, line[:120])
            y_position -= 6 * mm

        pdf.save()