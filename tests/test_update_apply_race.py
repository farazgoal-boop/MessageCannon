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


def test_installer_does_not_run_while_target_exe_file_is_still_locked_after_pid_exits(tmp_path):
    """Real bug fix (2026-08-17), found from a real user report that v1.7.2
    still didn't apply (stayed on v1.7.1) after clicking Download & Install:
    the watched PID exiting is NOT the same moment the real installed .exe
    file's lock actually releases. PyInstaller onefile ships a bootloader-
    parent process that self-extracts to a temp dir and then launches the
    real app as a CHILD -- `os.getpid()` inside the app resolves to that
    child, but the *parent* is the one still holding the real, on-disk exe
    file open, and measured directly on a real machine it can keep holding
    it for up to ~1-2s after the child has already exited (cleaning up its
    own temp extraction dir). This test simulates that split directly: a
    dummy process stands in for the watched PID and exits immediately,
    while a SEPARATE process independently holds a real, exclusive lock
    (.NET FileStream, share=None -- the same access Inno Setup itself
    needs) on the target exe path for a further ~2s. The installer must
    not run until that real lock actually releases, not just once the
    watched PID is gone."""
    marker = tmp_path / "marker.txt"
    installer = _write_marker_stand_in(tmp_path, marker)
    target_exe = tmp_path / "MessageCannon.exe"
    target_exe.write_bytes(b"stand-in exe bytes")

    dummy = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
    lock_holder = subprocess.Popen([
        "powershell.exe", "-NoProfile", "-Command",
        f"$fs = [System.IO.File]::Open('{target_exe}', 'Open', 'ReadWrite', 'None'); "
        f"Start-Sleep -Seconds 2; $fs.Close()",
    ])
    try:
        spawn_update_after_current_process_exits(
            installer, pid=dummy.pid, relaunch_exe_path=str(target_exe))
        dummy.terminate()
        dummy.wait(timeout=5)

        # Poll continuously (not a single fixed-delay sample -- a first
        # version of this test used a single time.sleep(0.8) check and was
        # confirmed, via a real measured timing script, to pass against
        # BOTH the buggy and the fixed code by pure coincidence: on the
        # real buggy code the marker consistently appeared around ~0.9-1.0s
        # on this machine, uncomfortably close to a 0.8s single sample) so
        # the actual real-world ordering of "marker appears" vs "lock
        # released" is what's asserted, not a guessed timing window.
        marker_seen_at = None
        lock_released_at = None
        deadline = time.time() + 10
        while time.time() < deadline and (marker_seen_at is None or lock_released_at is None):
            if marker_seen_at is None and marker.exists():
                marker_seen_at = time.time()
            if lock_released_at is None and lock_holder.poll() is not None:
                lock_released_at = time.time()
            time.sleep(0.05)

        assert lock_released_at is not None, "lock_holder never exited -- test setup is broken"
        assert marker_seen_at is not None, (
            "installer never ran even after the real file lock released")
        assert marker_seen_at >= lock_released_at, (
            "installer ran BEFORE the real target .exe file lock actually "
            "released, even though the watched PID had already exited -- "
            "this is exactly the newly-found real race")
    finally:
        if dummy.poll() is None:
            dummy.terminate()
            dummy.wait(timeout=5)
        lock_holder.wait(timeout=10)


def test_no_relaunch_script_also_waits_for_the_target_file_to_unlock(monkeypatch, tmp_path):
    """The rarer no-relaunch branch (relaunch_exe_path omitted) must get the
    same real-file-lock-wait fix, not just the relaunch branch -- it
    resolves the watched process's own image path up front and polls it
    the same way."""
    captured = {}

    class _FakePopen:
        def __init__(self, command, **kwargs):
            captured["script"] = command[-1]
            self.pid = 999999

    monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
    spawn_update_after_current_process_exits(str(tmp_path / "installer.exe"), pid=1234)

    script = captured["script"]
    assert "System.IO.File" in script and "'None'" in script, (
        "even the no-relaunch branch must wait for the real file lock to "
        "release before launching the installer, not just for the "
        "watched PID to exit")


def test_relaunch_ps1_file_also_waits_for_the_target_file_to_unlock(monkeypatch, tmp_path):
    captured = {}

    class _FakePopen:
        def __init__(self, command, **kwargs):
            captured["command"] = command
            self.pid = 999999

    monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
    spawn_update_after_current_process_exits(
        str(tmp_path / "installer.exe"), pid=1234,
        relaunch_exe_path=str(tmp_path / "MessageCannon.exe"))

    script_path = captured["command"][captured["command"].index("-File") + 1]
    content = open(script_path).read()
    os.remove(script_path)

    assert "System.IO.File" in content and "'None'" in content
    assert "targetExePath" in content


