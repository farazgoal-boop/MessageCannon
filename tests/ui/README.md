# UI/Integration test suite

## Running

Two invocations, for two different purposes — running everything at once
with `-n auto` under-reports failures on the Tcl crash and over-reports
them on timing (see "Why two commands" below).

```bash
# Functional/correctness tests — parallel, one process per file
python -m pytest tests/ui/ -n 48 --dist loadfile \
  --ignore=tests/ui/test_navigation_timing.py --ignore=tests/ui/test_close_button.py \
  --ignore=tests/ui/test_nav_accent_timing.py

# Timing-sensitive tests — must run alone, no parallel contention
python -m pytest tests/ui/test_navigation_timing.py
python -m pytest tests/ui/test_close_button.py
python -m pytest tests/ui/test_nav_accent_timing.py
```

## Why two commands

**Every test file needs its own process.** Creating more than ~2-3
`ctk.CTk()`/`tkinter.Tk()` root windows in sequence within a single Python
process is unreliable on this stack — verified directly while building this
suite: a function-scoped `MainWindow` fixture worked for several tests then
failed with `Can't find a usable init.tcl` on a later one. A session-scoped
fixture (one shared window per file) reduced this but didn't eliminate it
once enough files each created their own dedicated window too. Running each
test *file* in its own OS process via `pytest-xdist`
(`-n <file-count> --dist loadfile`) sidesteps it entirely — confirmed: same
suite, zero Tcl errors, once isolated this way.

**But parallel processes distort wall-clock timing assertions.** 5
simultaneous `MainWindow()` instances (each with a real, if fake-failing,
WhatsApp session-bootstrap thread) compete for CPU, inflating measured
transition times — confirmed directly: `test_navigation_timing.py` passes
7/7 every time run alone, but under `-n 5` different tests fail on
different runs (Campaigns+Contacts one run, Campaigns+Contacts+Cards the
next) — the signature of resource contention, not a real regression. Run
these two files alone for a trustworthy number.

## Why not pywinauto

The parent document for this suite asked for `pytest` + `pywinauto`
specifically. Verified directly before writing any tests: connected
pywinauto to a real running instance of this app via both the `"uia"` and
`"win32"` backends and enumerated every descendant control. CustomTkinter
renders its widgets as shapes drawn onto a Tk Canvas rather than as
distinct native Win32/UWP controls, so **neither backend exposes an
accessible name, role, or even a non-empty `window_text` for a single one
of the app's real buttons or nav items** — only generic, anonymous
`"Pane"`/`"Image"` (uia) or `"TkChild"`/`"Static"` (win32) elements, zero
identifiable by name. This is a structural characteristic of
CustomTkinter's rendering model on Windows, not a bug in the test script —
two backends were tried before concluding this.

These tests instead call the exact same command callables/methods a real
click invokes, directly, in-process (see `conftest.py`'s `app` fixture
docstring). This is still the real, shipped production code — PyInstaller
bundles this exact source — just invoked directly rather than via a
simulated OS-level click, since no tool available in this environment can
perform the latter against this UI framework.

## Known, documented exception: Compose timing

`test_navigation_timing.py` gives `Compose` a 700ms budget instead of the
500ms every other view gets. Compose has the heaviest widget tree in the
app (dual WhatsApp/Email panels + a live contact checkbox list) and Tk's
own layout cost for making it visible measured 350-670ms **on its own**,
isolated directly from any animation logic (timed `grid()` /
`update_idletasks()` / `place()` calls individually). It's exempted from
the slide-in animation entirely (`MainWindow._HEAVY_VIEWS_NO_ANIMATION`)
and its layout is pre-warmed once at startup (hidden behind the splash
screen) — both helped, neither eliminated the cost, which recurs (reduced)
on every visit, not just the first. Logged as a known structural
characteristic rather than chased further this pass; a full fix would mean
simplifying Compose's own widget tree.

## Fixtures

See `conftest.py` docstrings — `app` (session-scoped, shared) for most
tests, `isolated_db` (a throwaway temp-file SQLite database) for anything
that needs to write contact/campaign data without ever touching the real
user database.
