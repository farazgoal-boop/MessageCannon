"""In-app update checking against GitHub Releases.

Career Copilot Premium — studied per instruction before writing any of this
— turned out to have **no in-app update mechanism at all** to match: its only
update path is `install_update_now.bat`, a manual taskkill-then-rerun-the-
installer script the user double-clicks by hand, with no version check, no
GitHub API call, and no sidebar indicator anywhere in its source. There was
nothing to port. This module is new work, designed around MessageCannon's own
existing release pipeline (`.github/workflows/build-mac-linux.yml`, which
already tags+publishes GitHub Releases with macOS/Linux artifacts attached)
rather than copying anything.

Windows note: that workflow does not currently build/attach a Windows asset
(the release body just tells users to build one locally) — so `check_for_update`
can find a real Windows release but `asset_url` will be None until a Windows
.exe is actually attached to a release, either by adding a Windows CI job or
uploading one by hand. Callers must handle `asset_url is None` as a normal,
expected case, not an error.
"""

from __future__ import annotations

import os
import platform
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from typing import Callable, Optional

import requests

GITHUB_API_LATEST_RELEASE = "https://api.github.com/repos/farazgoal-boop/MessageCannon/releases/latest"
GITHUB_RELEASES_PAGE = "https://github.com/farazgoal-boop/MessageCannon/releases"
REQUEST_TIMEOUT_S = 6
DOWNLOAD_TIMEOUT_S = 30


@dataclass
class UpdateInfo:
    version: str                  # e.g. "1.1.0" (tag with leading 'v' stripped)
    tag: str                      # e.g. "v1.1.0"
    release_notes: str
    release_url: str
    asset_url: Optional[str]      # direct browser_download_url for this platform's asset, if attached
    asset_name: Optional[str]


def _parse_version(v: str) -> tuple:
    """'1.2.10' -> (1, 2, 10) so comparison is numeric, not lexicographic
    (a plain string compare would wrongly rank '1.9.0' above '1.10.0')."""
    parts = re.findall(r"\d+", v)
    return tuple(int(p) for p in parts) if parts else (0,)


def is_newer(remote_version: str, current_version: str) -> bool:
    return _parse_version(remote_version) > _parse_version(current_version)


def _asset_suffix_for_platform() -> str:
    system = platform.system()
    if system == "Windows":
        return ".exe"
    if system == "Darwin":
        return ".dmg"
    return ".AppImage"


def check_for_update(current_version: str) -> Optional[UpdateInfo]:
    """Returns UpdateInfo if a newer GitHub release exists, else None.

    Never raises: any network failure, timeout, or malformed response is
    treated as "no update found" rather than an error. A flaky or offline
    connection must never surface as a popup on every launch — the app stays
    fully usable on its current version regardless of whether this check
    succeeds."""
    try:
        resp = requests.get(
            GITHUB_API_LATEST_RELEASE,
            timeout=REQUEST_TIMEOUT_S,
            headers={"Accept": "application/vnd.github+json"},
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        tag = data.get("tag_name", "") or ""
        remote_version = tag.lstrip("vV")
        if not remote_version or not is_newer(remote_version, current_version):
            return None

        suffix = _asset_suffix_for_platform()
        asset_url = None
        asset_name = None
        for asset in data.get("assets", []) or []:
            name = asset.get("name", "")
            if name.lower().endswith(suffix.lower()):
                asset_url = asset.get("browser_download_url")
                asset_name = name
                break

        return UpdateInfo(
            version=remote_version,
            tag=tag,
            release_notes=(data.get("body") or "").strip(),
            release_url=data.get("html_url") or GITHUB_RELEASES_PAGE,
            asset_url=asset_url,
            asset_name=asset_name,
        )
    except Exception:
        return None


def download_asset(asset_url: str, asset_name: str,
                    on_progress: Optional[Callable[[float], None]] = None) -> str:
    """Downloads the release asset to a temp file, returns the local path.
    Raises on any failure — callers must catch and show an error while
    leaving the current install untouched; nothing here modifies the running
    app until the caller explicitly launches an installer afterward."""
    dest = os.path.join(tempfile.gettempdir(), asset_name)
    with requests.get(asset_url, stream=True, timeout=DOWNLOAD_TIMEOUT_S) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0) or 0)
        written = 0
        with open(dest, "wb") as f:
            for chunk in r.iter_content(chunk_size=262144):
                if not chunk:
                    continue
                f.write(chunk)
                written += len(chunk)
                if on_progress and total:
                    try:
                        on_progress(written / total)
                    except Exception:
                        # Progress reporting is UI convenience, not part of the
                        # download itself — a callback failure (e.g. the UI
                        # widget it updates no longer exists) must never abort
                        # an otherwise-successful download. Real bug found via
                        # a real end-to-end test: the file was fully and
                        # correctly written to disk, but the whole operation
                        # was reported as "failed" because this callback threw,
                        # so the successfully-downloaded installer was silently
                        # discarded and never launched.
                        pass
    if os.path.getsize(dest) == 0:
        raise IOError("Downloaded update file is empty")
    return dest


