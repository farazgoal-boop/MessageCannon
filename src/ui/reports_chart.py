"""Reusable matplotlib chart for the Reports tab (single canvas, in-place updates)."""

from __future__ import annotations

from typing import Optional, Tuple

from ..utils.logger import Logger


class ReportsChart:
    """Pie chart for read vs unread — create once, update via ax.clear() + draw_idle()."""

    def __init__(self, parent) -> None:
        from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
        from matplotlib.figure import Figure

        self._last: Optional[Tuple[int, int]] = None
        self.fig = Figure(figsize=(4.5, 1.8), dpi=100, facecolor="#0c131b")
        self.ax = self.fig.add_subplot(111)
        self.canvas = FigureCanvasTkAgg(self.fig, master=parent)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.update(0, 0)

    def update(self, read_count: int, unread_count: int) -> bool:
        """Redraw only when values change. Returns True if a redraw occurred."""
        key = (read_count, unread_count)
        if key == self._last:
            return False
        self._last = key

        try:
            self.ax.clear()
            if read_count + unread_count == 0:
                self.ax.text(0.5, 0.5, "No data yet", ha="center", va="center", color="#8ea5af")
                self.ax.set_facecolor("#0c131b")
                self.ax.axis("off")
            else:
                self.ax.pie(
                    [read_count, unread_count],
                    labels=["Read", "Unread"],
                    colors=["#39b37a", "#7d3037"],
                    autopct="%1.0f%%",
                    textprops={"color": "#d8ebf6", "fontsize": 9},
                )
                self.ax.set_facecolor("#0c131b")
            self.canvas.draw_idle()
            return True
        except Exception as exc:
            Logger.warning(f"Chart update skipped: {exc}")
            return False