def test_helper_env_strips_pyi_prefixed_vars(monkeypatch, tmp_path):
    """Real bug fix (2026-08-17), found from a real user report showing an
    actual PyInstaller error dialog after a real Download & Install click:
    "Security validation failure: parent process has different
    executable!" -- confirmed by reading the strings embedded in the real
    shipped MessageCannon.exe to come from PyInstaller's OWN onefile
    bootloader security check, not this app's code. Root cause:
    subprocess.Popen inherits the calling process's full environment by
    default -- when this whole flow runs for real (inside the actual
    frozen app, which has real _PYI_ARCHIVE_FILE/_PYI_APPLICATION_HOME_DIR
    etc. set by its own bootloader), those stale values leak into the
    spawned PowerShell helper and, from there, into the relaunched
    (updated) exe too -- which then looks like a spoofed worker
    sub-process of a parent that doesn't match its real OS parent
    (powershell.exe), tripping the security check for real."""
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", r"C:\fake\OLD_VERSION.exe")
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", r"C:\fake\_MEIold")
    monkeypatch.setenv("SOME_REAL_UNRELATED_VAR", "keep-me")
    captured = {}

    class _FakePopen:
        def __init__(self, command, **kwargs):
            captured["kwargs"] = kwargs
            self.pid = 999999

    monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
    spawn_update_after_current_process_exits(str(tmp_path / "installer.exe"), pid=1234)

    env = captured["kwargs"].get("env")
    assert env is not None, "must pass an explicit env= to Popen, not inherit implicitly"
    assert not any(k.startswith("_PYI") for k in env), (
        "no _PYI-prefixed variable may reach the helper -- this is exactly "
        "what leaked into the relaunched app and tripped PyInstaller's own "
        "real security check")
    assert env.get("SOME_REAL_UNRELATED_VAR") == "keep-me", (
        "must still be a real environment (other variables preserved), not "
        "an empty/broken one")


def test_relaunch_target_does_not_inherit_stale_pyi_env_vars(monkeypatch, tmp_path):
    """The real, full end-to-end version of the test above: a genuine
    subprocess.Popen chain (helper -> installer -> relaunch target, all
    real Windows processes, nothing mocked at this level) with fake
    _PYI_* vars set on the calling process (simulating being inside a
    real frozen MessageCannon.exe) must NOT let those vars reach the
    relaunched target's own visible environment. Confirmed to fail
    against the pre-fix code (a real, direct repro, not assumed) before
    trusting this test."""
    monkeypatch.setenv("_PYI_ARCHIVE_FILE", r"C:\fake\OLD_VERSION.exe")
    monkeypatch.setenv("_PYI_APPLICATION_HOME_DIR", r"C:\fake\_MEIold")

    install_marker = tmp_path / "install_marker.txt"
    installer = _write_marker_stand_in(tmp_path, install_marker, name="fake_installer.bat")

    relaunch_marker = tmp_path / "relaunch_env_marker.txt"
    relaunch_bat = tmp_path / "fake_relaunch_target.bat"
    relaunch_bat.write_text(
        '@echo off\r\n'
        f'(for /f "delims=" %%v in (\'set _PYI 2^>nul\') do echo %%v)> "{relaunch_marker}"\r\n'
        f'if not exist "{relaunch_marker}" echo NO_PYI_VARS_FOUND> "{relaunch_marker}"\r\n'
    )

    dummy = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", "Start-Sleep -Seconds 30"])
    try:
        spawn_update_after_current_process_exits(
            installer, pid=dummy.pid, relaunch_exe_path=str(relaunch_bat))
        dummy.terminate()
        dummy.wait(timeout=5)

        deadline = time.time() + 15
        while time.time() < deadline and not install_marker.exists():
            time.sleep(0.3)
        assert install_marker.exists(), "the installer never ran"

        deadline = time.time() + 15
        while time.time() < deadline and not relaunch_marker.exists():
            time.sleep(0.3)
        assert relaunch_marker.exists(), "the relaunch target never ran"

        content = relaunch_marker.read_text()
        assert "_PYI_ARCHIVE_FILE" not in content and "_PYI_APPLICATION_HOME_DIR" not in content, (
            f"stale _PYI_* env vars leaked into the relaunched target's own "
            f"visible environment -- this is the real mechanism behind the "
            f"reported 'Security validation failure' dialog. Saw: {content!r}")
    finally:
        if dummy.poll() is None:
            dummy.terminate()
            dummy.wait(timeout=5)


def test_uses_create_no_window_to_prevent_console_flash(monkeypatch, tmp_path):
    """Real bug fix (2026-08-17): a real user reported a visible PowerShell
    console window briefly flashing on screen right after clicking
    Download & Install. `-WindowStyle Hidden` only hides an already-created
    console -- a well-documented `powershell.exe` quirk where the console
    can flash before that hiding takes effect. `CREATE_NO_WINDOW` (0x08000000,
    distinct from the earlier, already-rejected `DETACHED_PROCESS`,
    0x00000008) prevents Windows from ever allocating a console for the
    helper process in the first place."""
    captured = {}

    class _FakePopen:
        def __init__(self, command, **kwargs):
            captured["kwargs"] = kwargs
            self.pid = 999999

    monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
    spawn_update_after_current_process_exits(str(tmp_path / "installer.exe"), pid=1234)

    flags = captured["kwargs"].get("creationflags", 0)
    assert flags & subprocess.CREATE_NO_WINDOW != 0, (
        "CREATE_NO_WINDOW must be set so the console never has a chance to "
        "flash -- -WindowStyle Hidden alone is not sufficient")
    assert flags & subprocess.DETACHED_PROCESS == 0, (
        "must not reintroduce DETACHED_PROCESS -- already confirmed to "
        "break Wait-Process inside this same helper")


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


