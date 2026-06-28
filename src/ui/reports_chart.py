"""Reusable matplotlib chart for the Reports tab (single canvas, in-place updates)."""

from __future__ import annotations

from typing import Optional, Tuple

import customtkinter as ctk

from ..utils.logger import Logger
from . import theme as T


class ReportsChart:
    """Pie chart for read vs unread — create once, update via ax.clear() + draw_idle()."""

    def __init__(self, parent) -> None:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self._last: Optional[Tuple[int, int]] = None
        bg = self._bg()
        self.fig = Figure(figsize=(4.5, 1.8), dpi=100, facecolor=bg)
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.update(0, 0)

    @staticmethod
    def _bg() -> str:
        return T.BG_SURFACE if ctk.get_appearance_mode().lower() == "light" else T.BG_MAIN

    @staticmethod
    def _text_color() -> str:
        return T.TEXT_MUTED

    def update(self, read_count: int, unread_count: int) -> bool:
        """Redraw only when values change. Returns True if a redraw occurred."""
        key = (read_count, unread_count)
        if key == self._last:
            return False
        self._last = key

        bg = self._bg()
        txt = self._text_color()
        try:
            self.fig.set_facecolor(bg)
            self.ax.clear()
            if read_count + unread_count == 0:
                self.ax.text(0.5, 0.5, "No data yet", ha="center", va="center", color=txt)
                self.ax.set_facecolor(bg)
                self.ax.axis("off")
            else:
                self.ax.pie(
                    [read_count, unread_count],
                    labels=["Read", "Unread"],
                    colors=[T.SUCCESS, T.ACCENT],
                    autopct="%1.0f%%",
                    textprops={"color": txt, "fontsize": 9},
                )
                self.ax.set_facecolor(bg)
            self.canvas.draw_idle()
            return True
        except Exception as exc:
            Logger.warning(f"Chart update skipped: {exc}")
            return False