def can_silent_install() -> bool:
    """True only on Windows, where installer/setup.iss already builds a
    per-user (PrivilegesRequired=lowest) installer — a silent re-run needs no
    admin elevation. macOS (.dmg, drag-to-Applications) and Linux (.deb needs
    sudo; AppImage has no install step) have no equivalent unattended path
    that's safe to automate without a real Mac/Linux install to verify
    against, which this environment doesn't have — scoped out deliberately
    rather than guessed at."""
    return platform.system() == "Windows"


def launch_silent_install_and_get_command(installer_path: str) -> list:
    """Returns the command to launch the downloaded Windows installer
    silently (per-user, no UAC prompt). MessageCannon must already be closed
    before this runs — Inno Setup cannot overwrite the running .exe."""
    return [installer_path, "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"]


def spawn_detached(command: list) -> None:
    """Launches `command` as a fully detached process so it survives this
    process exiting — used to start the installer right before MessageCannon
    closes itself for the update to complete."""
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(command, close_fds=True, **kwargs)


def get_installed_exe_path() -> Optional[str]:
    """Reads the real, current install directory from the same
    HKCU\\Software\\MessageCannon\\InstallPath registry value
    installer/setup.iss already writes on every install (see its own
    [Registry] section) and returns the full path to the app's own .exe
    inside it. Windows-only; returns None on any failure (key/value
    missing, non-Windows) rather than guessing a path -- a None result
    just means no auto-relaunch happens, never a crash."""
    if sys.platform != "win32":
        return None
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\MessageCannon") as key:
            install_dir, _ = winreg.QueryValueEx(key, "InstallPath")
    except OSError:
        return None
    return os.path.join(install_dir, "MessageCannon.exe")


