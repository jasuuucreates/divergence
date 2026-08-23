#!/bin/sh
# Put docker on PATH, portably. Source this; do not execute it.
#
# On Linux and macOS docker is already on PATH and this is a no-op. On Windows, Docker Desktop
# installs PER-USER into %LOCALAPPDATA%\Programs\DockerDesktop and does NOT add itself to the system
# PATH, so `docker` is simply absent from a fresh Git Bash shell. Hardcoding one developer's home
# directory (which is what this used to do) makes every script unrunnable by anyone else.
#
# MSYS_NO_PATHCONV stops Git Bash rewriting container-side absolute paths like /var/www/html into
# C:/Program Files/Git/var/www/html before handing them to docker.exe.

if ! command -v docker >/dev/null 2>&1; then
  for d in \
    "$LOCALAPPDATA/Programs/DockerDesktop/resources/bin" \
    "$HOME/AppData/Local/Programs/DockerDesktop/resources/bin" \
    "/c/Program Files/Docker/Docker/resources/bin" \
    "/usr/local/bin" "/opt/homebrew/bin"
  do
    if [ -x "$d/docker" ] || [ -x "$d/docker.exe" ]; then
      PATH="$d:$PATH"; export PATH; break
    fi
  done
fi

MSYS_NO_PATHCONV=1;  export MSYS_NO_PATHCONV
MSYS2_ARG_CONV_EXCL='*'; export MSYS2_ARG_CONV_EXCL

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found on PATH or in any known install location." >&2
  echo "  Windows: Docker Desktop installs per-user and does not add itself to PATH." >&2
  exit 1
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker is installed but the engine is not responding." >&2
  echo "  Start Docker Desktop and wait for it to report 'Engine running', then retry." >&2
  exit 1
fi
