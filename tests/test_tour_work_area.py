"""`_work_area_bottom` (tour.py) -- the real fix found while producing
Item 39 v2's own demo screenshots: the cursor-follow card was clamped
against the FULL screen height (taskbar included), so on any real machine
with a visible Windows taskbar the card could render partially behind it
whenever the cursor was near the bottom of the screen. No Tk window needed
for these -- pure platform/ctypes logic."""

from __future__ import annotations

import sys

from src.ui.tour import _work_area_bottom


def test_non_windows_returns_the_fallback_unchanged(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert _work_area_bottom(900) == 900


def test_windows_failure_falls_back_gracefully(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")

    class _BoomCtypes:
        def __getattr__(self, name):
            raise RuntimeError("no ctypes here")

    import builtins
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "ctypes":
            return _BoomCtypes()
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    assert _work_area_bottom(900) == 900


def test_on_this_real_windows_machine_returns_a_sane_bound():
    if sys.platform != "win32":
        import pytest
        pytest.skip("real work-area query is Windows-only")
    result = _work_area_bottom(1080)
    assert 0 < result <= 1080
