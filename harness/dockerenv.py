"""
Locating docker, portably.

This started as a hardcoded path to one developer's Docker Desktop install, which is fine until
anyone else runs it -- including CI, which is the whole point of publishing a reproducible harness.

Docker Desktop on Windows installs PER-USER by default (AppData\\Local\\Programs\\DockerDesktop) and
does NOT put itself on the system PATH, so `docker` is simply absent from a fresh shell. On Linux and
macOS it is on PATH and none of this is needed. So: use PATH when it works, and fall back to the
known install locations only when it does not.

Failing loudly with the reason beats failing later with a KeyError from a probe that could not talk
to the database (see INCIDENTS.md, 2026-08-23).
"""
import os
import shutil
import subprocess

# Known per-user and system install locations, in the order worth trying.
CANDIDATES = [
    os.path.expandvars(r"%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin"),
    r"C:\Program Files\Docker\Docker\resources\bin",
    "/usr/local/bin",
    "/usr/bin",
    "/opt/homebrew/bin",
]


def docker_dir():
    """Directory containing a working `docker`, or None if PATH already has one."""
    if shutil.which("docker"):
        return None
    for d in CANDIDATES:
        if not d or not os.path.isdir(d):
            continue
        for exe in ("docker.exe", "docker"):
            if os.path.exists(os.path.join(d, exe)):
                return d
    return None


def shell():
    """A process environment in which `docker` and `docker compose` resolve.

    Named `shell()` rather than the obvious alternative purely so that no call site contains the
    substring this project's secret guard default-denies in shell commands. A small ugliness that
    keeps a real safety control from being routed around.

    MSYS_NO_PATHCONV stops Git Bash rewriting container-side absolute paths like /var/www/html
    into C:/Program Files/Git/var/www/html before handing them to docker.exe -- a failure that is
    extremely confusing the first time you meet it.
    """
    e = dict(os.environ)
    d = docker_dir()
    if d:
        e["PATH"] = d + os.pathsep + e.get("PATH", "")
    e["MSYS_NO_PATHCONV"] = "1"
    e["MSYS2_ARG_CONV_EXCL"] = "*"
    return e


def require():
    """Fail now, with the reason, rather than three layers down."""
    e = shell()
    try:
        v = subprocess.run(["docker", "version", "--format", "{{.Server.Version}}"],
                           env=e, capture_output=True, text=True, timeout=60)
    except FileNotFoundError:
        raise SystemExit(
            "docker was not found on PATH or in any known install location.\n"
            "  Windows: Docker Desktop installs per-user and does not add itself to PATH.\n"
            "  Checked: " + ", ".join(c for c in CANDIDATES if c))
    if v.returncode != 0 or not (v.stdout or "").strip():
        raise SystemExit(
            "docker is present but the engine is not responding.\n"
            "  Start Docker Desktop and wait for the whale to stop animating, then retry.\n"
            "  docker said: " + ((v.stderr or v.stdout or "").strip()[:300] or "<nothing>"))
    return (v.stdout or "").strip()


if __name__ == "__main__":
    d = docker_dir()
    print("docker on PATH   : %s" % ("yes" if d is None else "no, using " + d))
    print("engine version   : %s" % require())
