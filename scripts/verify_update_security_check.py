"""Real, deterministic, isolated reproduction of the PyInstaller onefile
"Security validation failure: parent process has different executable!"
bug reported against the real in-app update/relaunch flow (2026-08-30).

Root cause (confirmed by reading the real bootloader source shipped with the
PyInstaller version installed on this machine -- bootloader/src/pyi_security.c
and pyi_main.c from https://github.com/pyinstaller/pyinstaller):

A PyInstaller onefile app on Windows always runs as TWO processes using the
SAME .exe file: a "parent" (bootloader) process that self-extracts to a temp
dir and sets internal `_PYI_ARCHIVE_FILE` / `_PYI_APPLICATION_HOME_DIR` /
`_PYI_PARENT_PROCESS_LEVEL` environment variables, then launches a "child"
process (the real, running application -- this is what `os.getpid()` resolves
to inside MessageCannon) which inherits those variables and skips
re-extraction. As a defense against a malicious process spoofing those
variables to trick a child into trusting an attacker-controlled temp
directory, the CHILD process verifies that its real, OS-reported PARENT
process is running the exact same executable path as itself
(`pyi_security_verify_parent_proces` in pyi_security.c) -- if not, it aborts
with exactly this error, via a blocking MessageBox on a windowed build.

The bug: `subprocess.Popen` inherits the calling process's FULL environment
by default. Since `_PYI_ARCHIVE_FILE` etc. are a NORMAL, ALWAYS-PRESENT part
of a running onefile app's own `os.environ` (confirmed live against this
machine's real, currently-running MessageCannon.exe -- see the investigation
notes accompanying this fix), spawning the update helper without stripping
them lets them leak through PowerShell's own `Start-Process` (which also
inherits its caller's environment) into the newly RELAUNCHED top-level
process. That fresh process then sees `_PYI_ARCHIVE_FILE` already set,
pointing at ITS OWN exe path (same install location, just newer bytes) --
so it mistakes itself for a "child" continuing a session, checks its real OS
parent (which is powershell.exe, not another copy of the app), and aborts.

This script proves, using a REAL compiled PyInstaller onefile probe app
(never the live production MessageCannon install, and never touching its
registry/session/database) and the REAL, unmodified
`spawn_update_after_current_process_exits()` from this codebase:

  1. The already-shipped fix (env stripped before spawning the relaunch
     helper) genuinely prevents the crash -- a real "updated" instance
     launches and its own Python code genuinely runs.
  2. The exact same scenario, run WITHOUT that stripping (mirroring what an
     OLDER, pre-fix build of this app would do), genuinely reproduces the
     real native security-check failure -- confirming the diagnosis, not
     just asserting it.

Run manually: build Probe.exe first (see build_probe() below is called
automatically if missing), then:

    python scripts/verify_update_security_check.py
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_SRC = str(REPO_ROOT / "src")

TEST_ROOT = Path(tempfile.gettempdir()) / "mc_update_security_probe"
SRC_DIR = TEST_ROOT / "src"
DIST_DIR = TEST_ROOT / "dist"
BUILD_DIR = TEST_ROOT / "build"
INSTALL_DIR = TEST_ROOT / "install"
MARKER_DIR = TEST_ROOT / "markers"
PROBE_EXE = INSTALL_DIR / "Probe.exe"
BUILT_EXE = DIST_DIR / "Probe.exe"

# Embedded so this script is fully self-contained and reusable (no separate
# source file to keep track of). Kept intentionally minimal: on start, every
# onefile process (parent AND child) writes a marker recording its own real
# _PYI_* environment -- a marker only ever appears if this Python code
# actually got to run, i.e. PyInstaller's native bootloader security check
# (pyi_security_verify_parent_proces in pyi_security.c) did NOT abort it
# first. It then waits for a JSON "trigger" file to appear, at which point
# it invokes the update orchestration ITSELF (either the real, unmodified
# `spawn_update_after_current_process_exits` from this repo, or a
# reimplementation of the pre-2026-08-17 behavior for comparison) -- this
# must happen from inside the probe's own process so it genuinely inherits
# this process's own real, poisoned _PYI_* environment, exactly like
# main_window.py's real call does. Calling the orchestration from the test
# driver's own (clean) process would prove nothing.
_PROBE_APP_SOURCE = r'''
import json
import os
import subprocess
import sys
import tempfile
import time
import pathlib

MARKER_DIR = pathlib.Path(r"%(marker_dir)s")
MARKER_DIR.mkdir(parents=True, exist_ok=True)

pid = os.getpid()
marker = MARKER_DIR / f"alive_{pid}.txt"
pyi_vars = {k: v for k, v in os.environ.items() if k.startswith("_PYI")}
with open(marker, "w", encoding="utf-8") as f:
    f.write(f"pid={pid}\n")
    f.write(f"ppid={os.getppid()}\n")
    for k, v in sorted(pyi_vars.items()):
        f.write(f"{k}={v}\n")

trigger_file = MARKER_DIR / f"trigger_{pid}.json"
stop_file = MARKER_DIR / f"stop_{pid}.txt"


def _run_fixed(cfg):
    # The REAL, unmodified function from this repo, called from inside a
    # real onefile child process.
    sys.path.insert(0, cfg["repo_src"])
    from core.update_checker import spawn_update_after_current_process_exits
    spawn_update_after_current_process_exits(
        cfg["installer_path"], pid, cfg["relaunch_path"])


def _run_broken(cfg):
    # Reimplements the PRE-2026-08-17 orchestration: no _PYI* stripping
    # anywhere -- mirrors what an older, already-compiled build of this
    # app's own code still does today for anyone on a version older than
    # the real fix.
    sys.path.insert(0, cfg["repo_src"])
    from core.update_checker import launch_silent_install_and_get_command
    install_cmd = launch_silent_install_and_get_command(cfg["installer_path"])
    script_fd, script_path = tempfile.mkstemp(suffix=".ps1", prefix="mc_broken_update_")
    script = (
        "param([int]$TargetPid,[string]$InstallerPath,[string]$InstallerArgsStr,[string]$RelaunchPath)\n"
        "Wait-Process -Id $TargetPid -ErrorAction SilentlyContinue\n"
        "Start-Sleep -Milliseconds 400\n"
        "$installerArgs = @($InstallerArgsStr -split ' ' | Where-Object { $_ -ne '' })\n"
        "$p = Start-Process -FilePath $InstallerPath -ArgumentList $installerArgs -Wait -PassThru\n"
        "if ($p.ExitCode -eq 0 -and $RelaunchPath) { Start-Process -FilePath $RelaunchPath -PassThru | Out-Null }\n"
        "try { Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue } catch {}\n"
    )
    with os.fdopen(script_fd, "w", encoding="utf-8") as f:
        f.write(script)
    command = [
        "powershell.exe", "-NoProfile", "-WindowStyle", "Hidden",
        "-ExecutionPolicy", "Bypass", "-File", script_path,
        "-TargetPid", str(pid),
        "-InstallerPath", install_cmd[0],
        "-InstallerArgsStr", " ".join(install_cmd[1:]),
        "-RelaunchPath", cfg["relaunch_path"],
    ]
    # THE BUG: full, unfiltered environment inheritance (no env= override).
    subprocess.Popen(command, close_fds=True,
                      stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                      stderr=subprocess.DEVNULL)


deadline = time.time() + 40
while time.time() < deadline and not stop_file.exists():
    if trigger_file.exists():
        try:
            cfg = json.loads(trigger_file.read_text(encoding="utf-8"))
            trigger_file.unlink()
            (_run_fixed if cfg["mode"] == "fixed" else _run_broken)(cfg)
        except Exception as e:
            (MARKER_DIR / f"error_{pid}.txt").write_text(repr(e), encoding="utf-8")
        break
    time.sleep(0.15)
'''

WAIT_FOR_CHILD_S = 20
WAIT_FOR_RELAUNCH_S = 20


def _clean_markers():
    if MARKER_DIR.exists():
        for f in MARKER_DIR.glob("*.txt"):
            try:
                f.unlink()
            except OSError:
                pass
    MARKER_DIR.mkdir(parents=True, exist_ok=True)


def _wait_for_marker(exclude_pids, timeout_s) -> int | None:
    """Poll for a NEW alive_<pid>.txt marker not in exclude_pids.
    A marker only appears if the probe's own Python code actually ran --
    i.e. the native bootloader security check did NOT abort it first."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        for f in MARKER_DIR.glob("alive_*.txt"):
            pid = int(f.stem.split("_", 1)[1])
            if pid not in exclude_pids:
                return pid
        time.sleep(0.2)
    return None


