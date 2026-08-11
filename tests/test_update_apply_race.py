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
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Windows-only update mechanism")

from src.core.update_checker import (  # noqa: E402
    spawn_update_after_current_process_exits,
    get_installed_exe_path,
)


def _write_marker_stand_in(tmp_path, marker_path, name="fake_installer.bat"):
    """A trivial stand-in for the real Inno Setup installer: when run with
    the same /VERYSILENT /SUPPRESSMSGBOXES /NORESTART args the real
    installer receives (a .bat ignores unknown args harmlessly), it just
    writes a marker file -- proving the real wait-then-launch mechanism
    without needing a real installer or touching any real install. `name`
    defaults to the original fixed filename every pre-existing test in
    this file already relies on; pass a distinct name when a test needs
    two independent stand-ins in the same tmp_path (e.g. installer +
    relaunch target) so one doesn't silently overwrite the other."""
    bat_path = tmp_path / name
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


def _write_failing_installer_stand_in(tmp_path):
    """A trivial stand-in for a real installer that fails (matching the
    real, already-documented Inno Setup exit-code-5 case) -- writes no
    marker and exits non-zero, so a relaunch triggered off this must never
    happen."""
    bat_path = tmp_path / "failing_installer.bat"
    bat_path.write_text("@echo off\r\nexit /b 5\r\n")
    return str(bat_path)


def test_relaunches_the_app_after_a_successful_install(tmp_path):
    """The real fix (2026-08-11): the app previously stayed closed after a
    successful update, forcing the user to find and reopen it themselves.
    Once the silent install genuinely succeeds (a real, checked exit code
    0 -- not assumed), the new version must now be relaunched
    automatically."""
    install_marker = tmp_path / "install_marker.txt"
    installer = _write_marker_stand_in(tmp_path, install_marker, name="fake_installer.bat")
    relaunch_marker = tmp_path / "relaunch_marker.txt"
    relaunch_exe = _write_marker_stand_in(tmp_path, relaunch_marker, name="fake_relaunch.bat")

    dummy = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
    try:
        spawn_update_after_current_process_exits(
            installer, pid=dummy.pid, relaunch_exe_path=relaunch_exe)
        dummy.terminate()
        dummy.wait(timeout=5)

        deadline = time.time() + 15
        while time.time() < deadline and not install_marker.exists():
            time.sleep(0.5)
        assert install_marker.exists(), "the installer never ran"

        deadline = time.time() + 15
        while time.time() < deadline and not relaunch_marker.exists():
            time.sleep(0.5)
        assert relaunch_marker.exists(), (
            "the app was not relaunched after a real, successful install")
    finally:
        if dummy.poll() is None:
            dummy.terminate()
            dummy.wait(timeout=5)


def test_does_not_relaunch_when_the_install_fails(tmp_path):
    """The install genuinely failing (the real, documented exit-code-5
    case) must never trigger a relaunch -- that would reopen the OLD
    version while implying an update that didn't actually happen."""
    installer = _write_failing_installer_stand_in(tmp_path)
    relaunch_marker = tmp_path / "relaunch_marker.txt"
    relaunch_exe = _write_marker_stand_in(tmp_path, relaunch_marker, name="fake_relaunch.bat")

    dummy = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
    try:
        spawn_update_after_current_process_exits(
            installer, pid=dummy.pid, relaunch_exe_path=relaunch_exe)
        dummy.terminate()
        dummy.wait(timeout=5)

        time.sleep(4)
        assert not relaunch_marker.exists(), (
            "the app was relaunched even though the install failed")
    finally:
        if dummy.poll() is None:
            dummy.terminate()
            dummy.wait(timeout=5)


def test_no_relaunch_param_keeps_the_original_fire_and_forget_behavior(monkeypatch, tmp_path):
    """When relaunch_exe_path is omitted -- every call site before this fix
    -- behavior must stay byte-for-byte the pre-fix fire-and-forget
    Start-Process: no -Wait, no -PassThru, no exit-code branch. This is
    the "don't touch anything else" guarantee for the default path."""
    captured = {}

    class _FakePopen:
        def __init__(self, command, **kwargs):
            captured["script"] = command[-1]
            self.pid = 999999

    monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
    spawn_update_after_current_process_exits(str(tmp_path / "installer.exe"), pid=1234)

    script = captured["script"]
    assert "-Wait" not in script
    assert "PassThru" not in script
    assert "ExitCode" not in script


class TestGetInstalledExePath:
    """get_installed_exe_path() reads the real HKCU\\Software\\MessageCannon
    InstallPath value installer/setup.iss already writes on every install.
    These tests monkeypatch winreg entirely rather than reading it for
    real -- this dev machine genuinely does have a real MessageCannon
    install registered there from earlier verification passes, so a real
    read would make the test's result depend on whatever happens to be
    installed locally right now, not the code under test."""

    def test_returns_none_on_non_windows(self, monkeypatch):
        monkeypatch.setattr("src.core.update_checker.sys.platform", "linux")
        assert get_installed_exe_path() is None

    def test_builds_exe_path_from_the_real_registry_value(self, monkeypatch):
        monkeypatch.setattr("src.core.update_checker.sys.platform", "win32")

        class _FakeKey:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

        fake_winreg = SimpleNamespace(
            HKEY_CURRENT_USER=object(),
            OpenKey=lambda root, subkey: _FakeKey(),
            QueryValueEx=lambda key, name: (
                r"C:\Users\Test\AppData\Local\Programs\MessageCannon", 1),
        )
        monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

        result = get_installed_exe_path()
        assert result == (
            r"C:\Users\Test\AppData\Local\Programs\MessageCannon\MessageCannon.exe")

    def test_returns_none_when_the_registry_key_is_missing(self, monkeypatch):
        monkeypatch.setattr("src.core.update_checker.sys.platform", "win32")

        def _raise_open_key(root, subkey):
            raise OSError("key not found")

        fake_winreg = SimpleNamespace(
            HKEY_CURRENT_USER=object(),
            OpenKey=_raise_open_key,
            QueryValueEx=lambda key, name: 1 / 0,  # must never be reached
        )
        monkeypatch.setitem(sys.modules, "winreg", fake_winreg)

        assert get_installed_exe_path() is None
