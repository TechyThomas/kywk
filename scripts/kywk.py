"""Dispatch Kywk task groups and update the installed release binaries."""

import argparse
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


REPOSITORY = "TechyThomas/kywk"
EXECUTABLES = ("kywk", "kywk-php", "kywk-git")


def _release_asset_name():
    system = platform.system().lower()
    if system == "darwin":
        system = "macos"
    elif system == "windows":
        system = "windows"
    elif system == "linux":
        system = "linux"
    else:
        raise RuntimeError("Automatic updates are not supported on {}".format(platform.system()))

    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64", "x64"):
        architecture = "x86_64"
    elif machine in ("aarch64", "arm64"):
        architecture = "aarch64"
    else:
        raise RuntimeError("Automatic updates are not supported on {}".format(platform.machine()))
    return "kywk-{}-{}.zip".format(system, architecture)


def _download_latest_release():
    asset_name = _release_asset_name()
    request = urllib.request.Request(
        "https://api.github.com/repos/{}/releases/latest".format(REPOSITORY),
        headers={"Accept": "application/vnd.github+json", "User-Agent": "kywk-updater"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            release = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise RuntimeError("Could not check GitHub Releases: {}".format(error))

    asset = next((item for item in release.get("assets", []) if item.get("name") == asset_name), None)
    if asset is None:
        raise RuntimeError("Latest release has no binary archive for {}".format(asset_name))
    request = urllib.request.Request(
        asset["browser_download_url"], headers={"User-Agent": "kywk-updater"}
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return release.get("tag_name", "latest"), response.read()
    except (urllib.error.URLError, TimeoutError) as error:
        raise RuntimeError("Could not download {}: {}".format(asset_name, error))


def _extract_release(archive_data, destination, windows):
    expected = {name + (".exe" if windows else "") for name in EXECUTABLES}
    try:
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            names = set(archive.namelist())
            if not expected.issubset(names):
                raise RuntimeError("Release archive is missing one or more Kywk executables")
            for name in expected:
                info = archive.getinfo(name)
                if info.is_dir():
                    raise RuntimeError("Release archive contains an invalid executable entry")
                (destination / name).write_bytes(archive.read(info))
    except zipfile.BadZipFile as error:
        raise RuntimeError("Downloaded release archive is invalid: {}".format(error))
    if not windows:
        for name in expected:
            path = destination / name
            path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return expected


def _update():
    if not getattr(sys, "frozen", False):
        raise RuntimeError("--update is available in downloaded release binaries only")

    install_dir = Path(sys.executable).resolve().parent
    windows = platform.system() == "Windows"
    suffix = ".exe" if windows else ""
    tag, archive_data = _download_latest_release()
    staging = Path(tempfile.mkdtemp(prefix="kywk-update-"))
    try:
        expected = _extract_release(archive_data, staging, windows)
        targets = [install_dir / name for name in expected]
        if any(not target.exists() for target in targets):
            raise RuntimeError("All Kywk release executables must be in the same directory")

        if windows:
            # Windows locks a running executable. A detached PowerShell process waits
            # for this process to exit before replacing the three files.
            script = (
                "Start-Sleep -Seconds 2; "
                "while (Get-Process -Id {pid} -ErrorAction SilentlyContinue) "
                "{{ Start-Sleep -Milliseconds 250 }}; "
                "$ErrorActionPreference = 'Stop'; "
                "{copy_commands}; "
                "Remove-Item -LiteralPath '{staging}' -Recurse -Force"
            ).format(
                pid=os.getpid(),
                staging=str(staging).replace("'", "''"),
                copy_commands=" ".join(
                    "Copy-Item -LiteralPath '{}' -Destination '{}' -Force;".format(
                        str(staging / (name + suffix)).replace("'", "''"),
                        str(install_dir / (name + suffix)).replace("'", "''"),
                    )
                    for name in EXECUTABLES
                ),
            )
            creationflags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(
                subprocess, "CREATE_NEW_PROCESS_GROUP", 0
            )
            subprocess.Popen(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                creationflags=creationflags,
            )
            print("Downloaded Kywk {}. The update will finish after this process exits.".format(tag))
            return 0

        for name in expected:
            os.replace(staging / name, install_dir / name)
        print("Updated Kywk to {}.".format(tag))
        return 0
    finally:
        if not windows:
            shutil.rmtree(staging, ignore_errors=True)


def main():
    parser = argparse.ArgumentParser(
        prog="kywk",
        description="Run a Kywk task group or update the release binaries.",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--php", action="store_true", help="run kywk-php")
    group.add_argument("--git", action="store_true", help="run kywk-git")
    group.add_argument("--update", action="store_true", help="download the latest release for this platform")
    args, remainder = parser.parse_known_args()

    if args.update:
        try:
            return _update()
        except (OSError, RuntimeError, ValueError) as error:
            print("kywk: {}".format(error), file=sys.stderr)
            return 1

    executable = "kywk-php" if args.php else "kywk-git"
    path = shutil.which(executable)
    if path is None:
        print("kywk: required executable {!r} was not found on PATH".format(executable), file=sys.stderr)
        return 127
    return subprocess.call([path] + remainder)


if __name__ == "__main__":
    sys.exit(main())