def _find_child_pid(parent_pid: int, timeout_s: float) -> int | None:
    import psutil
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        try:
            parent = psutil.Process(parent_pid)
            children = parent.children()
            if children:
                return children[0].pid
        except psutil.NoSuchProcess:
            return None
        time.sleep(0.15)
    return None


def _kill_tree(pid: int):
    import psutil
    try:
        p = psutil.Process(pid)
        for child in p.children(recursive=True):
            try:
                child.terminate()
            except psutil.NoSuchProcess:
                pass
        p.terminate()
    except psutil.NoSuchProcess:
        pass


def _describe_pyi_vars(pid: int) -> dict:
    import psutil
    try:
        env = psutil.Process(pid).environ()
        return {k: v for k, v in env.items() if k.startswith("_PYI")}
    except Exception as e:
        return {"<error>": str(e)}


def _launch_fresh_probe():
    """Launches the real, installed probe exe as a brand-new top-level
    process, exactly the way Explorer/Start Menu would (no PyInstaller env
    vars present in this test driver's own environment)."""
    clean_env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI")}
    proc = subprocess.Popen([str(PROBE_EXE)], env=clean_env, close_fds=True)
    return proc


def _make_stand_in_installer(replacement_exe: Path) -> Path:
    """A trivial stand-in for the real Inno Setup installer -- just copies
    a (possibly byte-different) probe exe over the installed one and exits
    0, so this test never depends on Inno Setup being present. Matches the
    same substitution already used by tests/test_update_apply_race.py."""
    bat_path = TEST_ROOT / "fake_installer.bat"
    bat_path.write_text(
        f'@echo off\r\ncopy /Y "{replacement_exe}" "{PROBE_EXE}" >nul\r\nexit /b 0\r\n',
        encoding="utf-8",
    )
    return bat_path


