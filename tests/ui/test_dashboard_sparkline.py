"""Item 37 (UI/UX benchmark pass vs premium tools): a real 7-day send-
volume sparkline on the Campaigns dashboard's primary stat card, plus a
real, pre-existing "Sent this week" label/data mismatch found and fixed
while adding it.
"""

from __future__ import annotations


def test_dashboard_sparkline_canvas_exists_and_is_real_sized(app):
    assert hasattr(app, "dashboard_sparkline")
    app.update()
    assert app.dashboard_sparkline.winfo_exists()
    assert app.dashboard_sparkline.winfo_reqheight() >= 20


def test_dashboard_sparkline_draws_real_points_for_real_data(app, monkeypatch):
    monkeypatch.setattr(app.db, "get_daily_sent_counts", lambda days=7: [1, 2, 3, 4, 5, 6, 7])
    app._draw_dashboard_sparkline()
    app.update()
    items = app.dashboard_sparkline.find_all()
    assert len(items) > 0, "expected real drawn canvas items (line/points), not an empty canvas"


def test_dashboard_sparkline_handles_all_zero_days_without_crashing(app, monkeypatch):
    monkeypatch.setattr(app.db, "get_daily_sent_counts", lambda days=7: [0, 0, 0, 0, 0, 0, 0])
    app._draw_dashboard_sparkline()
    app.update()
    # A flat all-zero week is a valid real state (brand-new install) --
    # must not raise (e.g. a division by zero on max(values)==0).


def test_sent_this_week_card_reflects_week_stats_not_today_stats(app, monkeypatch):
    """Real, pre-existing mismatch found while adding the sparkline: the
    card's own visible label reads "Sent this week" but was populated from
    get_message_stats_for_period("today"), not "week" -- confirmed by
    driving the real _refresh_stats() with distinguishable fake values for
    each period."""
    def fake_period_stats(period):
        return {"today": {"sent_count": 3}, "week": {"sent_count": 30}, "month": {"sent_count": 300}}[period]

    monkeypatch.setattr(app.db, "get_message_stats_for_period", fake_period_stats)
    monkeypatch.setattr(app.db, "get_daily_sent_counts", lambda days=7: [0] * 7)
    app._refresh_stats(update_dashboard_periods=True)
    app.update()
    assert app.dashboard_cards["Sent Today"].cget("text") == "30"
