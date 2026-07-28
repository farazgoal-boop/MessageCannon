"""Real bug found via a live user report: clicking "Download & Install" on
the update dialog (v1.3.0 -> v1.3.1) showed the download progress bar
complete and the app closed itself as expected -- but reopening via the
real Start Menu/Desktop icon still showed the old version, as if nothing
had happened.

Root-caused via a real, controlled reproduction (recorded in CLAUDE.md, not
just theorized): a genuine v1.3.0 install, launched for real, with the real
v1.3.1 installer run against it while still open -- the silent install does
NOT degrade gracefully; it fails outright with a real Inno Setup exit code
5 ("fatal error during install"), because it cannot overwrite this app's
own locked, in-use .exe. The old `_apply_downloaded_update` launched the
installer via `spawn_detached()` (a fire-and-forget `subprocess.Popen` that
never checks the exit code) essentially simultaneously with the app's own
`_on_close()` -- so this failure was completely invisible: the app closed
anyway and implied success, leaving the user stuck on the old version while
believing they'd updated.

Fix: `spawn_update_after_current_process_exits()` launches a background
helper that waits for the CURRENT process's own PID to fully exit (a real
Windows process-wait, not a fixed sleep/guess) before it ever runs the
installer, eliminating the race structurally.

A second, independent real bug was found while verifying the fix itself,
via a marker-file test harness (not assumed): the new helper initially
reused `spawn_detached()`'s own `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`
creationflags, but testing each flag combination in isolation showed
`DETACHED_PROCESS` specifically prevents the helper from ever completing
its job in this environment -- `CREATE_NEW_PROCESS_GROUP` alone (or no
flags at all) works correctly. Fixed to use `CREATE_NEW_PROCESS_GROUP` only.

The full real fix was also verified completely outside this test suite,
end to end, against the real production pipeline: a genuine v1.3.0 install,
a real running app, the real fixed apply-update code path pointed at that
real PID, a real app close, polling the real Windows registry
(``HKCU\\Software\\MessageCannon\\Version``) until it read "1.3.1", and --
critically -- relaunching via the real installed .exe path (exactly what a
Start Menu/Desktop icon does) and confirming the real window title read
"MessageCannon Pro v1.3.1". That real-world proof cannot be committed as an
automated test (it needs a real Inno Setup install/uninstall cycle and
takes real installer download/run time), so this file covers the
structural mechanism -- the same wait-then-launch code, exercised against a
trivial stand-in "installer" -- as the automated, repeatable regression
guard.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only update mechanism")

from src.core.update_checker import spawn_update_after_current_process_exits  # noqa: E402


def _write_marker_stand_in(tmp_path, marker_path):
    """A trivial stand-in for the real Inno Setup installer: when run with
    the same /VERYSILENT /SUPPRESSMSGBOXES /NORESTART args the real
    installer receives (a .bat ignores unknown args harmlessly), it just
    writes a marker file -- proving the real wait-then-launch mechanism
    without needing a real installer or touching any real install."""
    bat_path = tmp_path / "fake_installer.bat"
    bat_path.write_text(f'@echo off\r\necho done> "{marker_path}"\r\n')
    return str(bat_path)


def test_installer_does_not_run_while_target_process_is_still_alive(tmp_path):
    """The literal repro of the root cause: the installer must never be
    invoked while the process it needs to replace is still running."""
    marker = tmp_path / "marker.txt"
    installer = _write_marker_stand_in(tmp_path, marker)

    dummy = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
    try:
        spawn_update_after_current_process_exits(installer, pid=dummy.pid)
        time.sleep(1.5)
        assert not marker.exists(), (
            "installer ran while the target process was still alive -- "
            "this is exactly the race that caused the real reported bug")
    finally:
        dummy.terminate()
        dummy.wait(timeout=5)


def test_installer_runs_once_target_process_exits(tmp_path):
    """The real fix: once the target process genuinely exits, the waiting
    helper must actually proceed to run the installer -- proven with a real
    Windows process (not mocked) and a real Wait-Process-based helper."""
    marker = tmp_path / "marker.txt"
    installer = _write_marker_stand_in(tmp_path, marker)

    dummy = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
    spawn_update_after_current_process_exits(installer, pid=dummy.pid)

    dummy.terminate()
    dummy.wait(timeout=5)

    deadline = time.time() + 10
    while time.time() < deadline and not marker.exists():
        time.sleep(0.5)
    assert marker.exists(), "installer never ran after the target process genuinely exited"


def test_defaults_to_the_calling_process_own_pid(monkeypatch, tmp_path):
    """When no explicit pid is given (the real production call site never
    passes one), the helper must wait on the CALLING process's own PID, not
    some other one."""
    captured = {}

    class _FakePopen:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            captured["kwargs"] = kwargs
            self.pid = 999999

    monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
    spawn_update_after_current_process_exits(str(tmp_path / "installer.exe"))

    script = captured["command"][-1]
    assert f"Wait-Process -Id {os.getpid()}" in script


def test_does_not_use_detached_process_flag(monkeypatch, tmp_path):
    """Real, isolated bug found while verifying this fix: DETACHED_PROCESS
    specifically prevented the helper from ever completing, confirmed by
    testing each creationflags combination individually against a real
    marker-file target. Locks in the corrected flag so it can't silently
    regress back to the broken combination."""
    captured = {}

    class _FakePopen:
        def __init__(self, command, **kwargs):
            captured["kwargs"] = kwargs
            self.pid = 999999

    monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
    spawn_update_after_current_process_exits(str(tmp_path / "installer.exe"), pid=1234)

    flags = captured["kwargs"].get("creationflags", 0)
    assert flags & subprocess.DETACHED_PROCESS == 0, (
        "DETACHED_PROCESS must not be used -- confirmed via direct testing "
        "that it prevents the update-apply helper from ever completing")