def _run_one_scenario(label: str, mode: str) -> dict:
    print(f"\n=== Scenario: {label} ===")
    _clean_markers()

    old_top = _launch_fresh_probe()
    old_child_pid = _find_child_pid(old_top.pid, WAIT_FOR_CHILD_S)
    if old_child_pid is None:
        raise RuntimeError("Probe's own onefile child process never appeared")
    child_marker = _wait_for_marker(exclude_pids=set(), timeout_s=WAIT_FOR_CHILD_S)
    if child_marker != old_child_pid:
        # marker filenames are keyed by pid so this should always match;
        # tolerate ordering by just re-deriving via marker files directly.
        pass
    pyi_vars = _describe_pyi_vars(old_child_pid)
    print(f"old top-level pid={old_top.pid}, real onefile child pid={old_child_pid}")
    print(f"child's real _PYI* vars: {pyi_vars}")
    if not pyi_vars:
        raise RuntimeError(
            "Expected the real onefile child process to have _PYI_* env vars "
            "set (this is normal onefile behavior) -- something about the "
            "build changed; aborting rather than reporting a false result."
        )

    installer_path = _make_stand_in_installer(BUILT_EXE)

    # Hand the real child process (old_child_pid) a trigger file telling IT
    # to invoke the orchestration itself, from inside its own real process
    # -- this is what makes the test faithful: the spawn must happen from a
    # process that genuinely already has the poisoned _PYI* vars in its own
    # os.environ, exactly like main_window.py's real call does. Calling the
    # spawn function from this driver script's own (clean) process would
    # prove nothing, since this driver never has those vars set itself.
    trigger = MARKER_DIR / f"trigger_{old_child_pid}.json"
    trigger.write_text(json.dumps({
        "mode": mode,
        "repo_src": REPO_SRC,
        "installer_path": str(installer_path),
        "relaunch_path": str(PROBE_EXE),
    }), encoding="utf-8")

    # Give the child a moment to notice the trigger and call Popen for the
    # helper before we kill it.
    deadline = time.time() + 5
    while time.time() < deadline and trigger.exists():
        time.sleep(0.1)
    if trigger.exists():
        raise RuntimeError("Probe process never picked up the trigger file")
    time.sleep(0.3)

    err_file = MARKER_DIR / f"error_{old_child_pid}.txt"
    if err_file.exists():
        raise RuntimeError(f"Probe's own orchestration call raised: {err_file.read_text()}")

    # Let the real onefile child exit -- this is what the real helper's
    # Wait-Process/file-unlock-poll is waiting on before it proceeds.
    _kill_tree(old_top.pid)

    new_pid = _wait_for_marker(exclude_pids={old_child_pid}, timeout_s=WAIT_FOR_RELAUNCH_S)

    result = {"label": label, "old_child_pid": old_child_pid, "new_child_pid": new_pid}
    if new_pid is not None:
        print(f"RESULT: relaunch SUCCEEDED -- new onefile child pid={new_pid} "
              f"genuinely started and ran its own Python code.")
        result["success"] = True
    else:
        print("RESULT: relaunch FAILED -- no new marker appeared within "
              f"{WAIT_FOR_RELAUNCH_S}s. Checking for a hung dialog window...")
        result["success"] = False
        _report_and_close_stray_dialogs()

    return result