def spawn_update_after_current_process_exits(
    installer_path: str,
    pid: Optional[int] = None,
    relaunch_exe_path: Optional[str] = None,
) -> None:
    """Real bug fix (2026-07-28): the previous sequence was
    `spawn_detached(install_command)` immediately followed by `_on_close()` —
    launching the installer and closing the app at essentially the same
    moment. Confirmed via a real, controlled reproduction (a genuine
    installed v1.3.0, launched for real, with the real v1.3.1 installer run
    against it while still open): the silent install does NOT queue a
    delayed replace or otherwise degrade gracefully -- it fails outright
    with a real Inno Setup exit code 5 ("fatal error during install"),
    because it cannot overwrite this app's own locked, in-use .exe.
    `spawn_detached` never checked the exit code (it's fire-and-forget by
    design, so the install could survive the app closing), so this failure
    was completely invisible: the app closed anyway and implied success,
    leaving the user on the old version indefinitely while believing they'd
    updated.

    Fix: launch a background helper that waits for THIS process's own PID to
    fully exit -- guaranteed by Windows' own process-wait semantics, not a
    fixed sleep/guess -- before running the installer at all. This
    eliminates the race structurally rather than trying to close faster.

    A second real, isolated bug found while verifying THIS fix (via a
    marker-file test harness, not assumed): `subprocess.CREATE_NO_WINDOW`'s
    sibling `subprocess.DETACHED_PROCESS` -- previously used by the sibling
    `spawn_detached()` above, and initially copied into this function too --
    reliably prevented the helper from ever completing its job, confirmed by
    testing each `creationflags` combination in isolation (`DETACHED_PROCESS`
    alone: fails; `DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP`: fails;
    `CREATE_NEW_PROCESS_GROUP` alone: works; no flags at all: also works).
    `CREATE_NEW_PROCESS_GROUP` alone is used here -- it still isolates the
    helper from this process's own Ctrl+C/console signals, and `-WindowStyle
    Hidden` (passed to the PowerShell command itself, not a Popen flag)
    already keeps it invisible, so nothing is lost by dropping
    `DETACHED_PROCESS`.

    2026-08-11 real bug fix: the app did not reopen automatically once the
    silent install finished -- the user had to find and relaunch it
    themselves via the Start Menu/Desktop icon. installer/setup.iss's own
    `[Run]` post-install launch step is deliberately `skipifsilent` (a
    silent install must never pop UI), so nothing in the installer itself
    can do this. Fixed by optionally extending this same helper:
    `relaunch_exe_path`, when given, makes the install run synchronously
    (`-Wait -PassThru`, so its real exit code can be checked instead of
    assumed) and relaunches the app only once that exit code confirms
    success. Left as an opt-in parameter, defaulting to None (no relaunch,
    identical to the previous fire-and-forget behavior), specifically so
    this function's own existing tests -- which use a trivial stand-in
    installer, not a real install -- can never accidentally trigger a real
    relaunch.

    2026-08-11 follow-up real bug fix: the relaunch above worked mechanically
    (verified: the new process really does start, with the right exit-code
    gate) but a real user reported the new window never actually appeared on
    screen -- they had to open it themselves via the Start Menu/Desktop icon.
    Root-caused via a real, controlled reproduction of the exact production
    two-process shape (PyInstaller onefile ships a bootloader parent process
    that spawns the real, windowed app as a CHILD process -- confirmed
    directly via `Get-CimInstance Win32_Process`): a background helper
    process (this PowerShell script) launching a new window is subject to
    Windows' anti-focus-stealing protection -- `Start-Process` alone starts
    the process but does **not** grant it the right to become the foreground
    window, so it can open invisibly behind whatever else is on screen (e.g.
    other browser windows) with no visible cue, which reads exactly like "it
    didn't reopen." Fixed two ways, both standard Windows techniques for
    exactly this "close and relaunch as a new process" scenario:
    1. The relaunch script now walks down to the real windowed CHILD process
       (mirroring the same bootloader-to-child resolution used to verify this
       bug) and explicitly calls `ShowWindow`/`SetForegroundWindow` on its
       real window handle once it appears, wrapped in its own try/catch so a
       failure here can never prevent the relaunch itself from happening.
    2. `_apply_downloaded_update` (main_window.py) now calls
       `AllowSetForegroundWindow(ASFW_ANY)` from the still-foreground old
       process just before it closes, granting the *next* SetForegroundWindow
       call from *any* process the right to succeed -- both the new app's own
       normal startup `focus_force()` (main.py) and this script's explicit
       call benefit from that grant.

    Also switched from a single inline `-Command` string (manually
    single-quote-escaped, fragile for paths containing spaces like this
    project's own real "HAROON TRADERS" test install path) to a real,
    parameterized `.ps1` script file: paths are passed as genuine argv
    elements via `subprocess.Popen`'s own list-based quoting, not
    hand-escaped into a string, eliminating that whole class of risk.

    2026-08-17 real bug fix, found via a real end-to-end repro after a real
    user reported v1.7.2 still didn't apply (stayed on v1.7.1) AND a visible
    PowerShell console window flashed on screen -- two separate real bugs in
    this same function, not one:

    1. **The actual install-failure root cause.** `pid` here is
       `os.getpid()` from inside the running app -- but under PyInstaller
       onefile on Windows, that's the CHILD of a two-process pair (a
       bootloader-parent process that self-extracts to a temp dir, then
       launches the real app as a child, confirmed via
       `Get-CimInstance Win32_Process`). Measured directly, repeatedly, on
       this real machine: the *parent* -- not the child our own pid
       resolves to -- is the process that's actually still holding the
       installed `.exe` file open, and it does NOT release that lock the
       instant the child exits; cleaning up its own temp extraction
       directory took up to ~900ms-1.8s *after* the child was already gone.
       `Wait-Process -Id $TargetPid` (the child) was returning almost
       immediately while the real file lock was still held, so the
       installer launched right into a still-locked target file, failed
       silently (a real, non-zero, never-surfaced Inno Setup exit code --
       `/SUPPRESSMSGBOXES` means this is invisible), and since relaunch is
       correctly gated on exit code 0, no relaunch ever fired either --
       exactly the reported "install never applied, app never reopened"
       symptom, together, from one cause. Fixed by no longer trusting
       "PID exited" as a proxy for "the file is free": the script now polls
       the actual target `.exe` file itself (opened `ReadWrite`, share
       `None` -- the exact exclusivity Inno Setup itself needs) until it
       genuinely unlocks, bounded by `_FILE_UNLOCK_TIMEOUT_S`, before ever
       launching the installer. This sidesteps needing to reason about
       exactly which process in the pair holds the lock (a PyInstaller
       bootloader implementation detail that could shift across versions)
       by checking the one fact that actually matters.
    2. **The visible console flash.** `-WindowStyle Hidden` only tells
       PowerShell to hide its window *after* Windows has already created a
       console for it -- a well-documented `powershell.exe` quirk (as
       opposed to `pwsh.exe`) where the console can flash briefly before
       that hiding takes effect. The previous `creationflags` here was
       `CREATE_NEW_PROCESS_GROUP` alone, deliberately without
       `DETACHED_PROCESS` (the earlier, isolated real bug: `DETACHED_PROCESS`
       reliably broke `Wait-Process` inside the helper, confirmed by testing
       each flag combination directly) -- but `CREATE_NO_WINDOW` is a
       distinct flag from `DETACHED_PROCESS` (0x08000000 vs 0x00000008) and
       was never actually tried on its own. Verified directly this pass:
       `CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP` prevents Windows from
       ever allocating a console for the helper in the first place (so
       there is nothing to flash, a stronger guarantee than hiding an
       already-created one) and does not reintroduce the earlier
       `Wait-Process` breakage, since it is not `DETACHED_PROCESS`.

    2026-08-17 follow-up real bug fix, found from a real user report showing
    an actual PyInstaller error dialog after a real Download & Install
    click: "Security validation failure: parent process has different
    executable!" -- this exact wording, confirmed by reading the strings
    embedded in the real shipped MessageCannon.exe, comes from PyInstaller's
    own onefile bootloader (not this app's code): starting around
    PyInstaller 6.9, a process spawned via the same executable as its
    parent is assumed to be a worker sub-process that should REUSE the
    parent's already-extracted resources, tracked via internal `_PYI_*`
    environment variables (`_PYI_ARCHIVE_FILE`, `_PYI_APPLICATION_HOME_DIR`,
    etc.) -- and newer PyInstaller versions added a real security check
    validating that assumption against the actual OS-reported parent
    process before trusting it.

    Root cause: `subprocess.Popen` inherits the calling process's FULL
    environment by default when `env=` isn't given. When this whole update
    flow runs for real (inside the actual running, frozen MessageCannon.exe,
    not an external test driver), the OLD process's own real `_PYI_*`
    bookkeeping vars leak into the spawned PowerShell helper, and from there
    -- since PowerShell's own `Start-Process` also inherits its environment
    by default -- into the newly relaunched (updated) exe too. That process
    then sees stale bookkeeping pointing at the OLD version's archive/temp
    dir while its real OS parent is `powershell.exe`, not another
    MessageCannon.exe -- exactly the mismatch the security check correctly
    flags. Confirmed directly, not assumed: a throwaway test that sets fake
    `_PYI_ARCHIVE_FILE`/`_PYI_APPLICATION_HOME_DIR` values (simulating being
    inside a real frozen process) and has the spawned target dump its own
    visible environment showed those exact values leaking all the way
    through, unmodified, before this fix.

    Fixed by explicitly building the helper's environment (`env=`) with
    every `_PYI`-prefixed key stripped, so nothing stale ever reaches
    PowerShell in the first place -- and, defensively, the `.ps1` script
    itself also clears any `_PYI*` variables from its own process
    environment immediately before it launches the relaunch target, in case
    a future PyInstaller version introduces additional internal variables
    under the same prefix that this Python-level filter should already
    catch, or PowerShell itself ever picks up something from elsewhere."""
    if pid is None:
        pid = os.getpid()
    install_cmd = launch_silent_install_and_get_command(installer_path)
    helper_env = {k: v for k, v in os.environ.items() if not k.startswith("_PYI")}
    if not relaunch_exe_path:
        escaped_path = install_cmd[0].replace("'", "''")
        args_literal = ",".join(f"'{a}'" for a in install_cmd[1:])
        ps_script = (
            f"$__mcTargetExe = $null; "
            f"try {{ $__mcTargetExe = (Get-Process -Id {pid} -ErrorAction Stop).Path }} catch {{}}; "
            f"Wait-Process -Id {pid} -ErrorAction SilentlyContinue; "
            f"if ($__mcTargetExe) {{ "
            f"$__mcDeadline = (Get-Date).AddSeconds({_FILE_UNLOCK_TIMEOUT_S}); "
            f"while ((Get-Date) -lt $__mcDeadline) {{ "
            f"try {{ $__mcFs = [System.IO.File]::Open($__mcTargetExe, 'Open', 'ReadWrite', 'None'); $__mcFs.Close(); break }} "
            f"catch {{ Start-Sleep -Milliseconds 150 }} }} }}; "
            f"Start-Process -FilePath '{escaped_path}' -ArgumentList {args_literal}"
        )
        command = ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script]
    else:
        script_fd, script_path = tempfile.mkstemp(suffix=".ps1", prefix="mc_update_")
        with os.fdopen(script_fd, "w", encoding="utf-8") as f:
            f.write(_RELAUNCH_PS1_SCRIPT.replace("__FILE_UNLOCK_TIMEOUT_S__", str(_FILE_UNLOCK_TIMEOUT_S)))
        command = [
            "powershell.exe", "-NoProfile", "-WindowStyle", "Hidden",
            "-ExecutionPolicy", "Bypass", "-File", script_path,
            "-TargetPid", str(pid),
            "-InstallerPath", install_cmd[0],
            "-InstallerArgsStr", " ".join(install_cmd[1:]),
            "-RelaunchPath", relaunch_exe_path,
        ]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW
    subprocess.Popen(
        command, close_fds=True, env=helper_env,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **kwargs)


