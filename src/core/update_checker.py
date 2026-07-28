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


def spawn_update_after_current_process_exits(installer_path: str, pid: Optional[int] = None) -> None:
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
    `DETACHED_PROCESS`."""
    if pid is None:
        pid = os.getpid()
    install_cmd = launch_silent_install_and_get_command(installer_path)
    escaped_path = install_cmd[0].replace("'", "''")
    args_literal = ",".join(f"'{a}'" for a in install_cmd[1:])
    ps_script = (
        f"Wait-Process -Id {pid} -ErrorAction SilentlyContinue; "
        f"Start-Process -FilePath '{escaped_path}' -ArgumentList {args_literal}"
    )
    command = ["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", ps_script]
    kwargs = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    subprocess.Popen(
        command, close_fds=True,
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        **kwargs)