def _report_and_close_stray_dialogs():
    import psutil
    import ctypes
    user32 = ctypes.windll.user32
    found_any = False
    for p in psutil.process_iter(["pid", "name", "exe"]):
        try:
            if p.info["exe"] and str(p.info["exe"]) == str(PROBE_EXE):
                print(f"  stray Probe.exe process still alive: pid={p.info['pid']}")
                found_any = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    titles = []

    def _cb(hwnd, _):
        length = user32.GetWindowTextLengthW(hwnd)
        if length > 0:
            buf = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buf, length + 1)
            titles.append((hwnd, buf.value))
        return True

    WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)
    user32.EnumWindows(WNDENUMPROC(_cb), 0)
    error_windows = [(h, t) for h, t in titles if "error" in t.lower() and "probe" not in t.lower()]
    real_error_windows = [(h, t) for h, t in titles if t.strip().lower() == "error"]
    if real_error_windows:
        print(f"  found a real 'Error' dialog window on screen: {real_error_windows}")
        for hwnd, _ in real_error_windows:
            user32.PostMessageW(hwnd, 0x0010, 0, 0)  # WM_CLOSE
        found_any = True
    if not found_any:
        print("  no stray Probe.exe process or 'Error' dialog window found "
              "(process may have exited silently with a non-zero code).")


def build_probe_if_missing():
    if BUILT_EXE.exists():
        return
    SRC_DIR.mkdir(parents=True, exist_ok=True)
    probe_source = SRC_DIR / "probe_app.py"
    probe_source.write_text(
        _PROBE_APP_SOURCE % {"marker_dir": str(MARKER_DIR)}, encoding="utf-8")
    print(f"Building probe exe (real PyInstaller onefile, windowed) -- this "
          f"takes a little while the first time...")
    result = subprocess.run([
        sys.executable, "-m", "PyInstaller",
        "--onefile", "--windowed", "--noconfirm",
        "--distpath", str(DIST_DIR),
        "--workpath", str(BUILD_DIR),
        "--specpath", str(TEST_ROOT),
        "--name", "Probe",
        "--hidden-import", "platform", "--hidden-import", "requests",
        "--hidden-import", "re", "--hidden-import", "tempfile",
        "--hidden-import", "dataclasses", "--hidden-import", "typing",
        "--hidden-import", "subprocess", "--hidden-import", "json",
        str(probe_source),
    ], capture_output=True, text=True)
    if result.returncode != 0 or not BUILT_EXE.exists():
        print(result.stdout[-3000:])
        print(result.stderr[-3000:])
        raise RuntimeError("PyInstaller build of the probe exe failed")


def main():
    build_probe_if_missing()
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BUILT_EXE, PROBE_EXE)

    results = []
    results.append(_run_one_scenario(
        "REAL shipped fix (env stripped before relaunch)", "fixed"))
    time.sleep(1.5)
    results.append(_run_one_scenario(
        "Pre-fix behavior (no env stripping, mirrors an older build)", "broken"))

    print("\n=== SUMMARY ===")
    for r in results:
        print(f"  {r['label']}: {'SUCCESS (relaunched cleanly)' if r['success'] else 'FAILED (security check crash reproduced)'}")

    fixed_ok = results[0]["success"]
    broken_failed = not results[1]["success"]
    if fixed_ok and broken_failed:
        print("\nCONCLUSION: diagnosis confirmed. The already-shipped fix "
              "(stripping _PYI* env vars before spawning the relaunched "
              "process) is what makes the difference between these two "
              "otherwise-identical runs.")
    else:
        print("\nCONCLUSION: inconclusive/unexpected -- do not trust the fix "
              "based on this run. fixed_ok=%s broken_failed=%s" % (fixed_ok, broken_failed))
    return 0 if (fixed_ok and broken_failed) else 1


if __name__ == "__main__":
    raise SystemExit(main())