class TestRelaunchForegroundFix:
    """2026-08-11 follow-up real bug: a real user reported the relaunch
    above didn't visibly work -- confirmed via a real, controlled
    reproduction of the actual production shape (PyInstaller onefile's
    bootloader-parent + windowed-child process pair, via
    `Get-CimInstance Win32_Process`) that the underlying mechanism DOES
    fire correctly (the new process really does start with the right
    exit-code gate), but Windows' anti-focus-stealing protection can let a
    background-launched window open invisibly behind whatever else is on
    screen -- reading exactly like "it didn't reopen." Fixed by switching
    to a real parameterized .ps1 script file (argv-list quoting instead of
    hand-escaped string interpolation, which also removes a latent
    fragility for paths containing spaces, like this project's own real
    "HAROON TRADERS" test path) that explicitly resolves the real windowed
    child process and calls ShowWindow/SetForegroundWindow on it."""

    def test_relaunch_uses_a_real_ps1_file_not_a_hand_escaped_command_string(
            self, monkeypatch, tmp_path):
        captured = {}

        class _FakePopen:
            def __init__(self, command, **kwargs):
                captured["command"] = command
                self.pid = 999999

        monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
        relaunch_path = str(tmp_path / "HAROON TRADERS" / "MessageCannon.exe")
        spawn_update_after_current_process_exits(
            str(tmp_path / "installer.exe"), pid=1234, relaunch_exe_path=relaunch_path)

        command = captured["command"]
        assert "-File" in command
        script_path = command[command.index("-File") + 1]
        assert script_path.endswith(".ps1")
        assert os.path.exists(script_path), "the .ps1 helper must actually be written to disk"
        # The path (with its real embedded space) must travel as its own
        # untouched argv element -- not hand-quoted into a larger string,
        # which is exactly the class of fragility this fix removes.
        assert relaunch_path in command
        assert "-RelaunchPath" in command
        os.remove(script_path)

    def test_ps1_script_explicitly_forces_the_new_window_to_the_foreground(
            self, monkeypatch, tmp_path):
        """The actual fix: the written script must resolve the real windowed
        process (walking parent -> child, matching the real PyInstaller
        onefile shape) and call the real Win32 foreground APIs on it."""
        captured = {}

        class _FakePopen:
            def __init__(self, command, **kwargs):
                captured["command"] = command
                self.pid = 999999

        monkeypatch.setattr("src.core.update_checker.subprocess.Popen", _FakePopen)
        spawn_update_after_current_process_exits(
            str(tmp_path / "installer.exe"), pid=1234,
            relaunch_exe_path=str(tmp_path / "MessageCannon.exe"))

        script_path = captured["command"][captured["command"].index("-File") + 1]
        content = open(script_path).read()
        os.remove(script_path)

        assert "SetForegroundWindow" in content
        assert "ShowWindow" in content
        assert "ParentProcessId" in content, (
            "must walk down to the real windowed child, not assume the "
            "launched process itself owns the window")
        assert "try {" in content and "} catch {}" in content, (
            "the foreground-forcing step must be best-effort -- a failure "
            "there must never be able to block the relaunch itself")

    def test_relaunch_still_works_end_to_end_with_the_new_ps1_file(self, tmp_path):
        """Confirms the .ps1-file refactor didn't regress the actual
        mechanism this whole feature exists for -- same real assertion as
        test_relaunches_the_app_after_a_successful_install, run again here
        as a direct check on this specific change."""
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


def test_apply_downloaded_update_grants_foreground_rights_before_closing(monkeypatch):
    """The other half of the fix: `_apply_downloaded_update` (main_window.py)
    must call AllowSetForegroundWindow(ASFW_ANY) while it is still the
    foreground app, before it closes -- granting the *next*
    SetForegroundWindow call (from the new app's own startup focus_force(),
    or the relaunch script's explicit call) the right to succeed."""
    import types
    import src.ui.main_window as mw

    calls = []

    fake_user32 = types.SimpleNamespace(
        AllowSetForegroundWindow=lambda flag: calls.append(flag))
    fake_windll = types.SimpleNamespace(user32=fake_user32)
    monkeypatch.setattr(mw.ctypes, "windll", fake_windll, raising=False)
    monkeypatch.setattr(mw.sys, "platform", "win32")
    monkeypatch.setattr(
        mw, "spawn_update_after_current_process_exits", lambda *a, **k: None)
    monkeypatch.setattr(mw, "get_installed_exe_path", lambda: None)

    class _Dummy:
        _apply_downloaded_update = mw.MainWindow._apply_downloaded_update

        def _on_close(self):
            pass

    _Dummy()._apply_downloaded_update("C:\\fake\\installer.exe")

    assert calls == [-1], "must grant ASFW_ANY (-1) exactly once, before closing"