_FILE_UNLOCK_TIMEOUT_S = 10


_RELAUNCH_PS1_SCRIPT = r"""param(
    [int]$TargetPid,
    [string]$InstallerPath,
    [string]$InstallerArgsStr,
    [string]$RelaunchPath
)

# The file that's actually about to be overwritten -- prefer $RelaunchPath
# (it's built from the same registry InstallPath the installer itself
# writes to, so it names the exact on-disk target), falling back to the
# watched process's own image path when no relaunch path was given.
$targetExePath = $RelaunchPath
if (-not $targetExePath) {
    try { $targetExePath = (Get-Process -Id $TargetPid -ErrorAction Stop).Path } catch {}
}

Wait-Process -Id $TargetPid -ErrorAction SilentlyContinue

# Real bug fix (2026-08-17): the watched PID exiting is not the same
# moment the real .exe file lock releases -- PyInstaller onefile's
# bootloader-parent process can hold that file open for up to ~1-2s after
# its own child (the PID waited on above) has already exited, while it
# finishes cleaning up its own temp extraction directory. Poll the actual
# file for real exclusive-openability (the same access Inno Setup itself
# needs) instead of trusting "PID gone" as a proxy for "file free".
if ($targetExePath) {
    $__mcDeadline = (Get-Date).AddSeconds(__FILE_UNLOCK_TIMEOUT_S__)
    while ((Get-Date) -lt $__mcDeadline) {
        try {
            $__mcFs = [System.IO.File]::Open($targetExePath, 'Open', 'ReadWrite', 'None')
            $__mcFs.Close()
            break
        } catch {
            Start-Sleep -Milliseconds 150
        }
    }
}

$installerArgs = @($InstallerArgsStr -split ' ' | Where-Object { $_ -ne '' })
$p = Start-Process -FilePath $InstallerPath -ArgumentList $installerArgs -Wait -PassThru

if ($p.ExitCode -eq 0 -and $RelaunchPath) {
    # Real bug fix (2026-08-17): PyInstaller onefile's own internal _PYI_*
    # bookkeeping env vars (belonging to the OLD, closed process) can reach
    # this helper via inheritance and, if left in place, would leak into
    # the relaunch target below too -- making it look like a spoofed
    # "worker sub-process" of a process that no longer matches its real OS
    # parent, tripping PyInstaller's own real "Security validation failure:
    # parent process has different executable!" check. The Python side
    # already strips these before spawning this helper; clearing again here
    # is defense in depth against any future PyInstaller internal variable
    # under the same prefix, or anything else that might set one.
    Get-ChildItem Env: | Where-Object { $_.Name -like '_PYI*' } | ForEach-Object {
        Remove-Item "Env:$($_.Name)" -ErrorAction SilentlyContinue
    }
    $new = Start-Process -FilePath $RelaunchPath -PassThru
    try {
        Add-Type -Name ForegroundHelper -Namespace MessageCannonUpdate -MemberDefinition @'
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool SetForegroundWindow(System.IntPtr hWnd);
[System.Runtime.InteropServices.DllImport("user32.dll")]
public static extern bool ShowWindow(System.IntPtr hWnd, int nCmdShow);
'@
        $deadline = (Get-Date).AddSeconds(15)
        $targetId = $new.Id
        $hwnd = [IntPtr]::Zero
        while ((Get-Date) -lt $deadline -and $hwnd -eq [IntPtr]::Zero) {
            Start-Sleep -Milliseconds 300
            $child = Get-CimInstance Win32_Process -Filter "ParentProcessId=$targetId" -ErrorAction SilentlyContinue | Select-Object -First 1
            if ($child) { $targetId = $child.ProcessId }
            $proc = Get-Process -Id $targetId -ErrorAction SilentlyContinue
            if ($proc -and $proc.MainWindowHandle -ne [IntPtr]::Zero) { $hwnd = $proc.MainWindowHandle }
        }
        if ($hwnd -ne [IntPtr]::Zero) {
            [MessageCannonUpdate.ForegroundHelper]::ShowWindow($hwnd, 9) | Out-Null
            [MessageCannonUpdate.ForegroundHelper]::SetForegroundWindow($hwnd) | Out-Null
        }
    } catch {}
}

try { Remove-Item -LiteralPath $MyInvocation.MyCommand.Path -Force -ErrorAction SilentlyContinue } catch {}
"""
