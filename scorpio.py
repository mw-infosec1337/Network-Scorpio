#!/usr/bin/env python3
"""
Network Scorpio — terminal network toolkit.
Copyright © Mohamed W Abdelwahed.

Supported platforms (Python 3.9+ required):
  • Windows 10 / 11 / 11 Pro / 11 Home / Server (all editions)
  • macOS 10.14 Mojave through newest macOS / Mac OS X releases
  • Linux: all major distros (Ubuntu, Debian, Kali, Fedora, Arch, openSUSE,
    Alpine, Gentoo, Void, Mint, Pop!, Manjaro, RHEL, CentOS, SteamOS, WSL, …)
  • BSD: FreeBSD, OpenBSD, NetBSD, and generic Unix-like systems

Optional: nmap (auto-install offered on first run via your package manager).
"""

from __future__ import annotations

import concurrent.futures
import importlib
import ipaddress
import json
import os
import platform
import random
import re
import shutil
import socket
import struct
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable, TypeVar

_T = TypeVar("_T")

# Filled by _load_python_deps() after bootstrap (see ensure_environment).
speedtest: Any = None
psutil: Any = None

PYTHON_PACKAGES: tuple[tuple[str, str], ...] = (
    ("speedtest-cli", "speedtest"),
    ("colorama", "colorama"),
    ("psutil", "psutil"),
)

MIN_PYTHON = (3, 9)
_FALLBACK_REQUIREMENTS = "speedtest-cli>=2.1.3\ncolorama>=0.4.6\npsutil>=5.9.0\n"

TOOL_NAME = "Network Scorpio"
AUTHOR = "Mohamed W Abdelwahed"
COPYRIGHT = f"© {AUTHOR}"

# Raw logo lines (ANSI applied at render time).
CYBER_LOGO_LINES: tuple[str, ...] = (
    "╔══════════════════════════════════════════════════════════╗",
    "║ ▓▒░  N E T W O R K   S C O R P I O  ░▒▓  :: NET_OPS_ARMED ║",
    "╚══════════════════════════════════════════════════════════╝",
    "           ╱╲      ╔════════════════════════════╗",
    "          ╱▓▓╲     ║  SCORPIO // INTRUSION_KIT   ║",
    "         ╱████╲    ╚════════════════════════════╝",
    "        ◢██████◣   ┌────────────────────────────┐",
    "          ╲██╱     │ XOR  AES  TLS  DNS  LAN  │",
    "           ╲╱      └────────────────────────────┘",
    "  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
    "   >> ENCRYPTED_UPLINK // HANDSHAKE_OK // NODE_ONLINE",
    "   >> root@network-scorpio:~# _",
)

MATRIX_CHARS = "01アイウエカキクケコ▓▒░█"
GLITCH_CHARS = "@#$%&*!?/\\|<>[]{}~^"

ANSI_BOLD = "\033[1m"
ANSI_DIM = "\033[2m"
ANSI_GREEN = "\033[32m"
ANSI_CYAN = "\033[36m"
ANSI_YELLOW = "\033[33m"
ANSI_MAGENTA = "\033[35m"
ANSI_BRIGHT_GREEN = "\033[92m"
ANSI_BRIGHT_CYAN = "\033[96m"
ANSI_BRIGHT_MAGENTA = "\033[95m"
ANSI_RESET = "\033[0m"


def _use_color() -> bool:
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def bold(s: str) -> str:
    return f"{ANSI_BOLD}{s}{ANSI_RESET}" if _use_color() else s


def dim(s: str) -> str:
    return f"{ANSI_DIM}{s}{ANSI_RESET}" if _use_color() else s


def green(s: str) -> str:
    return f"{ANSI_GREEN}{s}{ANSI_RESET}" if _use_color() else s


def cyan(s: str) -> str:
    return f"{ANSI_CYAN}{s}{ANSI_RESET}" if _use_color() else s


def yellow(s: str) -> str:
    return f"{ANSI_YELLOW}{s}{ANSI_RESET}" if _use_color() else s


def _script_dir() -> Path:
    return Path(__file__).resolve().parent


def _platform_family() -> str:
    p = sys.platform
    if p == "win32":
        return "windows"
    if p == "darwin":
        return "darwin"
    if p.startswith("freebsd"):
        return "freebsd"
    if p.startswith("openbsd"):
        return "openbsd"
    if p.startswith("netbsd"):
        return "netbsd"
    if p.startswith("linux"):
        return "linux"
    return "unix"


def _is_wsl() -> bool:
    if _platform_family() != "linux":
        return False
    try:
        with open("/proc/version", encoding="utf-8", errors="ignore") as f:
            return "microsoft" in f.read().lower()
    except OSError:
        return False


def _read_os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    for path in ("/etc/os-release", "/usr/lib/os-release"):
        try:
            with open(path, encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, val = line.split("=", 1)
                    data[key] = val.strip().strip('"').strip("'")
            if data:
                return data
        except OSError:
            continue
    return data


def _windows_label() -> str:
    product = ""
    try:
        import winreg

        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        )
        try:
            product = str(winreg.QueryValueEx(key, "ProductName")[0]).strip()
        except OSError:
            pass
        winreg.CloseKey(key)
    except OSError:
        pass
    build = sys.getwindowsversion().build
    if product:
        return f"{product} (build {build})"
    if build >= 22000:
        return f"Windows 11 (build {build})"
    ver = sys.getwindowsversion()
    return f"Windows {ver.major}.{ver.minor} (build {build})"


def _macos_label() -> str:
    ver = platform.mac_ver()[0]
    if ver:
        return f"macOS {ver}"
    return "macOS"


def _linux_label() -> str:
    rel = _read_os_release()
    pretty = rel.get("PRETTY_NAME") or rel.get("NAME") or "Linux"
    if _is_wsl():
        return f"{pretty} (WSL)"
    return pretty


def _os_label() -> str:
    fam = _platform_family()
    if fam == "windows":
        return _windows_label()
    if fam == "darwin":
        return _macos_label()
    if fam == "linux":
        return _linux_label()
    if fam == "freebsd":
        return f"FreeBSD {platform.release()}".strip()
    if fam == "openbsd":
        return f"OpenBSD {platform.release()}".strip()
    if fam == "netbsd":
        return f"NetBSD {platform.release()}".strip()
    return f"Unix ({sys.platform})"


# (package_manager_binary, install_prefix_without_packages)
_LINUX_PACKAGE_MANAGERS: tuple[tuple[str, list[str]], ...] = (
    ("apt-get", ["sudo", "apt-get", "install", "-y"]),
    ("aptitude", ["sudo", "aptitude", "install", "-y"]),
    ("dnf", ["sudo", "dnf", "install", "-y"]),
    ("yum", ["sudo", "yum", "install", "-y"]),
    ("pacman", ["sudo", "pacman", "-S", "--noconfirm", "--needed"]),
    ("zypper", ["sudo", "zypper", "install", "-y"]),
    ("apk", ["sudo", "apk", "add"]),
    ("xbps-install", ["sudo", "xbps-install", "-y"]),
    ("emerge", ["sudo", "emerge", "--ask=n"]),
    ("pkg", ["sudo", "pkg", "install", "-y"]),
    ("swupd", ["sudo", "swupd", "install"]),
    ("eopkg", ["sudo", "eopkg", "install", "-y"]),
    ("opkg", ["sudo", "opkg", "install"]),
    ("snap", ["sudo", "snap", "install"]),
)


def _nmap_packages_for_pm(pm: str) -> list[str]:
    if pm == "emerge":
        return ["net-analyzer/nmap"]
    return ["nmap"]


def _pip_packages_for_pm(pm: str) -> list[str]:
    if pm == "pacman":
        return ["python-pip", "python-virtualenv"]
    if pm == "apk":
        return ["py3-pip", "py3-virtualenv"]
    if pm == "emerge":
        return ["dev-python/pip", "virtualenv"]
    if pm in ("dnf", "yum", "zypper"):
        return ["python3-pip", "python3-virtualenv"]
    return ["python3-pip", "python3-venv"]


def _check_python_version() -> None:
    if sys.version_info < MIN_PYTHON:
        need = f"{MIN_PYTHON[0]}.{MIN_PYTHON[1]}"
        have = f"{sys.version_info.major}.{sys.version_info.minor}"
        print(
            yellow(
                f"{TOOL_NAME} requires Python {need}+ (this interpreter is {have})."
            )
        )
        sys.exit(1)


def _in_venv() -> bool:
    if hasattr(sys, "real_prefix"):
        return True
    return sys.prefix != getattr(sys, "base_prefix", sys.prefix)


def _venv_python_path() -> Path:
    base = _script_dir() / ".venv"
    if _platform_family() == "windows":
        return base / "Scripts" / "python.exe"
    return base / "bin" / "python"


def _run_cmd(
    cmd: list[str],
    *,
    capture: bool = False,
    timeout: float | None = None,
    check: bool = False,
) -> subprocess.CompletedProcess[str]:
    kwargs: dict[str, Any] = {
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, check=check, **kwargs)


def _missing_python_imports() -> list[tuple[str, str]]:
    missing: list[tuple[str, str]] = []
    for pip_name, import_name in PYTHON_PACKAGES:
        try:
            __import__(import_name)
        except ImportError:
            missing.append((pip_name, import_name))
    return missing


def _load_python_deps() -> None:
    global speedtest, psutil
    import speedtest as _speedtest
    import psutil as _psutil
    from colorama import init as colorama_init

    speedtest = _speedtest
    psutil = _psutil
    colorama_init()


def _ask_yes_no(prompt: str, default_yes: bool = True) -> bool:
    hint = "[Y/n]" if default_yes else "[y/N]"
    try:
        raw = input(f"{prompt} {hint} ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    if not raw:
        return default_yes
    return raw in ("y", "yes")


def _requirements_file() -> Path:
    req = _script_dir() / "requirements.txt"
    if not req.is_file():
        req.write_text(_FALLBACK_REQUIREMENTS, encoding="utf-8")
    return req


def _ensure_pip() -> bool:
    try:
        r = _run_cmd(
            [sys.executable, "-m", "pip", "--version"],
            capture=True,
            timeout=30,
        )
        if r.returncode == 0:
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    print(dim("  → bootstrapping pip (ensurepip)…"))
    try:
        r = _run_cmd(
            [sys.executable, "-m", "ensurepip", "--upgrade"],
            timeout=120,
        )
        if r.returncode == 0:
            return True
    except (OSError, subprocess.TimeoutExpired):
        pass
    if _platform_family() == "linux":
        for pm, prefix in _LINUX_PACKAGE_MANAGERS:
            if not shutil.which(pm) or pm == "snap":
                continue
            pkgs = _pip_packages_for_pm(pm)
            cmd = prefix + pkgs
            print(dim(f"  → trying pip via {pm}: {' '.join(cmd)}"))
            try:
                r = _run_cmd(cmd, timeout=300)
                if r.returncode == 0:
                    return _run_cmd(
                        [sys.executable, "-m", "pip", "--version"],
                        capture=True,
                        timeout=30,
                    ).returncode == 0
            except (OSError, subprocess.TimeoutExpired):
                continue
    return False


def _pip_install_packages(pip_names: list[str], *, python_exe: str | None = None) -> bool:
    exe = python_exe or sys.executable
    if python_exe is None and not _ensure_pip():
        print(yellow("pip is not available for this Python."))
        return False
    req = _requirements_file()
    base = [exe, "-m", "pip", "install", "--upgrade"]
    if len(pip_names) == len(PYTHON_PACKAGES):
        targets: list[str] = ["-r", str(req)]
    else:
        targets = list(pip_names)

    strategies: list[list[str]] = [[]]
    if _platform_family() == "windows":
        strategies.append(["--user"])
    else:
        strategies.extend([["--user"], ["--break-system-packages"]])

    for extra in strategies:
        cmd = base + extra + targets
        print(dim(f"  → {' '.join(cmd)}"))
        try:
            r = _run_cmd(cmd, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0:
            return True
    return False


def _bootstrap_project_venv() -> None:
    """Create .venv next to scorpio.py, install deps, restart with that Python."""
    if _in_venv():
        return
    venv_dir = _script_dir() / ".venv"
    vpy = _venv_python_path()
    print()
    print(dim("  → creating local .venv (portable, no system Python changes)…"))
    try:
        _run_cmd(
            [sys.executable, "-m", "venv", str(venv_dir)],
            timeout=180,
        )
    except (OSError, subprocess.TimeoutExpired):
        return
    if not vpy.is_file():
        print(yellow("Could not create .venv (is python3-venv installed?)."))
        return
    if not _pip_install_packages(
        [p for p, _ in PYTHON_PACKAGES], python_exe=str(vpy)
    ):
        return
    print(green("Environment ready — restarting with local .venv…"))
    time.sleep(0.5)
    script = str(Path(__file__).resolve())
    os.execv(str(vpy), [str(vpy), script, *sys.argv[1:]])


def _install_python_dependencies(missing: list[tuple[str, str]]) -> bool:
    names = [p for p, _ in missing]
    print()
    print("Installing Python packages…")
    if not _pip_install_packages(names):
        print(yellow("System install blocked — trying local .venv instead…"))
        _bootstrap_project_venv()
        print(
            yellow(
                "Automatic install failed. Try manually:\n"
                f"  {sys.executable} -m pip install -r requirements.txt\n"
                "Or:\n"
                f"  {sys.executable} -m venv .venv && "
                f"{_venv_python_path()} -m pip install -r requirements.txt"
            )
        )
        return False
    for _, import_name in missing:
        sys.modules.pop(import_name, None)
    importlib.invalidate_caches()
    try:
        _load_python_deps()
    except ImportError as e:
        print(yellow(f"Packages installed but import failed: {e}"))
        return False
    still = _missing_python_imports()
    if still:
        print(yellow("Still missing: " + ", ".join(p for p, _ in still)))
        return False
    print(green("Python packages ready."))
    return True


def _nmap_present() -> bool:
    return shutil.which("nmap") is not None


def _install_nmap_system() -> bool:
    if _nmap_present():
        return True

    fam = _platform_family()
    attempts: list[tuple[str, list[str]]] = []

    if fam == "windows":
        if shutil.which("winget"):
            attempts.append(
                (
                    "winget",
                    [
                        "winget",
                        "install",
                        "-e",
                        "--id",
                        "Insecure.Nmap",
                        "--accept-package-agreements",
                        "--accept-source-agreements",
                    ],
                )
            )
        if shutil.which("choco"):
            attempts.append(("choco", ["choco", "install", "nmap", "-y"]))
    elif fam == "darwin":
        if shutil.which("brew"):
            attempts.append(("Homebrew", ["brew", "install", "nmap"]))
        if shutil.which("port"):
            attempts.append(("MacPorts", ["sudo", "port", "install", "nmap"]))
    elif fam == "linux":
        for pm, prefix in _LINUX_PACKAGE_MANAGERS:
            if not shutil.which(pm):
                continue
            attempts.append((pm, prefix + _nmap_packages_for_pm(pm)))
    elif fam == "freebsd":
        if shutil.which("pkg"):
            attempts.append(("pkg", ["sudo", "pkg", "install", "-y", "nmap"]))
    elif fam == "openbsd":
        if shutil.which("pkg_add"):
            attempts.append(("pkg_add", ["pkg_add", "nmap"]))
    elif fam == "netbsd":
        if shutil.which("pkgin"):
            attempts.append(("pkgin", ["pkgin", "-y", "install", "nmap"]))

    if not attempts:
        print(
            dim(
                "No supported package manager found for nmap. "
                "Install from https://nmap.org/download.html"
            )
        )
        return False

    for label, cmd in attempts:
        print(dim(f"  → {label}: {' '.join(cmd)}"))
        try:
            r = _run_cmd(cmd, timeout=900)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0 and _nmap_present():
            print(green("nmap installed."))
            return True

    print(
        dim(
            "Could not install nmap automatically (admin/sudo may be required). "
            "Option 2 works without it but is slower."
        )
    )
    return False


def ensure_environment() -> None:
    """Detect OS, offer Y/N install for Python libs + nmap, then load imports."""
    _check_python_version()
    os_name = _os_label()
    py_missing = _missing_python_imports()
    nmap_missing = not _nmap_present()

    if not py_missing and not nmap_missing:
        _load_python_deps()
        return

    print()
    print(bold(f"{TOOL_NAME} — setup check"))
    print(dim(f"Detected OS: {os_name}"))
    print(
        dim(
            "Supports: Windows 11/10, all macOS, all Linux distros, BSD — Python 3.9+"
        )
    )
    print(dim(f"Python: {sys.executable}"))
    if _in_venv():
        print(dim("Environment: virtualenv / .venv"))
    print()

    if py_missing:
        print(yellow("Missing Python libraries:"))
        for pip_name, import_name in py_missing:
            print(dim(f"  • {pip_name}  (import: {import_name})"))
    else:
        print(green("Python libraries: OK"))

    if nmap_missing:
        print(
            yellow(
                "Missing system tool: nmap  "
                "(better network scan in option 2)"
            )
        )
    else:
        print(green("nmap: OK"))

    print()
    if not _ask_yes_no("Install missing components now?", default_yes=True):
        print()
        if py_missing:
            print(
                yellow(
                    "Cannot start without Python libraries. "
                    "Run again and choose Y, or run:\n"
                    f"  {sys.executable} -m pip install -r requirements.txt"
                )
            )
            sys.exit(1)
        _load_python_deps()
        if nmap_missing:
            print(dim("Continuing without nmap (limited scan features)."))
        return

    if py_missing:
        if not _install_python_dependencies(py_missing):
            sys.exit(1)
    else:
        _load_python_deps()

    if nmap_missing:
        print()
        if _ask_yes_no(
            "Install nmap now? (may ask for admin/sudo password)",
            default_yes=True,
        ):
            _install_nmap_system()
        elif not _nmap_present():
            print(dim("Skipping nmap — option 2 will use ping-only discovery."))

    if speedtest is None or psutil is None:
        _load_python_deps()

    print()


def _print_done() -> None:
    print(green(bold("DONE !")))


def _read_char_raw() -> str:
    """Read one keypress (TTY). Esc returns '\\x1b'."""
    if not sys.stdin.isatty():
        return "\n"
    if _platform_family() == "windows":
        import msvcrt

        b = msvcrt.getch()
        if b in (b"\x00", b"\xe0"):
            msvcrt.getch()
            return ""
        try:
            return b.decode("utf-8")
        except UnicodeDecodeError:
            return ""
    try:
        import termios
        import tty
    except ImportError:
        return "\n"

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            import select

            if select.select([sys.stdin], [], [], 0.03)[0]:
                sys.stdin.read(2)
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _post_done_prompt() -> str:
    """
    After DONE ! — only Esc (main menu) or type exit (quit).
    Returns 'menu' or 'exit'.
    """
    print()
    print(dim("  Esc  → back to main menu"))
    print(dim(f"  exit → quit {TOOL_NAME}"))
    print()

    if not sys.stdin.isatty():
        line = input(dim("Press Enter for menu, or type exit: ")).strip().lower()
        return "exit" if line in ("exit", "quit", "q") else "menu"

    print(dim("> "), end="", flush=True)
    buf = ""
    while True:
        try:
            ch = _read_char_raw()
        except (EOFError, KeyboardInterrupt):
            print()
            return "menu"
        if ch == "\x1b":
            print()
            return "menu"
        if ch in ("\r", "\n"):
            print()
            if buf.strip().lower() in ("exit", "quit", "q"):
                return "exit"
            return "menu"
        if ch in ("\x7f", "\b"):
            if buf:
                buf = buf[:-1]
                sys.stdout.write("\b \b")
                sys.stdout.flush()
            continue
        if len(ch) == 1 and ch.isprintable():
            buf += ch
            sys.stdout.write(ch)
            sys.stdout.flush()
            if buf.lower() == "exit":
                print()
                return "exit"


def _clear_status_line() -> None:
    w = min(120, shutil.get_terminal_size(fallback=(100, 24)).columns)
    sys.stdout.write("\r" + " " * w + "\r")
    sys.stdout.flush()


def _run_with_spinner(message: str, func: Callable[[], _T]) -> _T:
    """Run a blocking call while showing a spinner (nmap/speedtest prep can be silent)."""
    stop = threading.Event()
    result: list[_T | BaseException | None] = [None]

    def worker() -> None:
        try:
            result[0] = func()
        except BaseException as e:
            result[0] = e

    def animate() -> None:
        frames = "|/-\\"
        i = 0
        while not stop.wait(0.09):
            ch = frames[i % len(frames)]
            sys.stdout.write(f"\r{dim(f'{ch}  {message}')}")
            sys.stdout.flush()
            i += 1

    wth = threading.Thread(target=worker, daemon=False)
    anim = threading.Thread(target=animate, daemon=True)
    anim.start()
    wth.start()
    try:
        wth.join()
    finally:
        stop.set()
        anim.join(timeout=1.0)
        _clear_status_line()
    out = result[0]
    if isinstance(out, BaseException):
        raise out
    return out  # type: ignore[return-value]


def clear_screen() -> None:
    if sys.platform == "win32":
        os_module = __import__("os")
        os_module.system("cls")
    else:
        sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()


def _logo_palette() -> list[str]:
    return [
        ANSI_BRIGHT_CYAN,
        ANSI_BRIGHT_GREEN,
        ANSI_CYAN,
        ANSI_GREEN,
        ANSI_BRIGHT_MAGENTA,
        ANSI_MAGENTA,
    ]


def _colorize_logo_line(line: str, line_idx: int, pulse: int = 0) -> str:
    if not _use_color():
        return line
    colors = _logo_palette()
    out: list[str] = []
    for col, ch in enumerate(line):
        if ch == " ":
            out.append(ch)
            continue
        ci = (line_idx + col + pulse) % len(colors)
        out.append(f"{colors[ci]}{ch}{ANSI_RESET}")
    return "".join(out)


def _glitch_line(line: str, intensity: float) -> str:
    if not _use_color() or intensity <= 0:
        return line
    out: list[str] = []
    for ch in line:
        if ch == " " or random.random() > intensity:
            out.append(ch)
        else:
            g = random.choice(GLITCH_CHARS)
            c = random.choice(
                [ANSI_BRIGHT_GREEN, ANSI_BRIGHT_CYAN, ANSI_YELLOW, ANSI_BRIGHT_MAGENTA]
            )
            out.append(f"{c}{g}{ANSI_RESET}")
    return "".join(out)


def _matrix_rain_frame(width: int, height: int, tick: int) -> list[str]:
    rows: list[str] = []
    for r in range(height):
        parts: list[str] = []
        for c in range(width):
            if random.random() < 0.12:
                ch = random.choice(MATRIX_CHARS)
                if _use_color():
                    col = random.choice(
                        [ANSI_GREEN, ANSI_BRIGHT_GREEN, ANSI_CYAN, ANSI_DIM]
                    )
                    parts.append(f"{col}{ch}{ANSI_RESET}")
                else:
                    parts.append(ch)
            else:
                parts.append(" ")
        rows.append("".join(parts))
    if _use_color() and tick % 4 == 0:
        tag = ">> INITIALIZING NETWORK SCORPIO KERNEL..."
        pad = max(0, (width - len(tag)) // 2)
        rows.append(" " * pad + f"{ANSI_DIM}{tag}{ANSI_RESET}")
    return rows


def _print_static_cyber_logo() -> None:
    term_w = shutil.get_terminal_size(fallback=(100, 24)).columns
    for i, line in enumerate(CYBER_LOGO_LINES):
        if len(line) > term_w:
            line = line[: max(0, term_w - 1)] + "…"
        print(_colorize_logo_line(line, i))
    print()
    pad = max(0, (term_w - len(COPYRIGHT)) // 2)
    print(dim(" " * pad + bold(COPYRIGHT)))
    print()


def play_animated_logo() -> None:
    """Premium hacker-style boot animation; static fallback if not a TTY."""
    if not sys.stdout.isatty():
        _print_static_cyber_logo()
        return

    term_w = shutil.get_terminal_size(fallback=(100, 24)).columns
    logo = [
        ln if len(ln) <= term_w else ln[: max(0, term_w - 1)] + "…"
        for ln in CYBER_LOGO_LINES
    ]

    sys.stdout.write("\033[?25l")
    try:
        rain_h = min(10, max(6, len(logo) - 2))
        rain_w = min(term_w, 72)
        for tick in range(22):
            clear_screen()
            for row in _matrix_rain_frame(rain_w, rain_h, tick):
                print(row)
            time.sleep(0.035)

        for frame in range(28):
            clear_screen()
            intensity = max(0.0, 0.55 - frame * 0.02)
            for i, line in enumerate(logo):
                print(_glitch_line(line, intensity))
            time.sleep(0.04)

        for pulse in range(6):
            clear_screen()
            for i, line in enumerate(logo):
                print(_colorize_logo_line(line, i, pulse))
            time.sleep(0.07)

        for scan in range(-1, len(logo) + 1):
            clear_screen()
            for i, line in enumerate(logo):
                if i == scan:
                    print(f"{ANSI_BRIGHT_GREEN}{ANSI_BOLD}{line}{ANSI_RESET}")
                else:
                    print(_colorize_logo_line(line, i, scan))
            time.sleep(0.045)

        clear_screen()
        for i, line in enumerate(logo):
            print(_colorize_logo_line(line, i))
        print()
        pad = max(0, (term_w - len(COPYRIGHT)) // 2)
        print(dim(" " * pad + bold(COPYRIGHT)))
        print()
        time.sleep(0.12)
    finally:
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()


def print_header() -> None:
    play_animated_logo()


def bits_to_mbps(bits_per_s: float | None) -> float:
    if bits_per_s is None:
        return 0.0
    return bits_per_s / 1_000_000


def make_download_callback(label: str) -> Callable[..., None]:
    last = [0.0]

    def cb(current: int, total: int, **kwargs: object) -> None:
        if kwargs.get("start"):
            return
        if not kwargs.get("end"):
            return
        now = time.monotonic()
        if now - last[0] < 0.12:
            return
        last[0] = now
        pct = min(100, int(100 * (current + 1) / max(1, total)))
        bar_w = 28
        filled = int(bar_w * pct / 100)
        bar = "█" * filled + "░" * (bar_w - filled)
        sys.stdout.write(f"\r{label} [{bar}] {pct:3d}%")
        sys.stdout.flush()

    return cb


def make_upload_callback(label: str) -> Callable[..., None]:
    last = [0.0]

    def cb(current: int, total: int, **kwargs: object) -> None:
        if kwargs.get("start"):
            return
        if not kwargs.get("end"):
            return
        now = time.monotonic()
        if now - last[0] < 0.12:
            return
        last[0] = now
        pct = min(100, int(100 * (current + 1) / max(1, total)))
        bar_w = 28
        filled = int(bar_w * pct / 100)
        bar = "█" * filled + "░" * (bar_w - filled)
        sys.stdout.write(f"\r{label} [{bar}] {pct:3d}%")
        sys.stdout.flush()

    return cb


def run_speed_test() -> None:
    """
    Uses speedtest.net's multi-connection workflow with server-provided
    thread counts (threads=None) for results aligned with their methodology.
    """
    print()
    print(bold("Internet speed test"))
    print(dim("Close heavy downloads/uploads elsewhere for a cleaner reading."))
    print()

    st = speedtest.Speedtest(secure=True)
    _run_with_spinner("Fetching speedtest.net server list…", st.get_servers)
    print(dim("Server list ready."))
    best = _run_with_spinner(
        "Selecting best server by latency…", st.get_best_server
    )
    name = best.get("name", "unknown")
    sponsor = best.get("sponsor", "")
    loc = best.get("country", "")
    ping_ms = best.get("latency")
    print(green(f"Server: {name}"))
    if sponsor:
        print(dim(f"        {sponsor}"))
    if loc:
        print(dim(f"        {loc}"))
    if ping_ms is not None:
        print(dim(f"Latency (ping): {ping_ms:.1f} ms"))
    print()

    print(dim("Download (multi-connection)…"))
    st.download(callback=make_download_callback("Download"))
    print()
    dl = bits_to_mbps(st.results.download)
    print(green(f"Download: {dl:.2f} Mbps"))

    print()
    print(dim("Upload (multi-connection)…"))
    st.upload(callback=make_upload_callback("Upload"), pre_allocate=True)
    print()
    ul = bits_to_mbps(st.results.upload)
    print(green(f"Upload:   {ul:.2f} Mbps"))

    print()
    print(dim("— Results use speedtest.net servers and parallel streams (Ookla-style). —"))
    _print_done()


def _outward_ipv4() -> str | None:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _iter_local_ipv4_networks() -> list[tuple[ipaddress.IPv4Interface, str]]:
    if psutil is None:
        return []
    out: list[tuple[ipaddress.IPv4Interface, str]] = []
    for iface, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family != socket.AF_INET:
                continue
            if not a.address or a.address.startswith("127."):
                continue
            if not a.netmask:
                continue
            try:
                iface_ip = ipaddress.IPv4Interface(f"{a.address}/{a.netmask}")
            except ValueError:
                continue
            if iface_ip.network.is_loopback:
                continue
            if iface_ip.network.prefixlen >= 31:
                continue
            out.append((iface_ip, iface))
    return out


def _pick_scan_network(
    nets: list[tuple[ipaddress.IPv4Interface, str]],
) -> tuple[ipaddress.IPv4Network, str] | None:
    if not nets:
        return None
    outward = _outward_ipv4()
    if outward:
        try:
            o = ipaddress.IPv4Address(outward)
        except ValueError:
            o = None
        if o is not None:
            for iface_ip, iface in nets:
                if o in iface_ip.network:
                    return iface_ip.network, iface
    best = max(nets, key=lambda x: x[0].network.num_addresses)
    return best[0].network, best[1]


_ping_busybox: bool | None = None


def _ping_uses_busybox() -> bool:
    global _ping_busybox
    if _ping_busybox is not None:
        return _ping_busybox
    ping = shutil.which("ping")
    if not ping:
        _ping_busybox = False
        return False
    try:
        r = _run_cmd([ping], capture=True, timeout=3)
        text = (r.stdout or "") + (r.stderr or "")
        _ping_busybox = "busybox" in text.lower()
    except OSError:
        _ping_busybox = False
    return _ping_busybox


def _ping_cmd(ip: str, *, fast: bool = False) -> list[str]:
    fam = _platform_family()
    if fam == "windows":
        ms = "500" if fast else "1500"
        return ["ping", "-n", "1", "-w", ms, ip]
    if fam == "darwin":
        ms = "1000" if fast else "2000"
        return ["ping", "-c", "1", "-W", ms, ip]
    if fam in ("freebsd", "openbsd", "netbsd"):
        sec = "1" if fast else "2"
        return ["ping", "-c", "1", "-t", sec, ip]
    if fam == "linux" and _ping_uses_busybox():
        sec = "1" if fast else "2"
        return ["ping", "-c", "1", "-w", sec, ip]
    sec = "1" if fast else "2"
    return ["ping", "-c", "1", "-W", sec, ip]


def _parse_ping_ttl(stdout: str, stderr: str) -> int | None:
    text = stdout + stderr
    m = re.search(r"(?i)ttl[=:]\s*(\d+)", text)
    if m:
        return int(m.group(1))
    return None


def _parse_ping_rtt(stdout: str, stderr: str) -> float | None:
    text = stdout + stderr
    m = re.search(r"(?i)(?:time[=<])(\d+(?:\.\d+)?)\s*ms", text)
    if m:
        return float(m.group(1))
    return None


def _ping_host(
    ip: str, *, fast: bool = False
) -> tuple[str, bool, int | None, float | None]:
    timeout = 2.5 if fast else 4.0
    try:
        r = _run_cmd(
            _ping_cmd(ip, fast=fast),
            capture=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError):
        return ip, False, None, None
    alive = r.returncode == 0
    out = (r.stdout or "") + (r.stderr or "")
    ttl = _parse_ping_ttl(out, "") if alive else None
    rtt = _parse_ping_rtt(out, "") if alive else None
    return ip, alive, ttl, rtt


def _ttl_hint(ttl: int | None) -> str:
    if ttl is None:
        return "no ICMP TTL (host down or filtered)"
    if ttl > 128:
        return f"ICMP TTL={ttl} — often network gear / uncommon stacks (hop-adjusted; heuristic only)"
    if ttl > 64:
        return f"ICMP TTL={ttl} — commonly Windows-family initial TTL 128 minus hops (heuristic only)"
    return f"ICMP TTL={ttl} — commonly Linux/macOS/iOS initial TTL 64 minus hops (heuristic only)"


def _nmap_available() -> bool:
    return shutil.which("nmap") is not None


def _nmap_parse_hosts_detail(xml_text: str) -> list[dict[str, str]]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []
    hosts: list[dict[str, str]] = []
    for host in root.findall("host"):
        st = host.find("status")
        if st is None or st.get("state") != "up":
            continue
        ip: str | None = None
        mac: str | None = None
        for addr in host.findall("address"):
            atype = addr.get("addrtype")
            if atype == "ipv4":
                ip = addr.get("addr")
            elif atype == "mac":
                mac = addr.get("addr")
        if not ip:
            continue
        hostname: str | None = None
        hn_el = host.find("hostnames")
        if hn_el is not None:
            for hn in hn_el.findall("hostname"):
                name = hn.get("name")
                if name:
                    hostname = name
                    break
        entry: dict[str, str] = {"ip": ip}
        if mac:
            entry["mac"] = mac.lower()
        if hostname:
            entry["hostname"] = hostname
        hosts.append(entry)
    return hosts


def _nmap_parse_fast_ports(xml_text: str) -> dict[str, str]:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return {}
    out: dict[str, list[str]] = {}
    for host in root.findall("host"):
        st = host.find("status")
        if st is None or st.get("state") != "up":
            continue
        ip: str | None = None
        for addr in host.findall("address"):
            if addr.get("addrtype") == "ipv4":
                ip = addr.get("addr")
                break
        if not ip:
            continue
        ports: list[str] = []
        ports_el = host.find("ports")
        if ports_el is not None:
            for p in ports_el.findall("port"):
                state_el = p.find("state")
                if state_el is not None and state_el.get("state") == "open":
                    ports.append(f"{p.get('portid', '')}/{p.get('protocol', 'tcp')}")
        if ports:
            out[ip] = ports
    return {ip: ",".join(ps[:6]) for ip, ps in out.items()}


def _arp_table() -> dict[str, str]:
    table: dict[str, str] = {}
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["arp", "-a"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if r.returncode == 0:
                for m in re.finditer(
                    r"(\d+\.\d+\.\d+\.\d+)\s+([0-9a-f-]{17})",
                    r.stdout,
                    re.I,
                ):
                    table[m.group(1)] = m.group(2).replace("-", ":").lower()
        elif sys.platform == "darwin":
            r = subprocess.run(
                ["arp", "-an"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if r.returncode == 0:
                for m in re.finditer(
                    r"\((\d+\.\d+\.\d+\.\d+)\)\s+at\s+([0-9a-f:]{17})",
                    r.stdout,
                    re.I,
                ):
                    table[m.group(1)] = m.group(2).lower()
        else:
            r = subprocess.run(
                ["ip", "neigh", "show"],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if r.returncode == 0:
                for m in re.finditer(
                    r"(\d+\.\d+\.\d+\.\d+)\s+dev\s+\S+\s+lladdr\s+([0-9a-f:]{17})",
                    r.stdout,
                    re.I,
                ):
                    table[m.group(1)] = m.group(2).lower()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return table


def _nmap_host_discovery(cidr: str) -> list[dict[str, str]] | None:
    if not _nmap_available():
        return None
    net = ipaddress.ip_network(cidr, strict=False)
    timeout = min(120, max(25, 15 + net.num_addresses // 8))
    cmd = [
        "nmap",
        "-sn",
        "-n",
        "-T5",
        "--max-retries",
        "1",
        "--host-timeout",
        "5s",
        "-oX",
        "-",
        cidr,
    ]
    if _platform_family() in ("linux", "freebsd") and net.prefixlen >= 16:
        cmd = [
            "nmap",
            "-sn",
            "-PR",
            "-n",
            "-T5",
            "--max-retries",
            "1",
            "--host-timeout",
            "5s",
            "-oX",
            "-",
            cidr,
        ]
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    hosts = _nmap_parse_hosts_detail(r.stdout)
    if r.returncode != 0 and not hosts:
        return None
    return hosts


def _nmap_batch_fast_ports(ips: list[str]) -> dict[str, str]:
    if not ips or not _nmap_available():
        return {}
    targets = ips[:64]
    try:
        r = subprocess.run(
            [
                "nmap",
                "-F",
                "-n",
                "-T5",
                "--open",
                "--max-retries",
                "1",
                "--host-timeout",
                "12s",
                "-oX",
                "-",
                *targets,
            ],
            capture_output=True,
            text=True,
            timeout=min(180, 20 + 8 * len(targets)),
        )
    except (subprocess.TimeoutExpired, OSError):
        return {}
    if not r.stdout.strip():
        return {}
    return _nmap_parse_fast_ports(r.stdout)


def _ping_sweep(
    network: ipaddress.IPv4Network, *, quiet: bool = False, fast: bool = True
) -> list[dict[str, str]]:
    hosts = [str(h) for h in network.hosts()]
    found: list[dict[str, str]] = []
    workers = min(64, max(16, len(hosts)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(_ping_host, ip, fast=fast): ip for ip in hosts}
        done = 0
        total = len(futs)
        for fut in concurrent.futures.as_completed(futs):
            done += 1
            if not quiet and (done % 40 == 0 or done == total):
                fr = "|/-\\"[done % 4]
                sys.stdout.write(f"\r{dim(f'{fr}  Probing hosts… {done}/{total}')}")
                sys.stdout.flush()
            try:
                ip, alive, _ttl, _rtt = fut.result()
            except Exception:
                continue
            if alive:
                found.append({"ip": ip})
    if not quiet:
        sys.stdout.write("\r" + " " * 60 + "\r")
        sys.stdout.flush()
    found.sort(key=lambda x: ipaddress.IPv4Address(x["ip"]))
    return found


def _discover_live_hosts(
    cidr: str, network: ipaddress.IPv4Network
) -> list[dict[str, str]]:
    if _nmap_available():
        hosts = _nmap_host_discovery(cidr)
        if hosts is not None:
            if hosts:
                for h in hosts:
                    h["_from_nmap"] = True
                return sorted(
                    hosts, key=lambda x: ipaddress.IPv4Address(x["ip"])
                )
            return []
    return _ping_sweep(network, quiet=True, fast=True)


def _ptr_hostname(ip: str) -> str | None:
    try:
        return socket.gethostbyaddr(ip)[0]
    except OSError:
        return None


_OUI_VENDORS: dict[str, str] = {
    "00:0c:29": "VMware", "00:0a:27": "VirtualBox", "00:50:56": "VMware",
    "00:1e:c2": "Apple", "00:1f:5b": "Apple", "00:1f:f3": "Apple",
    "00:23:12": "Apple", "00:25:00": "Apple", "0e:aa:c2": "Apple",
    "14:7d:da": "Apple", "28:cf:e9": "Apple", "3c:22:fb": "Apple",
    "5c:f9:38": "Apple", "7c:d1:c3": "Apple", "a4:83:e7": "Apple",
    "ac:de:48": "Apple", "b8:8d:12": "Apple", "f0:18:98": "Apple",
    "58:96:71": "CommScope", "24:e8:53": "Intel", "b8:27:eb": "Raspberry Pi",
    "dc:a6:32": "Raspberry Pi", "e4:5f:01": "Raspberry Pi",
    "00:14:bf": "Cisco", "00:18:39": "Cisco", "00:1a:a0": "Cisco",
    "00:24:01": "Cisco", "00:26:ca": "Cisco", "00:50:ba": "D-Link",
    "00:1d:0f": "Netgear", "00:24:b2": "Netgear", "a0:04:60": "Netgear",
    "b0:be:76": "TP-Link", "c0:25:e9": "TP-Link", "f4:f2:6d": "TP-Link",
    "00:1a:70": "Samsung", "5c:0a:5b": "Samsung", "b4:79:a7": "Samsung",
    "bc:20:a4": "Samsung", "d0:66:7b": "Samsung", "f8:04:2e": "Samsung",
    "00:15:00": "Intel", "00:1b:21": "Intel", "00:1e:65": "Intel",
    "00:21:6b": "Intel", "3c:97:0e": "Intel", "48:51:b7": "Intel",
    "68:05:ca": "Intel", "84:3a:4b": "Intel", "a4:bf:01": "Intel",
    "b4:b6:86": "Intel", "f8:63:3f": "Intel",
}

_PORT_SERVICE_LABELS: dict[str, str] = {
    "21/tcp": "FTP", "22/tcp": "SSH", "23/tcp": "Telnet", "25/tcp": "SMTP",
    "53/tcp": "DNS", "53/udp": "DNS", "80/tcp": "HTTP", "110/tcp": "POP3",
    "135/tcp": "Windows RPC", "139/tcp": "NetBIOS", "143/tcp": "IMAP",
    "443/tcp": "HTTPS", "445/tcp": "SMB", "993/tcp": "IMAPS", "995/tcp": "POP3S",
    "1433/tcp": "SQL Server", "3306/tcp": "MySQL", "3389/tcp": "RDP",
    "5000/tcp": "AirPlay", "5353/udp": "mDNS", "5900/tcp": "VNC",
    "7070/tcp": "AirPlay", "8080/tcp": "HTTP proxy", "8443/tcp": "HTTPS alt",
}


def _mac_vendor(mac: str) -> str:
    if not mac or mac == "—":
        return "—"
    norm = mac.lower().replace("-", ":")
    if len(norm) < 8:
        return "—"
    prefix = norm[:8]
    if prefix in _OUI_VENDORS:
        return _OUI_VENDORS[prefix]
    try:
        first = int(norm.split(":")[0], 16)
        if first & 0x02:
            return "Private / randomized MAC"
    except ValueError:
        pass
    return "—"


def _host_short_name(hostname: str, ip: str, vendor: str) -> str:
    if hostname and hostname != "—":
        short = hostname.split(".")[0]
        if short and short.lower() not in ("localhost", "unknown"):
            return short
    if vendor and vendor != "—":
        return f"{vendor} device"
    return f"Host .{ip.split('.')[-1]}"


def _format_open_services(ports: str) -> str:
    if not ports or ports == "—":
        return "none detected"
    parts = []
    for item in ports.split(","):
        item = item.strip()
        if not item:
            continue
        label = _PORT_SERVICE_LABELS.get(item, item)
        parts.append(label)
    return ", ".join(parts[:8]) + ("…" if len(parts) > 8 else "")


def _infer_device_type(
    *,
    name: str,
    hostname: str,
    ip: str,
    vendor: str,
    ports: str,
) -> tuple[str, str]:
    h = f"{name} {hostname}".lower()
    port_s = ports or ""

    if any(x in h for x in ("macbook", "imac", "mac-mini", "macpro", "mac ")):
        return "Apple Mac", "Computer"
    if any(x in h for x in ("iphone", "ipad", "ipod")):
        return "Apple iPhone / iPad", "Mobile"
    if "kali" in h or "parrot" in h:
        return "Linux (Kali / security)", "Computer"
    if any(x in h for x in ("ubuntu", "debian", "fedora", "linux", "raspberry")):
        return "Linux system", "Computer"
    if any(x in h for x in ("android", "galaxy", "pixel")):
        return "Android phone / tablet", "Mobile"
    if any(x in h for x in ("windows", "desktop-", "laptop-")):
        return "Windows PC", "Computer"
    if any(
        x in h
        for x in (
            "router", "gateway", "modem", "cr200", "fritz", "netgear",
            "linksys", "mynetworksettings", "arris", "surfboard",
        )
    ):
        return "Router / Gateway", "Network"
    if ip.endswith(".1") and ("80/tcp" in port_s or "443/tcp" in port_s):
        return "Router / Gateway", "Network"
    if "5000/tcp" in port_s or "7070/tcp" in port_s:
        return "Apple Mac / TV", "Computer"
    if "3389/tcp" in port_s or "445/tcp" in port_s:
        return "Windows PC", "Computer"
    if "22/tcp" in port_s and "80/tcp" not in port_s:
        return "Linux / Unix host", "Computer"
    if vendor == "Apple":
        return "Apple device", "Computer"
    if vendor in ("CommScope", "Netgear", "TP-Link", "Cisco", "Cisco-Linksys", "D-Link"):
        return "Network equipment", "Network"
    if vendor == "Samsung":
        return "Samsung device", "Mobile / TV"
    if vendor == "Intel":
        return "PC / laptop", "Computer"
    if vendor == "Raspberry Pi":
        return "Raspberry Pi", "IoT / Computer"
    if vendor == "Private / randomized MAC":
        return "Phone / tablet (privacy MAC)", "Mobile"
    return "Network device", "Unknown"


def _host_highlight_name(name: str) -> str:
    if not _use_color():
        return bold(name)
    return f"{ANSI_BRIGHT_CYAN}{ANSI_BOLD}{name}{ANSI_RESET}"


def _host_highlight_type(dtype: str) -> str:
    if not _use_color():
        return dtype
    return f"{ANSI_BRIGHT_GREEN}{dtype}{ANSI_RESET}"


def _host_build_profile(row: dict[str, str]) -> dict[str, str]:
    mac = row.get("mac", "—")
    hostname = row.get("hostname", "—")
    vendor = _mac_vendor(mac)
    name = _host_short_name(hostname, row["ip"], vendor)
    dtype, role = _infer_device_type(
        name=name,
        hostname=hostname,
        ip=row["ip"],
        vendor=vendor,
        ports=row.get("ports", "—"),
    )
    return {
        "name": name,
        "hostname": hostname,
        "device_type": dtype,
        "role": role,
        "vendor": vendor,
        "services": _format_open_services(row.get("ports", "—")),
    }


def _enrich_one_host(
    entry: dict[str, str],
    arp: dict[str, str],
    ping_cache: dict[str, str],
) -> dict[str, str]:
    ip = entry["ip"]
    if not entry.get("hostname"):
        ptr = _ptr_hostname(ip)
        if ptr:
            entry = {**entry, "hostname": ptr}
    hostname = entry.get("hostname") or "—"
    mac = entry.get("mac") or arp.get(ip) or "—"
    ping = ping_cache.get(ip, "up" if entry.get("_from_nmap") else "—")
    return {
        "ip": ip,
        "hostname": hostname,
        "mac": mac,
        "ping": ping,
        "ports": "—",
    }


def _enrich_hosts_parallel(
    live: list[dict[str, str]], arp: dict[str, str]
) -> list[dict[str, str]]:
    ping_cache: dict[str, str] = {}
    need_ping = [e for e in live if not e.get("_from_nmap")]
    if need_ping:
        workers = min(24, max(4, len(need_ping)))

        def _ping_entry(entry: dict[str, str]) -> tuple[str, bool, int | None, float | None]:
            return _ping_host(entry["ip"], fast=True)

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
            for ip, alive, _ttl, rtt in ex.map(_ping_entry, need_ping):
                if rtt is not None:
                    ping_cache[ip] = f"{rtt:.0f} ms"
                elif alive:
                    ping_cache[ip] = "up"

    rows: list[dict[str, str]] = []
    workers = min(24, max(6, len(live)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [
            ex.submit(_enrich_one_host, e, arp, ping_cache) for e in live
        ]
        for fut in concurrent.futures.as_completed(futs):
            try:
                rows.append(fut.result())
            except Exception:
                pass
    rows.sort(key=lambda x: ipaddress.IPv4Address(x["ip"]))
    return rows


def _print_host_scan_report(rows: list[dict[str, str]], cidr: str) -> None:
    if not rows:
        return
    print()
    print(bold("LAN HOST REPORT"))
    print(dim(f"{cidr}  ·  {len(rows)} device(s) online"))
    print(dim("═" * 50))
    for i, row in enumerate(rows, 1):
        profile = _host_build_profile(row)
        print()
        print(
            f"  {yellow(f'#{i}')}  "
            f"{_host_highlight_name(profile['name'])}  "
            f"{dim('—')}  {_host_highlight_type(profile['device_type'])}"
        )
        print(dim("  " + "─" * 46))
        print(f"  {dim('IP'):<14} {cyan(row['ip'])}")
        if profile["hostname"] != "—":
            print(f"  {dim('Hostname'):<14} {profile['hostname']}")
        print(f"  {dim('Category'):<14} {profile['role']}")
        if profile["vendor"] != "—":
            print(f"  {dim('Manufacturer'):<14} {profile['vendor']}")
        if row["mac"] != "—":
            print(f"  {dim('MAC'):<14} {row['mac']}")
        ping = row.get("ping", "—")
        if ping not in ("—", "up"):
            print(f"  {dim('Latency'):<14} {green(ping)}")
        elif ping == "up":
            print(f"  {dim('Status'):<14} {green('online')}")
        services = profile["services"]
        if services != "none detected":
            print(f"  {dim('Services'):<14} {services}")
    print()


def run_network_host_survey() -> None:
    print()

    if psutil is None:
        print(
            yellow("Missing psutil. Install: pip install psutil"),
            file=sys.stderr,
        )
        _print_done()
        return

    nets = _iter_local_ipv4_networks()
    picked = _pick_scan_network(nets)
    if not picked:
        print(yellow("No LAN found."), file=sys.stderr)
        _print_done()
        return

    network, _iface = picked
    cidr = str(network)

    def _scan_and_profile() -> list[dict[str, str]]:
        live = _discover_live_hosts(cidr, network)
        if not live:
            return []
        arp = _arp_table()
        rows = _enrich_hosts_parallel(live, arp)
        if _nmap_available():
            port_map = _nmap_batch_fast_ports([h["ip"] for h in live])
            for row in rows:
                if port_map.get(row["ip"]):
                    row["ports"] = port_map[row["ip"]]
        return rows

    rows = _run_with_spinner(
        f"Scanning {cidr} and profiling devices…",
        _scan_and_profile,
    )

    if not rows:
        print(yellow("No live hosts found on this LAN."))
        _print_done()
        return

    _print_host_scan_report(rows, cidr)
    _print_done()


def _resolve_target(raw: str) -> str | None:
    text = raw.strip()
    if not text:
        return None
    try:
        return str(ipaddress.ip_address(text))
    except ValueError:
        pass
    try:
        return socket.gethostbyname(text)
    except OSError:
        return None


def _local_ip_on_network(network: ipaddress.IPv4Network) -> str | None:
    outward = _outward_ipv4()
    if outward:
        try:
            if ipaddress.ip_address(outward) in network:
                return outward
        except ValueError:
            pass
    if psutil is None:
        return None
    for _name, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family != socket.AF_INET or not a.address:
                continue
            try:
                if ipaddress.ip_address(a.address) in network:
                    return a.address
            except ValueError:
                continue
    return None


def _ping_multi(
    ip: str, count: int = 6
) -> tuple[int, int, float | None, int | None]:
    """Return (sent, received, avg_ms, loss_percent)."""
    fam = _platform_family()
    if fam == "windows":
        cmd = ["ping", "-n", str(count), "-w", "1000", ip]
    elif fam in ("freebsd", "openbsd", "netbsd"):
        cmd = ["ping", "-c", str(count), "-t", "2", ip]
    elif fam == "linux" and _ping_uses_busybox():
        cmd = ["ping", "-c", str(count), "-w", "2", ip]
    else:
        cmd = ["ping", "-c", str(count), "-W", "2", ip]
    try:
        r = _run_cmd(
            cmd,
            capture=True,
            timeout=count * 3 + 8,
        )
    except (OSError, subprocess.TimeoutExpired):
        return count, 0, None, 100
    out = r.stdout + r.stderr
    sent, recv = count, 0
    m = re.search(r"(\d+)\s+packets transmitted[,\s]+(\d+)\s+received", out, re.I)
    if m:
        sent, recv = int(m.group(1)), int(m.group(2))
    elif sys.platform == "win32":
        m2 = re.search(r"Sent = (\d+).*Received = (\d+)", out, re.I | re.S)
        if m2:
            sent, recv = int(m2.group(1)), int(m2.group(2))
    avg: float | None = None
    mavg = re.search(
        r"(?:round-trip|rtt).*= [\d.]+/([\d.]+)/",
        out,
        re.I,
    )
    if mavg:
        avg = float(mavg.group(1))
    else:
        times = [float(x) for x in re.findall(r"time[=<](\d+(?:\.\d+)?)\s*ms", out, re.I)]
        if times:
            avg = sum(times) / len(times)
    loss = 0 if sent == 0 else int(round(100 * (sent - recv) / sent))
    return sent, recv, avg, loss


def _test_dns_resolution() -> bool:
    try:
        socket.getaddrinfo("google.com", 80, type=socket.SOCK_STREAM)
        return True
    except OSError:
        return False


def _test_internet_reachability() -> bool:
    for target in ("8.8.8.8", "1.1.1.1"):
        _ip, alive, _ttl, _rtt = _ping_host(target, fast=True)
        if alive:
            return True
    return False


def _tcp_probe(ip: str, port: int, timeout: float = 1.2) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def _probe_common_ports(ip: str) -> str:
    ports = [(22, "ssh"), (80, "http"), (443, "https"), (445, "smb"), (3389, "rdp")]
    open_ports: list[str] = []
    for num, label in ports:
        if _tcp_probe(ip, num):
            open_ports.append(label)
    return ", ".join(open_ports) if open_ports else "none detected"


def _traceroute_summary(ip: str) -> str:
    if _platform_family() == "windows":
        cmd = ["tracert", "-d", "-h", "12", ip]
        exe = "tracert"
    elif shutil.which("traceroute"):
        cmd = ["traceroute", "-n", "-w", "2", "-q", "1", "-m", "12", ip]
        exe = "traceroute"
    else:
        return "not available (install traceroute)"
    try:
        r = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=45,
        )
    except (OSError, subprocess.TimeoutExpired):
        return f"{exe} timed out"
    lines = [ln.strip() for ln in (r.stdout or "").splitlines() if ln.strip()]
    hops = [ln for ln in lines if re.search(r"^\s*\d+", ln) or re.search(r"^\d+\s+", ln)]
    if not hops:
        return "no hop data"
    tail = hops[-4:] if len(hops) > 4 else hops
    return " | ".join(tail[:4])


def _troubleshoot_pick_target(
    network: ipaddress.IPv4Network, cidr: str
) -> str | None:
    print()
    print(bold("Locate user PC"))
    print(f"  {yellow('1')}  Enter IP address")
    print(f"  {yellow('2')}  Enter hostname")
    print(f"  {yellow('3')}  Quick LAN scan → pick from list")
    print(f"  {yellow('0')}  Cancel")
    print()
    mode = input(dim("Choice: ")).strip().lower()
    if mode in ("0", "q", "cancel"):
        print(dim("Cancelled."))
        return None
    if mode == "1":
        raw = input(dim("User PC IP: ")).strip()
        return _resolve_target(raw)
    if mode == "2":
        raw = input(dim("User PC hostname: ")).strip()
        return _resolve_target(raw)
    if mode == "3":
        live = _run_with_spinner(
            f"Quick scan {cidr}…",
            lambda: _discover_live_hosts(cidr, network),
        )
        if not live:
            print(yellow("No live hosts found on this LAN."))
            return None
        print()
        print(bold(f"Live hosts ({len(live)}):"))
        for i, h in enumerate(live, 1):
            ip = h["ip"]
            name = h.get("hostname") or ""
            label = f"{ip}  ({name})" if name else ip
            print(f"  {yellow(str(i))}  {label}")
        print()
        pick = input(dim("Pick number or IP: ")).strip()
        if not pick:
            print(yellow("No selection."))
            return None
        if pick.isdigit():
            idx = int(pick)
            if 1 <= idx <= len(live):
                return live[idx - 1]["ip"]
            print(yellow(f"Enter 1–{len(live)} from the list."))
            return None
        for h in live:
            if h["ip"] == pick:
                return h["ip"]
        resolved = _resolve_target(pick)
        if resolved:
            in_list = any(h["ip"] == resolved for h in live)
            if not in_list:
                print(
                    dim(
                        f"Using {resolved} — not in scan list; running tests anyway."
                    )
                )
            return resolved
        print(yellow("Invalid choice — use a list number or a valid IP/hostname."))
        return None
    print(yellow("Invalid choice."))
    return None


def _build_troubleshoot_verdict(
    target: str,
    *,
    recv: int,
    loss: int,
    avg_ms: float | None,
    gw_ok: bool,
    dns_ok: bool,
    internet_ok: bool,
    same_subnet: bool,
    open_ports: str,
) -> list[str]:
    lines: list[str] = []
    if recv == 0:
        if gw_ok and internet_ok:
            lines.append(
                "User PC does not respond to ping — likely powered off, unplugged, "
                "Wi-Fi disabled, wrong VLAN, or ICMP blocked by firewall."
            )
        elif gw_ok and not internet_ok:
            lines.append(
                "User PC silent; gateway works but internet from your laptop fails — "
                "possible WAN/ISP issue affecting the site."
            )
        elif not gw_ok:
            lines.append(
                "User PC and default gateway both unreachable — check your link, "
                "switch, or AP before blaming the user machine."
            )
        else:
            lines.append(
                "User PC unreachable from this laptop — investigate L2/L3 path and firewall."
            )
    elif loss >= 30:
        lines.append(
            f"High packet loss ({loss}%) to user PC — suspect Wi-Fi, bad cable, "
            "switch port, or congestion."
        )
    elif avg_ms is not None and avg_ms > 120:
        lines.append(
            f"High latency ({avg_ms:.0f}ms) to user PC — Wi-Fi or long network path."
        )
    else:
        lines.append(
            "User PC is reachable from your laptop — L2/L3 path looks OK at ICMP level."
        )
        if open_ports == "none detected":
            lines.append(
                "No common service ports open (RDP/SMB/SSH) — host may be up but "
                "firewalled or a simple device."
            )
        else:
            lines.append(
                f"Service ports open: {open_ports} — workstation/server likely online."
            )
    if not dns_ok:
        lines.append(
            "DNS resolution failed on your laptop — user 'no internet' may be DNS-wide, "
            "not only their PC."
        )
    if not same_subnet:
        lines.append(
            "User IP is not on your current subnet — traffic may be routed; "
            "confirm VLAN and IP assignment."
        )
    if recv > 0 and dns_ok and internet_ok and loss < 10:
        lines.append(
            "Next step: check DNS/gateway/proxy/VPN on the user PC (ipconfig / ifconfig) "
            "or remote in if ping works but apps fail."
        )
    return lines


def run_troubleshoot_host() -> None:
    print()
    print(bold("IT support — troubleshoot user PC"))
    print(dim("Run from your sysadmin laptop on the same network as the user."))
    print()

    if psutil is None:
        print(yellow("Install psutil: pip install psutil"))
        _print_done()
        return

    nets = _iter_local_ipv4_networks()
    picked = _pick_scan_network(nets)
    if not picked:
        print(yellow("No LAN found."))
        _print_done()
        return

    network, _iface = picked
    cidr = str(network)
    target = _troubleshoot_pick_target(network, cidr)
    if not target:
        _print_done()
        return

    hostname = _ptr_hostname(target)
    arp = _arp_table()
    mac = arp.get(target, "—")
    admin_ip = _local_ip_on_network(network) or _outward_ipv4() or "—"
    same_subnet = False
    try:
        same_subnet = ipaddress.ip_address(target) in network
    except ValueError:
        pass

    gw, _gw_iface = _default_route_info()

    print()
    print(bold("TARGET"))
    print(dim("─" * 44))
    _info_line("IP", target)
    _info_line("Hostname", hostname or "—")
    _info_line("MAC", mac)
    _info_line("Your IP", admin_ip)
    _info_line("Same subnet", "yes" if same_subnet else "no")

    print()
    print(bold("CONNECTIVITY TESTS"))
    print(dim("─" * 44))

    sent, recv, avg_ms, loss = _run_with_spinner(
        f"Pinging {target} (6 packets)…",
        lambda: _ping_multi(target, 6),
    )
    _info_line("Ping", f"{recv}/{sent} replies, {loss}% loss")
    if avg_ms is not None:
        _info_line("Avg RTT", f"{avg_ms:.1f} ms")

    gw_ok = False
    if gw:
        _gs, gr, gavg, gloss = _ping_multi(gw, 4)
        gw_ok = gr > 0
        gtxt = f"{gr}/{_gs} replies"
        if gavg is not None:
            gtxt += f", {gavg:.0f}ms avg"
        _info_line("Gateway", f"{gw} — {gtxt}")
    else:
        _info_line("Gateway", "not detected")

    dns_ok = _run_with_spinner("Testing DNS…", _test_dns_resolution)
    _info_line("DNS", "OK (google.com resolves)" if dns_ok else "FAILED")

    internet_ok = _run_with_spinner(
        "Testing internet (8.8.8.8 / 1.1.1.1)…",
        _test_internet_reachability,
    )
    _info_line("Internet", "reachable" if internet_ok else "not reachable from here")

    open_ports = _run_with_spinner(
        f"Probing common ports on {target}…",
        lambda: _probe_common_ports(target),
    )
    _info_line("TCP services", open_ports)

    if not same_subnet:
        trace = _run_with_spinner(
            f"Traceroute to {target}…",
            lambda: _traceroute_summary(target),
        )
        _info_line("Route", trace)

    print()
    print(bold("VERDICT"))
    print(dim("─" * 44))
    for line in _build_troubleshoot_verdict(
        target,
        recv=recv,
        loss=loss,
        avg_ms=avg_ms,
        gw_ok=gw_ok,
        dns_ok=dns_ok,
        internet_ok=internet_ok,
        same_subnet=same_subnet,
        open_ports=open_ports,
    ):
        print(dim(f"  • {line}"))

    print()
    _print_done()


def _is_private_ipv4(addr: str) -> bool:
    try:
        return ipaddress.ip_address(addr).is_private
    except ValueError:
        return False


def _default_gateway_linux() -> tuple[str | None, str | None]:
    try:
        r = subprocess.run(
            ["ip", "-4", "route", "show", "default"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode == 0 and r.stdout.strip():
            m = re.search(r"default via (\S+)\s+dev\s+(\S+)", r.stdout)
            if m:
                return m.group(1), m.group(2)
    except (OSError, subprocess.TimeoutExpired):
        pass
    try:
        with open("/proc/net/route", encoding="utf-8", errors="ignore") as fh:
            next(fh, None)
            for line in fh:
                fields = line.strip().split()
                if len(fields) < 4:
                    continue
                if fields[1] == "00000000" and int(fields[3], 16) & 2:
                    gw = socket.inet_ntoa(struct.pack("<L", int(fields[2], 16)))
                    return gw, fields[0]
    except (OSError, ValueError, struct.error):
        pass
    return None, None


def _default_gateway_windows() -> tuple[str | None, str | None]:
    try:
        script = (
            "$r = Get-NetRoute -DestinationPrefix '0.0.0.0/0' | "
            "Where-Object { $_.NextHop -ne '0.0.0.0' } | "
            "Sort-Object RouteMetric | Select-Object -First 1; "
            "if ($null -eq $r) { exit 1 }; "
            "$r.NextHop; $r.InterfaceAlias"
        )
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=14,
        )
        if r.returncode != 0:
            return None, None
        lines = [x.strip() for x in r.stdout.splitlines() if x.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]
        if len(lines) == 1:
            return lines[0], None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None, None


def _default_gateway_darwin() -> tuple[str | None, str | None]:
    try:
        r = subprocess.run(
            ["route", "-n", "get", "0.0.0.0"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        if r.returncode != 0:
            return None, None
        g = re.search(r"gateway:\s*(\S+)", r.stdout)
        iface = re.search(r"interface:\s*(\S+)", r.stdout)
        return ((g.group(1) if g else None), (iface.group(1) if iface else None))
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None, None


def _default_route_info() -> tuple[str | None, str | None]:
    if sys.platform == "win32":
        return _default_gateway_windows()
    if sys.platform == "darwin":
        return _default_gateway_darwin()
    return _default_gateway_linux()


def _dns_servers() -> list[str]:
    if sys.platform == "win32":
        try:
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    "Get-DnsClientServerAddress -AddressFamily IPv4 "
                    "| Where-Object { $_.ServerAddresses } "
                    "| ForEach-Object { $_.ServerAddresses } "
                    "| Sort-Object -Unique",
                ],
                capture_output=True,
                text=True,
                timeout=14,
            )
            if r.returncode == 0 and r.stdout.strip():
                return [x.strip() for x in r.stdout.splitlines() if x.strip()]
        except (OSError, subprocess.TimeoutExpired):
            pass
        return []
    out: list[str] = []
    try:
        with open("/etc/resolv.conf", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if line.lower().startswith("nameserver "):
                    parts = line.split()
                    if len(parts) >= 2 and parts[1] not in out:
                        out.append(parts[1])
    except OSError:
        pass
    return out


DNS_PRESETS: dict[str, list[str]] = {
    "google": ["8.8.8.8", "8.8.4.4"],
    "cloudflare": ["1.1.1.1", "1.0.0.1"],
    "quad9": ["9.9.9.9", "149.112.112.112"],
    "opendns": ["208.67.222.222", "208.67.220.220"],
}


def _parse_dns_input(raw: str) -> list[str] | None:
    text = raw.strip().lower()
    if not text:
        return None
    if text in DNS_PRESETS:
        return DNS_PRESETS[text]
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return None
    if ip.version != 4:
        return None
    return [str(ip)]


def _darwin_network_service(iface: str | None) -> str | None:
    if not iface:
        return None
    try:
        r = subprocess.run(
            ["networksetup", "-listallhardwareports"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return None
        blocks = re.split(r"\n\n+", r.stdout)
        for block in blocks:
            dev_m = re.search(r"Device:\s*(\S+)", block)
            name_m = re.search(r"Hardware Port:\s*(.+)", block)
            if dev_m and name_m and dev_m.group(1) == iface:
                return name_m.group(1).strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _linux_nmcli_active_connection() -> str | None:
    if not shutil.which("nmcli"):
        return None
    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,DEVICE", "con", "show", "--active"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode != 0:
            return None
        for line in r.stdout.splitlines():
            if not line or ":" not in line:
                continue
            name, dev = line.split(":", 1)
            if dev and dev != "--":
                return name.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _apply_dns_servers(servers: list[str], iface: str | None) -> bool:
    if not servers:
        return False

    if sys.platform == "win32":
        alias = iface
        if not alias:
            _, alias = _default_gateway_windows()
        if not alias:
            print(yellow("Could not detect active network interface."))
            return False
        joined = ",".join(f'"{s}"' for s in servers)
        script = (
            f'Set-DnsClientServerAddress -InterfaceAlias "{alias}" '
            f"-ServerAddresses @({joined})"
        )
        try:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command", script],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if r.returncode == 0:
                return True
            err = (r.stderr or r.stdout or "").strip()
            if err:
                print(dim(err))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return False

    if sys.platform == "darwin":
        service = _darwin_network_service(iface)
        if not service:
            print(yellow("Could not map interface to a macOS network service."))
            return False
        try:
            r = subprocess.run(
                ["networksetup", "-setdnsservers", service, *servers],
                capture_output=True,
                text=True,
                timeout=20,
            )
            if r.returncode == 0:
                return True
            if r.stderr:
                print(dim(r.stderr.strip()))
        except (OSError, subprocess.TimeoutExpired):
            pass
        return False

    conn = _linux_nmcli_active_connection()
    if conn and shutil.which("nmcli"):
        dns_val = " ".join(servers)
        try:
            mod = subprocess.run(
                [
                    "nmcli",
                    "con",
                    "mod",
                    conn,
                    "ipv4.dns",
                    dns_val,
                    "ipv4.ignore-auto-dns",
                    "yes",
                ],
                capture_output=True,
                text=True,
                timeout=20,
            )
            up = subprocess.run(
                ["nmcli", "con", "up", conn],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if mod.returncode == 0 and up.returncode == 0:
                return True
            err = (mod.stderr or mod.stdout or up.stderr or "").strip()
            if err:
                print(dim(err))
        except (OSError, subprocess.TimeoutExpired):
            pass

    if iface and shutil.which("resolvectl"):
        try:
            r = subprocess.run(
                ["resolvectl", "dns", iface, *servers],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if r.returncode == 0:
                return True
        except (OSError, subprocess.TimeoutExpired):
            pass

    print(
        yellow(
            "Automatic DNS change failed. You may need admin/root, NetworkManager, "
            "or set DNS manually in system settings."
        )
    )
    return False


def _info_section(title: str) -> None:
    print()
    print(bold(title))
    print(dim("─" * 44))


def _info_line(label: str, value: str | None, width: int = 14) -> None:
    if not value:
        return
    print(f"  {label:<{width}} {value}")


def _print_network_report(
    iface: str | None,
    medium: str,
    link: str,
    mtu: str,
    wifi_ssid: str | None,
    gw: str | None,
    gw_name: str | None,
    dns: list[str],
    local_rows: list[tuple[str, str]],
    outward: str | None,
    wan: dict[str, str] | None,
) -> None:
    print()
    print(bold("Network info"))
    print(dim("═" * 44))

    _info_section("CONNECTION")
    _info_line("Interface", iface or "—")
    _info_line("Type", medium)
    _info_line("Link", link)
    _info_line("MTU", mtu)
    if wifi_ssid:
        _info_line("Wi-Fi", wifi_ssid)

    _info_section("GATEWAY")
    _info_line("IP", gw or "—")
    if gw_name:
        _info_line("Hostname", gw_name)

    _info_section("DNS")
    if dns:
        _info_line("Servers", ", ".join(dns[:6]))
        if len(dns) > 6:
            _info_line("", f"+ {len(dns) - 6} more", width=14)
    else:
        _info_line("Servers", "—")

    _info_section("THIS PC")
    if local_rows:
        for ip, ifname in local_rows:
            print(f"  {ip:<16} {ifname}")
    else:
        _info_line("IPv4", "—")
    if outward:
        _info_line("Route IP", outward)

    _info_section("INTERNET")
    if wan:
        _info_line("Public IP", wan.get("ip"))
        _info_line("ISP / ASN", wan.get("org"))
        loc_parts = [p for p in (wan.get("city"), wan.get("region"), wan.get("country")) if p]
        if loc_parts:
            _info_line("Location", ", ".join(loc_parts))
        _info_line("Hostname", wan.get("hostname"))
    else:
        _info_line("Public IP", "unavailable (offline or blocked)")

    print()


def _configure_dns_flow(iface: str | None) -> None:
    print()
    print(bold("Configure DNS"))
    print(dim("─" * 44))
    print(dim("  IP examples:  8.8.8.8   1.1.1.1"))
    print(dim("  Presets:      google  cloudflare  quad9  opendns"))
    print()
    raw = input(dim("DNS address or preset: ")).strip()
    servers = _parse_dns_input(raw)
    if servers is None:
        if raw:
            print(yellow("Invalid IPv4 or preset."))
        return

    label = raw if raw not in DNS_PRESETS else f"{raw} ({', '.join(servers)})"
    print(dim(f"  Target: {', '.join(servers)}"))
    if not _ask_yes_no(f"Apply {label}?", default_yes=True):
        print(dim("Cancelled."))
        return

    if _apply_dns_servers(servers, iface):
        print(green("DNS updated."))
        current = _dns_servers()
        if current:
            _info_line("Now using", ", ".join(current[:6]))
    else:
        print(yellow("Could not apply automatically (try admin/root)."))


def run_configure_dns() -> None:
    print()
    _, iface = _default_route_info()
    _configure_dns_flow(iface)


def _neighbor_mac(gw: str) -> str | None:
    if not gw:
        return None
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["arp", "-a", gw],
                capture_output=True,
                text=True,
                timeout=6,
            )
            m = re.search(
                r"([0-9a-f]{2}(?:-[0-9a-f]{2}){5})",
                r.stdout,
                re.I,
            )
            if m:
                return m.group(1).replace("-", ":").lower()
        elif sys.platform == "darwin":
            r = subprocess.run(
                ["arp", "-n", gw],
                capture_output=True,
                text=True,
                timeout=6,
            )
            m = re.search(r"at\s+([0-9a-f:]{17})", r.stdout, re.I)
            if m:
                return m.group(1).lower()
        else:
            r = subprocess.run(
                ["ip", "neigh", "show", gw],
                capture_output=True,
                text=True,
                timeout=5,
            )
            m = re.search(r"lladdr\s+([0-9a-f:]{17})", r.stdout, re.I)
            if m:
                return m.group(1).lower()
            r2 = subprocess.run(
                ["arp", "-n", gw],
                capture_output=True,
                text=True,
                timeout=5,
            )
            m2 = re.search(
                r"(([0-9a-f]{1,2}:){5}[0-9a-f]{1,2})",
                r2.stdout,
                re.I,
            )
            if m2:
                return m2.group(1).lower()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _http_title(url: str) -> str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 NetworkScorpioLANProbe/1.0"},
        )
        with urllib.request.urlopen(req, timeout=2.5) as resp:
            chunk = resp.read(12000).decode("utf-8", errors="ignore")
        m = re.search(r"<title[^>]*>([^<]{1,140})", chunk, re.I | re.S)
        if m:
            return re.sub(r"\s+", " ", m.group(1)).strip()
    except (urllib.error.URLError, OSError, ValueError):
        pass
    return None


def _router_login_page_hint(gw: str) -> str | None:
    if not gw or not _is_private_ipv4(gw):
        return None
    for path in ("/", "/login.html", "/index.html", "/cgi-bin/luci"):
        url = f"http://{gw}{path}" if path != "/" else f"http://{gw}/"
        title = _http_title(url)
        if title:
            return title
    return None


def _wifi_ssid_for_iface(iface: str | None) -> str | None:
    if not iface:
        return None
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode != 0:
                return None
            m = re.search(r"(?im)^\s*SSID\s*:\s*(.+)\s*$", r.stdout)
            if m:
                return m.group(1).strip()
        elif sys.platform == "darwin":
            r = subprocess.run(
                ["networksetup", "-getairportnetwork", iface],
                capture_output=True,
                text=True,
                timeout=8,
            )
            if r.returncode != 0:
                return None
            m = re.search(r"Network:\s*(.+)", r.stdout)
            if m:
                return m.group(1).strip()
        else:
            if shutil.which("iw"):
                r = subprocess.run(
                    ["iw", "dev", iface, "link"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.returncode == 0:
                    m = re.search(r"SSID:\s*(.+)", r.stdout)
                    if m:
                        return m.group(1).strip()
            if shutil.which("nmcli"):
                r = subprocess.run(
                    ["nmcli", "-t", "-f", "DEVICE,CONNECTION", "device"],
                    capture_output=True,
                    text=True,
                    timeout=6,
                )
                for line in r.stdout.splitlines():
                    parts = line.split(":")
                    if len(parts) >= 2 and parts[0] == iface:
                        conn = parts[1].strip()
                        if conn and conn != "--":
                            return conn
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def _wifi_extra_linux(iface: str) -> str | None:
    if not shutil.which("iw"):
        return None
    try:
        r = subprocess.run(
            ["iw", "dev", iface, "link"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if r.returncode != 0:
            return None
        bits: list[str] = []
        m = re.search(r"signal:\s*(-?\d+)\s*dBm", r.stdout)
        if m:
            bits.append(f"signal {m.group(1)} dBm")
        m = re.search(r"freq:\s*(\d+)", r.stdout)
        if m:
            bits.append(f"freq {m.group(1)} MHz")
        m = re.search(r"tx bitrate:\s*([^\n]+)", r.stdout)
        if m:
            bits.append(f"TX {m.group(1).strip()}")
        return " · ".join(bits) if bits else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _interface_medium(iface: str | None) -> str:
    if not iface:
        return "unknown"
    if sys.platform.startswith("linux"):
        if os.path.exists(f"/sys/class/net/{iface}/wireless"):
            return "Wi-Fi"
        return "Ethernet / wired (or non-Wi-Fi)"
    if sys.platform == "win32":
        esc = iface.replace("'", "''")
        try:
            r = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-Command",
                    f"(Get-NetAdapter -Name '{esc}' -ErrorAction SilentlyContinue)"
                    f".PhysicalMediaType",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if r.returncode == 0 and r.stdout.strip():
                t = r.stdout.strip()
                if re.search(r"802\.11|Native 802\.11|Wireless", t, re.I):
                    return f"Wi-Fi ({t})"
                return f"Wired / other ({t})"
        except (OSError, subprocess.TimeoutExpired):
            pass
        low = iface.lower()
        if "wi-fi" in low or "wlan" in low or "wireless" in low:
            return "Wi-Fi (name heuristic)"
        return "unknown (could not query PhysicalMediaType)"
    if sys.platform == "darwin":
        low = iface.lower()
        if low.startswith("en") and not low.startswith("enx"):
            return "Wi-Fi or Ethernet (macOS en*; check System Settings if unsure)"
        return "unknown"
    return "unknown"


def _iface_mtu(iface: str | None) -> str:
    if not iface:
        return "—"
    if psutil is not None:
        try:
            st = psutil.net_if_stats().get(iface)
            if st is not None:
                mtu = getattr(st, "mtu", None)
                if mtu:
                    return str(mtu)
        except (OSError, AttributeError):
            pass
    if sys.platform.startswith("linux"):
        try:
            with open(
                f"/sys/class/net/{iface}/mtu",
                encoding="utf-8",
                errors="ignore",
            ) as f:
                return f.read().strip()
        except OSError:
            pass
    return "—"


def _iface_speed_line(iface: str | None) -> str:
    if not iface or psutil is None:
        return "—"
    try:
        st = psutil.net_if_stats().get(iface)
        if st is None:
            return "—"
        parts: list[str] = []
        if st.isup:
            parts.append("link up")
        else:
            parts.append("link down")
        if st.speed and st.speed > 0:
            parts.append(f"reported {st.speed} Mb/s")
        dup = getattr(st, "duplex", None)
        if dup is not None and str(dup) != "NicDuplex.NIC_DUPLEX_UNKNOWN":
            parts.append(str(dup).replace("NicDuplex.", "").replace("_", " ").lower())
        return ", ".join(parts) if parts else "—"
    except (OSError, AttributeError):
        return "—"


def _local_ipv4_summary() -> list[str]:
    if psutil is None:
        return []
    lines: list[str] = []
    for name, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family != socket.AF_INET:
                continue
            ip = a.address
            if ip.startswith("127."):
                continue
            scope = "private LAN" if _is_private_ipv4(ip) else "public / routable"
            nm = a.netmask or "—"
            lines.append(f"  {name}: {ip} ({scope}) netmask {nm}")
    return lines


def _wan_dict_normalize(raw: dict[str, object]) -> dict[str, str]:
    out: dict[str, str] = {}
    mapping = [
        ("ip", ["ip", "query"]),
        ("hostname", ["hostname"]),
        ("city", ["city"]),
        ("region", ["region", "regionName"]),
        ("country", ["country", "country_name"]),
        ("org", ["org", "org_name", "as", "asn"]),
        ("postal", ["postal", "zip"]),
        ("timezone", ["timezone", "timezone_name"]),
    ]
    for key, aliases in mapping:
        for a in aliases:
            v = raw.get(a)
            if v is not None and str(v).strip():
                out[key] = str(v).strip()
                break
    loc = raw.get("loc")
    if isinstance(loc, str) and loc.strip():
        out["geo_loc"] = loc.strip()
    return out


def _fetch_wan_identity() -> dict[str, str] | None:
    for url in (
        "https://ipinfo.io/json",
        "https://ipapi.co/json/",
    ):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "NetworkScorpioTool/1.0"},
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                raw = json.loads(resp.read().decode("utf-8", errors="replace"))
            if isinstance(raw, dict):
                return _wan_dict_normalize(raw)  # type: ignore[arg-type]
        except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
            continue
    return None


def run_network_intel() -> None:
    print()

    if psutil is None:
        print(yellow("Install psutil: pip install psutil"))
        _print_done()
        return

    gw, iface = _default_route_info()
    outward = _outward_ipv4()
    med = _interface_medium(iface)
    wifi_ssid = _wifi_ssid_for_iface(iface) if iface and "Wi-Fi" in med else None
    gw_name = _ptr_hostname(gw) if gw else None
    dns = _dns_servers()

    local_rows: list[tuple[str, str]] = []
    for name, addrs in psutil.net_if_addrs().items():
        for a in addrs:
            if a.family != socket.AF_INET:
                continue
            ip = a.address
            if ip.startswith("127."):
                continue
            local_rows.append((ip, name))
    local_rows.sort(key=lambda x: ipaddress.IPv4Address(x[0]))

    wan = _run_with_spinner("Loading internet details…", _fetch_wan_identity)

    _print_network_report(
        iface=iface,
        medium=med,
        link=_iface_speed_line(iface),
        mtu=_iface_mtu(iface),
        wifi_ssid=wifi_ssid,
        gw=gw,
        gw_name=gw_name,
        dns=dns,
        local_rows=local_rows,
        outward=outward,
        wan=wan,
    )

    print()
    _print_done()


# --- Network Security monitor -------------------------------------------------

_SECURITY_HIGH_PORTS = frozenset(
    {4444, 5555, 6666, 6667, 1337, 31337, 12345, 1234, 9001, 2744, 666}
)
_SECURITY_SENSITIVE_LISTEN = frozenset(
    {
        21, 23, 69, 135, 139, 445, 1433, 1521, 3306, 3389, 5432, 5900, 6379,
        8080, 8443, 8888, 27017, 9200, 11211,
    }
)
_SECURITY_SAFE_LISTEN = frozenset({22, 53, 80, 443, 631, 5353, 7680, 853})

_SECURITY_PORT_NAMES: dict[int, str] = {
    20: "FTP-DATA", 21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
    67: "DHCP", 68: "DHCP", 69: "TFTP", 80: "HTTP", 110: "POP3", 123: "NTP",
    135: "RPC", 139: "NetBIOS", 143: "IMAP", 161: "SNMP", 443: "HTTPS",
    445: "SMB", 465: "SMTPS", 514: "Syslog", 587: "SMTP", 631: "IPP",
    993: "IMAPS", 995: "POP3S", 1433: "MSSQL", 1521: "Oracle", 3306: "MySQL",
    3389: "RDP", 3478: "STUN", 4444: "Metasploit?", 5432: "PostgreSQL",
    5900: "VNC", 6379: "Redis", 8080: "HTTP-ALT", 8443: "HTTPS-ALT",
    8888: "HTTP-ALT", 27017: "MongoDB",
}

_SECURITY_CLIENT_PORTS = frozenset(
    {21, 22, 23, 25, 53, 80, 110, 143, 443, 465, 587, 993, 995, 8080, 8443}
)

# (hostname regex, commercial name, kind: app|website|service|cloud)
_SECURITY_BRAND_RULES: tuple[tuple[re.Pattern[str], str, str], ...] = (
    (re.compile(r"google|gstatic|googleusercontent|1e100\.net|gvt\d|googlesyndication|googleapis|ggpht|gmail", re.I), "Google", "website"),
    (re.compile(r"cursor\.sh|cursor\.com|todesktop|anysphere", re.I), "Cursor", "app"),
    (re.compile(r"github|githubusercontent|github\.io", re.I), "GitHub", "website"),
    (re.compile(r"microsoft|office365|office\.com|live\.com|outlook|azure|msft|windowsupdate|bing\.com", re.I), "Microsoft", "website"),
    (re.compile(r"apple\.com|icloud|mzstatic|itunes|push\.apple", re.I), "Apple", "website"),
    (re.compile(r"amazonaws|cloudfront|amazon\.com|aws\.", re.I), "Amazon AWS", "cloud"),
    (re.compile(r"facebook|fbcdn|instagram|whatsapp|meta\.com", re.I), "Meta", "website"),
    (re.compile(r"twitter\.com|twimg|x\.com", re.I), "X (Twitter)", "website"),
    (re.compile(r"discord(app)?\.|discord\.com", re.I), "Discord", "app"),
    (re.compile(r"spotify", re.I), "Spotify", "website"),
    (re.compile(r"netflix", re.I), "Netflix", "website"),
    (re.compile(r"youtube|ytimg|youtu\.be", re.I), "YouTube", "website"),
    (re.compile(r"openai|chatgpt|oaistatic|oaiusercontent", re.I), "OpenAI", "website"),
    (re.compile(r"anthropic|claude", re.I), "Anthropic", "website"),
    (re.compile(r"slack\.com|slack-edge|slackb", re.I), "Slack", "app"),
    (re.compile(r"zoom\.us|zoom\.com", re.I), "Zoom", "app"),
    (re.compile(r"teams\.microsoft|skype", re.I), "Microsoft Teams", "app"),
    (re.compile(r"dropbox", re.I), "Dropbox", "cloud"),
    (re.compile(r"cloudflare|cf-ray", re.I), "Cloudflare", "cloud"),
    (re.compile(r"steam|valvesoftware", re.I), "Steam", "app"),
    (re.compile(r"reddit|redd\.it", re.I), "Reddit", "website"),
    (re.compile(r"linkedin", re.I), "LinkedIn", "website"),
    (re.compile(r"tiktok|tiktokcdn|byteoversea", re.I), "TikTok", "website"),
    (re.compile(r"telegram", re.I), "Telegram", "app"),
    (re.compile(r"signal\.org", re.I), "Signal", "app"),
    (re.compile(r"docker|dockerhub", re.I), "Docker", "cloud"),
    (re.compile(r"npmjs|registry\.npm", re.I), "npm", "service"),
    (re.compile(r"pypi\.org|pythonhosted", re.I), "PyPI", "service"),
    (re.compile(r"ubuntu\.com|canonical", re.I), "Canonical", "service"),
    (re.compile(r"debian\.org", re.I), "Debian", "service"),
    (re.compile(r"kali\.org|offsec", re.I), "Kali / OffSec", "service"),
    (re.compile(r"archive\.org", re.I), "Internet Archive", "website"),
    (re.compile(r"wikipedia|wikimedia", re.I), "Wikipedia", "website"),
    (re.compile(r"stackoverflow|stackexchange", re.I), "Stack Overflow", "website"),
    (re.compile(r"fastly|akamai|edgekey", re.I), "CDN", "cloud"),
    (re.compile(r"snapchat", re.I), "Snapchat", "website"),
)

_PROCESS_BRANDS: dict[str, tuple[str, str]] = {
    "chrome": ("Google Chrome", "app"),
    "google chrome": ("Google Chrome", "app"),
    "chromium": ("Chromium", "app"),
    "firefox": ("Firefox", "app"),
    "msedge": ("Microsoft Edge", "app"),
    "microsoft edge": ("Microsoft Edge", "app"),
    "brave": ("Brave", "app"),
    "opera": ("Opera", "app"),
    "safari": ("Safari", "app"),
    "cursor": ("Cursor", "app"),
    "code": ("Visual Studio Code", "app"),
    "slack": ("Slack", "app"),
    "discord": ("Discord", "app"),
    "spotify": ("Spotify", "app"),
    "steam": ("Steam", "app"),
    "telegram": ("Telegram", "app"),
    "zoom": ("Zoom", "app"),
    "teams": ("Microsoft Teams", "app"),
    "outlook": ("Microsoft Outlook", "app"),
    "thunderbird": ("Thunderbird", "app"),
    "wget": ("wget", "app"),
    "curl": ("curl", "app"),
    "python": ("Python", "app"),
    "node": ("Node.js", "app"),
    "docker": ("Docker", "app"),
    "sshd": ("SSH Server", "service"),
    "ssh": ("SSH", "service"),
    "nginx": ("Nginx", "service"),
    "apache2": ("Apache", "service"),
    "httpd": ("Apache", "service"),
    "mysqld": ("MySQL", "service"),
    "postgres": ("PostgreSQL", "service"),
    "systemd-resolve": ("DNS (systemd)", "service"),
}


def _security_brand_highlight(name: str) -> str:
    if not name or name == "—":
        return dim("Unknown")
    if not _use_color():
        return name
    return f"{ANSI_BRIGHT_CYAN}{ANSI_BOLD}{name}{ANSI_RESET}"


def _security_kind_tag(kind: str) -> str:
    labels = {
        "app": "app",
        "website": "web",
        "service": "svc",
        "cloud": "cloud",
        "device": "LAN",
    }
    return dim(labels.get(kind, kind))


def _security_org_to_brand(org: str) -> str:
    s = org.strip()
    if re.match(r"^AS\d+\s+", s):
        s = re.sub(r"^AS\d+\s+", "", s)
    for suffix in (
        " LLC", " Inc.", " Inc", " Ltd.", " Ltd", " Limited", " Corporation",
        " Corp.", " Corp", " GmbH", " S.A.", " B.V.", " PLC", " Co.",
    ):
        if s.endswith(suffix):
            s = s[: -len(suffix)]
    return s.strip() or org


def _security_identify_from_host(hostname: str) -> tuple[str | None, str]:
    if not hostname or hostname == "—":
        return None, "unknown"
    host = hostname.lower().rstrip(".")
    for pattern, brand, kind in _SECURITY_BRAND_RULES:
        if pattern.search(host):
            return brand, kind
    parts = host.split(".")
    if len(parts) >= 2:
        base = parts[-2]
        if len(base) > 2 and base not in ("co", "com", "net", "org"):
            return base.capitalize(), "website"
    return None, "unknown"


def _security_identify_from_process(process: str) -> tuple[str | None, str]:
    if not process or process in ("—", "unknown"):
        return None, "unknown"
    key = process.lower().replace(".exe", "").strip()
    if key in _PROCESS_BRANDS:
        return _PROCESS_BRANDS[key]
    for stem, pair in _PROCESS_BRANDS.items():
        if stem in key:
            return pair
    return None, "unknown"


def _security_fetch_ip_brand(ip: str) -> tuple[str | None, str]:
    try:
        url = f"http://ip-api.com/json/{ip}?fields=status,org,reverse"
        req = urllib.request.Request(
            url, headers={"User-Agent": "NetworkScorpioTool/1.0"}
        )
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        if data.get("status") != "success":
            return None, "unknown"
        org = data.get("org") or ""
        if org:
            return _security_org_to_brand(str(org)), "website"
        rev = data.get("reverse") or ""
        if rev:
            return _security_identify_from_host(str(rev))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        pass
    return None, "unknown"


def _security_identify_peer(
    ip: str | None,
    hostname: str,
    process: str,
    scope: str,
) -> tuple[str, str]:
    proc_brand, proc_kind = _security_identify_from_process(process)
    host_brand, host_kind = _security_identify_from_host(hostname)
    if host_brand:
        return host_brand, host_kind
    if proc_brand and scope == "internet":
        return proc_brand, proc_kind
    if scope == "LAN":
        if hostname and hostname != "—":
            short = hostname.split(".")[0]
            return short.capitalize(), "device"
        return "Device on LAN", "device"
    if scope == "local":
        return "This machine", "service"
    if proc_brand:
        return proc_brand, proc_kind
    return "Unknown", "unknown"


def _security_lookup_public_brands(ips: set[str]) -> dict[str, tuple[str, str]]:
    need = {ip for ip in ips if ip}
    if not need:
        return {}
    out: dict[str, tuple[str, str]] = {}
    # ip-api free tier: stay under ~40/min
    batch = sorted(need)[:24]

    def one(ip: str) -> tuple[str, tuple[str | None, str]]:
        return ip, _security_fetch_ip_brand(ip)

    workers = min(8, len(batch))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for ip, pair in pool.map(one, batch):
            if pair[0]:
                out[ip] = pair
    return out


def _security_enrich_rows(
    rows: list[dict[str, Any]],
    ip_brands: dict[str, tuple[str, str]],
) -> None:
    for row in rows:
        rip = row.get("r_ip")
        host = row.get("remote_name", "—")
        proc = row.get("process", "—")
        scope = row.get("scope", "—")
        brand, kind = _security_identify_peer(rip, host, proc, scope)
        if brand in ("Unknown",) and rip and rip in ip_brands:
            brand, kind = ip_brands[rip]
        if brand == "Unknown" and host not in ("—", ""):
            brand, kind = _security_identify_from_host(host)
            if not brand:
                brand = host.split(".")[0].capitalize()
                kind = "website"
        row["brand"] = brand
        row["brand_kind"] = kind


def _security_build_connection_cards(
    inbound: list[dict[str, Any]],
    outbound: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in inbound + outbound:
        brand = row.get("brand", "Unknown")
        key = (brand, row.get("direction"), row.get("r_ip"), row.get("process"))
        if key not in merged:
            merged[key] = {
                "brand": brand,
                "brand_kind": row.get("brand_kind", "unknown"),
                "direction": row.get("direction"),
                "process": row.get("process", "—"),
                "r_ip": row.get("r_ip"),
                "remote": row.get("remote"),
                "remote_name": row.get("remote_name", "—"),
                "scope": row.get("scope"),
                "count": 1,
            }
        else:
            merged[key]["count"] += 1
    cards = list(merged.values())
    cards.sort(
        key=lambda c: (
            0 if c["direction"] == "outbound" else 1,
            c["brand"].lower(),
        )
    )
    return cards


def _security_process_name(pid: int | None) -> str:
    if pid is None or psutil is None:
        return "—"
    try:
        return psutil.Process(pid).name()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        return "unknown"


def _security_conn_endpoints(
    conn: Any,
) -> tuple[str | None, int | None, str | None, int | None]:
    l_ip, l_port, r_ip, r_port = None, None, None, None
    if conn.laddr:
        l_ip = getattr(conn.laddr, "ip", conn.laddr[0])
        l_port = getattr(conn.laddr, "port", conn.laddr[1])
    if conn.raddr:
        r_ip = getattr(conn.raddr, "ip", conn.raddr[0])
        r_port = getattr(conn.raddr, "port", conn.raddr[1])
    return l_ip, l_port, r_ip, r_port


def _security_proto(conn: Any) -> str:
    ctype = getattr(conn, "type", socket.SOCK_STREAM)
    return "udp" if ctype == socket.SOCK_DGRAM else "tcp"


def _security_ep(ip: str | None, port: int | None) -> str:
    if port is None:
        return "—"
    if not ip or ip in ("0.0.0.0", "::", "*"):
        return f"*:{port}"
    if ":" in ip and not ip.startswith("["):
        return f"[{ip}]:{port}"
    return f"{ip}:{port}"


def _security_service_label(port: int | None) -> str:
    if port is None:
        return "—"
    return _SECURITY_PORT_NAMES.get(port, f"port {port}")


def _security_ip_scope(ip: str | None) -> str:
    if not ip:
        return "—"
    try:
        addr = ipaddress.ip_address(ip)
        if addr.is_loopback:
            return "local"
        if addr.is_private or addr.is_link_local:
            return "LAN"
        if addr.is_multicast:
            return "multicast"
        return "internet"
    except ValueError:
        return "—"


def _security_bind_scope(l_ip: str | None) -> str:
    if l_ip in (None, "0.0.0.0", "::", ""):
        return "all interfaces"
    if l_ip in ("127.0.0.1", "::1"):
        return "localhost only"
    return f"interface {l_ip}"


def _security_process_info(pid: int | None) -> tuple[str, str]:
    name = _security_process_name(pid)
    exe = "—"
    if pid is None or psutil is None:
        return name, exe
    try:
        path = psutil.Process(pid).exe()
        if path:
            exe = path if len(path) <= 44 else ("…" + path[-41:])
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass
    return name, exe


def _security_is_routable_peer(ip: str | None) -> bool:
    if not ip:
        return False
    try:
        addr = ipaddress.ip_address(ip)
        return not (addr.is_loopback or addr.is_unspecified)
    except ValueError:
        return False


def _security_classify_direction(
    l_port: int | None,
    r_port: int | None,
    listener_keys: set[tuple[str, int]],
    proto: str,
) -> str:
    if l_port is not None and (proto, l_port) in listener_keys:
        return "inbound"
    if r_port in _SECURITY_CLIENT_PORTS and l_port and l_port > 1024:
        return "outbound"
    if l_port and l_port < 1024 and r_port and r_port > 1024:
        return "inbound"
    if r_port and r_port < 1024 and l_port and l_port > 1024:
        return "outbound"
    return "other"


def _security_resolve_hostnames(ips: set[str]) -> dict[str, str]:
    if not ips:
        return {}
    out: dict[str, str] = {}

    def lookup(ip: str) -> tuple[str, str]:
        name = _ptr_hostname(ip)
        return ip, name if name else "—"

    workers = min(12, max(1, len(ips)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for ip, name in pool.map(lookup, sorted(ips, key=str)):
            out[ip] = name
    return out


def _security_collect_connections() -> list[Any]:
    if psutil is None:
        return []
    try:
        return list(psutil.net_connections(kind="inet"))
    except psutil.AccessDenied:
        print(
            yellow(
                "Limited view: run as root/administrator for full connection details."
            )
        )
        try:
            return list(psutil.net_connections(kind="inet"))
        except (psutil.Error, OSError):
            return []


def _security_build_snapshot() -> dict[str, Any]:
    conns = _security_collect_connections()
    listeners: list[dict[str, Any]] = []
    inbound: list[dict[str, Any]] = []
    outbound: list[dict[str, Any]] = []
    other_active: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    seen_finding: set[tuple[Any, ...]] = set()
    remote_counts: dict[str, int] = {}
    listener_keys: set[tuple[str, int]] = set()
    peer_ips: set[str] = set()

    stats = {
        "total": len(conns),
        "listen": 0,
        "established": 0,
        "inbound_n": 0,
        "outbound_n": 0,
        "internet_peers": 0,
    }

    def add_finding(
        *,
        risk: str,
        kind: str,
        reason: str,
        status: str,
        local: str,
        remote: str,
        port: int,
        pid: int | None,
        proto: str,
    ) -> None:
        key = (risk, kind, local, remote, port, pid, reason)
        if key in seen_finding:
            return
        seen_finding.add(key)
        proc, _exe = _security_process_info(pid)
        fid = len(findings) + 1
        summary = f"{kind}: {local} → {remote} — {reason}"
        if proc not in ("—", "unknown"):
            summary += f" ({proc})"
        findings.append(
            {
                "id": fid,
                "risk": risk,
                "kind": kind,
                "reason": reason,
                "status": status,
                "local": local,
                "remote": remote,
                "port": port,
                "pid": pid,
                "process": proc,
                "proto": proto,
                "summary": summary,
            }
        )

    # Pass 1 — listeners
    for conn in conns:
        status = (conn.status or "").upper()
        if status != "LISTEN":
            continue
        l_ip, l_port, _r_ip, _r_port = _security_conn_endpoints(conn)
        if l_port is None:
            continue
        proto = _security_proto(conn)
        pid = getattr(conn, "pid", None)
        proc, exe = _security_process_info(pid)
        listener_keys.add((proto, l_port))
        stats["listen"] += 1
        wide_open = l_ip in (None, "0.0.0.0", "::", "")
        local_s = _security_ep(l_ip, l_port)
        listeners.append(
            {
                "proto": proto,
                "port": l_port,
                "service": _security_service_label(l_port),
                "bind": local_s,
                "scope": _security_bind_scope(l_ip),
                "process": proc,
                "exe": exe,
                "pid": pid,
            }
        )
        if l_port in _SECURITY_HIGH_PORTS:
            add_finding(
                risk="HIGH",
                kind="LISTEN",
                reason=f"high-risk port {l_port} open to network",
                status=status,
                local=local_s,
                remote="—",
                port=l_port,
                pid=pid,
                proto=proto,
            )
        elif l_port in _SECURITY_SENSITIVE_LISTEN and wide_open:
            add_finding(
                risk="MED",
                kind="LISTEN",
                reason=f"sensitive port {l_port} listening on all interfaces",
                status=status,
                local=local_s,
                remote="—",
                port=l_port,
                pid=pid,
                proto=proto,
            )
        elif (
            wide_open
            and l_port not in _SECURITY_SAFE_LISTEN
            and l_port < 1024
            and l_port not in (80, 443)
        ):
            add_finding(
                risk="LOW",
                kind="LISTEN",
                reason=f"privileged port {l_port} bound to all interfaces",
                status=status,
                local=local_s,
                remote="—",
                port=l_port,
                pid=pid,
                proto=proto,
            )

    listeners.sort(key=lambda x: (x["proto"], x["port"]))

    # Pass 2 — active sessions
    active_status = frozenset(
        {"ESTABLISHED", "SYN_SENT", "SYN_RECV", "FIN_WAIT1", "FIN_WAIT2", "CLOSE_WAIT"}
    )
    for conn in conns:
        status = (conn.status or "").upper()
        if status not in active_status:
            continue
        l_ip, l_port, r_ip, r_port = _security_conn_endpoints(conn)
        proto = _security_proto(conn)
        pid = getattr(conn, "pid", None)
        proc, exe = _security_process_info(pid)
        local_s = _security_ep(l_ip, l_port)
        remote_s = _security_ep(r_ip, r_port)
        direction = _security_classify_direction(
            l_port, r_port, listener_keys, proto
        )
        peer_scope = _security_ip_scope(r_ip)

        row = {
            "proto": proto.upper(),
            "status": status,
            "local": local_s,
            "remote": remote_s,
            "r_ip": r_ip,
            "r_port": r_port,
            "l_port": l_port,
            "remote_name": "—",
            "direction": direction,
            "scope": peer_scope,
            "process": proc,
            "exe": exe,
            "pid": pid,
            "service": _security_service_label(r_port or l_port),
        }

        if status == "ESTABLISHED":
            stats["established"] += 1

        if r_ip and _security_is_routable_peer(r_ip):
            peer_ips.add(r_ip)
            if peer_scope == "internet":
                remote_counts[r_ip] = remote_counts.get(r_ip, 0) + 1

        if direction == "inbound" and r_ip:
            inbound.append(row)
            stats["inbound_n"] += 1
        elif direction == "outbound" and r_ip:
            outbound.append(row)
            stats["outbound_n"] += 1
        elif r_ip:
            other_active.append(row)

        if r_ip and r_port is not None:
            try:
                pub = not ipaddress.ip_address(r_ip).is_private
            except ValueError:
                pub = not _is_private_ipv4(r_ip)
            if pub and r_ip not in ("127.0.0.1", "::1"):
                if r_port in _SECURITY_HIGH_PORTS:
                    add_finding(
                        risk="HIGH",
                        kind="OUTBOUND",
                        reason=f"connection to high-risk remote port {r_port}",
                        status=status,
                        local=local_s,
                        remote=remote_s,
                        port=r_port,
                        pid=pid,
                        proto=proto,
                    )
                elif r_port in {23, 21, 135, 139, 445, 1433, 3389, 5900}:
                    add_finding(
                        risk="HIGH",
                        kind="OUTBOUND",
                        reason=f"outbound to internet on sensitive port {r_port}",
                        status=status,
                        local=local_s,
                        remote=remote_s,
                        port=r_port,
                        pid=pid,
                        proto=proto,
                    )
            if l_port in _SECURITY_HIGH_PORTS and status == "ESTABLISHED":
                add_finding(
                    risk="HIGH",
                    kind="INBOUND",
                    reason=f"active session on local high-risk port {l_port}",
                    status=status,
                    local=local_s,
                    remote=remote_s,
                    port=l_port,
                    pid=pid,
                    proto=proto,
                )

    for rip, cnt in remote_counts.items():
        if cnt >= 25:
            add_finding(
                risk="MED",
                kind="FLOOD",
                reason=f"{cnt} connections to {rip} (possible scan or bot traffic)",
                status="ESTABLISHED",
                local="—",
                remote=rip,
                port=0,
                pid=None,
                proto="tcp",
            )

    names = _security_resolve_hostnames(peer_ips)
    for group in (inbound, outbound, other_active):
        for row in group:
            rip = row.get("r_ip")
            if rip:
                row["remote_name"] = names.get(rip, "—")

    public_ips = {
        ip for ip in peer_ips if _security_ip_scope(ip) == "internet"
    }
    ip_brands = _security_lookup_public_brands(public_ips)

    for group in (inbound, outbound):
        _security_enrich_rows(group, ip_brands)

    for entry in listeners:
        proc = entry.get("process", "—")
        brand, kind = _security_identify_from_process(proc)
        if not brand:
            brand = entry["service"]
            kind = "service"
        entry["brand"] = brand
        entry["brand_kind"] = kind

    connections = _security_build_connection_cards(inbound, outbound)
    stats["internet_peers"] = sum(
        1 for c in connections if c.get("scope") == "internet"
    )

    risk_order = {"HIGH": 0, "MED": 1, "LOW": 2}
    findings.sort(key=lambda f: (risk_order.get(f["risk"], 9), f["id"]))
    for i, f in enumerate(findings, 1):
        f["id"] = i
    suspicious = [f for f in findings if f["risk"] in ("HIGH", "MED")]

    return {
        "stats": stats,
        "listeners": listeners,
        "connections": connections,
        "findings": findings,
        "suspicious": suspicious,
        "host": socket.gethostname(),
    }


def _security_risk_label(risk: str) -> str:
    if risk == "HIGH":
        return cyan(f"[{risk}]")
    if risk == "MED":
        return yellow(f"[{risk}]")
    return dim(f"[{risk}]")


def _security_display_dashboard(snap: dict[str, Any]) -> None:
    stats = snap["stats"]
    listeners = snap["listeners"]
    connections = snap["connections"]
    suspicious = snap["suspicious"]
    now = time.strftime("%Y-%m-%d %H:%M:%S")

    print()
    print(bold("HOST FIREWALL"))
    print(dim("What is open and who you are talking to — right now"))
    print(dim("─" * 50))
    print(f"  {snap.get('host', '—')}  ·  {now}")
    print(
        f"  {stats['listen']} open ports  ·  {stats['established']} live  ·  "
        f"{stats['inbound_n']} in  ·  {stats['outbound_n']} out"
    )

    _info_section("Open ports on this PC")
    if not listeners:
        print(dim("  None visible — run as root/admin for full detail."))
    else:
        for entry in listeners[:35]:
            brand = entry.get("brand", entry["service"])
            port_tag = dim(f":{entry['port']} {entry['proto'].upper()}")
            proc = entry["process"]
            proc_s = dim(proc) if proc not in ("—", "unknown") else dim("—")
            print(
                f"  {_security_brand_highlight(brand)}  {port_tag}  "
                f"{proc_s}  {_security_kind_tag(entry.get('brand_kind', 'service'))}"
            )
        if len(listeners) > 35:
            print(dim(f"  … +{len(listeners) - 35} more"))

    _info_section("Live connections")
    if not connections:
        print(dim("  No active inbound/outbound sessions right now."))
    else:
        for card in connections[:40]:
            brand = card.get("brand", "Unknown")
            direction = card.get("direction", "other")
            arrow = cyan("→") if direction == "outbound" else green("←")
            dir_word = "to" if direction == "outbound" else "from"
            proc = card.get("process", "—")
            host = card.get("remote_name", "—")
            rip = card.get("r_ip") or ""
            endpoint = host if host not in ("—", "") else rip
            if host not in ("—", "") and rip:
                endpoint = f"{host}  {dim(rip)}"
            elif rip:
                endpoint = rip
            cnt = card.get("count", 1)
            cnt_s = dim(f"  ×{cnt}") if cnt > 1 else ""
            print(
                f"  {arrow} {_security_brand_highlight(brand)}  "
                f"{_security_kind_tag(card.get('brand_kind', ''))}  "
                f"{dim(dir_word)}  {proc}{cnt_s}"
            )
            if endpoint:
                print(f"      {dim(str(endpoint)[:56])}")

    print()
    if suspicious:
        print(yellow(bold("  ⚠  SUSPICIOUS ACTIVITY")))
        print(dim("  ─────────────────────────────"))
        for f in suspicious:
            print(
                f"  {yellow(str(f['id']))}  {_security_risk_label(f['risk'])}  "
                f"{f['summary']}"
            )
    else:
        print(green("  ✓  No suspicious activity detected."))


def _security_manual_commands(f: dict[str, Any]) -> list[str]:
    port = f["port"]
    proto = f["proto"]
    remote = f["remote"]
    r_ip = remote.split(":")[0] if remote and remote != "—" else None
    fam = _platform_family()
    cmds: list[str] = []
    if f["pid"]:
        cmds.append(f"# End process: kill {f['pid']}  ({f['process']})")
    if f["kind"] == "LISTEN" and port:
        if fam == "windows":
            cmds.append(
                f'netsh advfirewall firewall add rule name="ScorpioBlockIn{port}" '
                f"dir=in action=block protocol={proto.upper()} localport={port}"
            )
        elif fam in ("linux", "freebsd"):
            cmds.append(
                f"sudo iptables -I INPUT -p {proto} --dport {port} -j DROP"
            )
        elif fam == "darwin":
            cmds.append(
                f"# Block inbound {proto}/{port} — use pf or System Settings → Firewall"
            )
    if f["kind"] in ("OUTBOUND", "INBOUND") and r_ip and port:
        if fam == "windows":
            cmds.append(
                f'netsh advfirewall firewall add rule name="ScorpioBlockOut" '
                f"dir=out action=block remoteip={r_ip} remoteport={port} "
                f"protocol={proto.upper()}"
            )
        elif fam in ("linux", "freebsd"):
            cmds.append(
                f"sudo iptables -I OUTPUT -d {r_ip} -p {proto} --dport {port} -j DROP"
            )
    return cmds


def _security_terminate_pid(pid: int) -> bool:
    if psutil is None:
        return False
    try:
        proc = psutil.Process(pid)
        name = proc.name()
        confirm = input(
            dim(f"Terminate {name} (PID {pid})? [y/N]: ")
        ).strip().lower()
        if confirm not in ("y", "yes"):
            print(dim("Skipped."))
            return False
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except psutil.TimeoutExpired:
            proc.kill()
        print(green(f"Process {name} (PID {pid}) stopped."))
        return True
    except psutil.NoSuchProcess:
        print(yellow("Process already exited."))
        return True
    except psutil.AccessDenied:
        print(yellow("Permission denied — run Network Scorpio as root/administrator."))
        return False


def _security_block_inbound_port(port: int, proto: str) -> bool:
    fam = _platform_family()
    pname = proto.upper()
    confirm = input(
        dim(f"Add firewall rule to block inbound {proto}/{port}? [y/N]: ")
    ).strip().lower()
    if confirm not in ("y", "yes"):
        print(dim("Skipped."))
        return False
    if fam == "windows":
        rule = f"ScorpioBlockIn{port}{proto}"
        r = _run_cmd(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule}", "dir=in", "action=block",
                f"protocol={pname}", f"localport={port}",
            ],
            capture=True,
            timeout=30,
        )
        if r.returncode == 0:
            print(green(f"Inbound {proto}/{port} blocked (Windows Firewall)."))
            return True
        print(yellow((r.stderr or r.stdout or "Firewall rule failed.").strip()))
        return False
    if fam == "linux":
        if shutil.which("iptables"):
            r = _run_cmd(
                [
                    "iptables", "-I", "INPUT", "-p", proto,
                    "--dport", str(port), "-j", "DROP",
                ],
                capture=True,
                timeout=15,
            )
            if r.returncode == 0:
                print(green(f"Inbound {proto}/{port} blocked (iptables)."))
                return True
        print(yellow("iptables failed or needs sudo. Commands printed below."))
        return False
    if fam == "darwin":
        print(
            yellow(
                "macOS: enable Firewall in System Settings, or add a pf rule manually."
            )
        )
        return False
    print(yellow("Automatic firewall block not available on this OS."))
    return False


def _security_block_outbound(host: str, port: int, proto: str) -> bool:
    fam = _platform_family()
    pname = proto.upper()
    confirm = input(
        dim(f"Block outbound {proto} to {host}:{port}? [y/N]: ")
    ).strip().lower()
    if confirm not in ("y", "yes"):
        print(dim("Skipped."))
        return False
    if fam == "windows":
        rule = f"ScorpioBlockOut{host.replace('.', '')}{port}"
        r = _run_cmd(
            [
                "netsh", "advfirewall", "firewall", "add", "rule",
                f"name={rule}", "dir=out", "action=block",
                f"protocol={pname}", f"remoteip={host}", f"remoteport={port}",
            ],
            capture=True,
            timeout=30,
        )
        if r.returncode == 0:
            print(green(f"Outbound to {host}:{port} blocked."))
            return True
        print(yellow((r.stderr or r.stdout or "Rule failed.").strip()))
        return False
    if fam == "linux" and shutil.which("iptables"):
        r = _run_cmd(
            [
                "iptables", "-I", "OUTPUT", "-d", host, "-p", proto,
                "--dport", str(port), "-j", "DROP",
            ],
            capture=True,
            timeout=15,
        )
        if r.returncode == 0:
            print(green(f"Outbound to {host}:{port} blocked (iptables)."))
            return True
        print(yellow("iptables needs root. See manual commands."))
        return False
    print(yellow("Use manual firewall commands on this platform."))
    return False


def _security_fix_menu(f: dict[str, Any]) -> None:
    print()
    print(bold(f"Fix finding #{f['id']}"))
    print(dim(f"  {f['summary']}"))
    print()
    opts: list[tuple[str, str]] = []
    if f["pid"]:
        opts.append(("1", f"Stop process (PID {f['pid']} — {f['process']})"))
    if f["kind"] == "LISTEN" and f["port"]:
        opts.append(("2", f"Block inbound {f['proto']}/{f['port']} (firewall)"))
    if f["kind"] in ("OUTBOUND", "INBOUND") and f["remote"] not in ("—", ""):
        parts = f["remote"].rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            opts.append(("3", f"Block outbound to {f['remote']}"))
    opts.append(("4", "Show manual commands (copy/paste)"))
    opts.append(("0", "Back"))
    for code, label in opts:
        print(f"  {yellow(code)}  {label}")
    print()
    pick = input(dim("Choose action: ")).strip()
    if pick == "0":
        return
    if pick == "1" and f["pid"]:
        _security_terminate_pid(f["pid"])
        return
    if pick == "2" and f["kind"] == "LISTEN" and f["port"]:
        _security_block_inbound_port(f["port"], f["proto"])
        return
    if pick == "3" and f["remote"] not in ("—", ""):
        parts = f["remote"].rsplit(":", 1)
        if len(parts) == 2 and parts[1].isdigit():
            _security_block_outbound(parts[0], int(parts[1]), f["proto"])
        return
    if pick == "4":
        print()
        print(bold("Manual commands"))
        for line in _security_manual_commands(f):
            print(f"  {line}")
        return
    print(yellow("Invalid choice."))


def _security_remediation_loop(findings: list[dict[str, Any]]) -> None:
    print()
    print(bold("Remediation"))
    print(
        dim(
            "Review each alert before acting. Stopping processes or changing "
            "firewall rules can disrupt legitimate services."
        )
    )
    while True:
        print()
        for f in findings:
            print(f"  {yellow(str(f['id']))}  {_security_risk_label(f['risk'])}  {f['summary']}")
        print(f"  {yellow('0')}  Done with fixes")
        print()
        pick = input(dim("Fix finding # (0 = done): ")).strip()
        if pick in ("0", ""):
            break
        if not pick.isdigit():
            print(yellow("Enter a number from the list."))
            continue
        idx = int(pick)
        match = next((f for f in findings if f["id"] == idx), None)
        if not match:
            print(yellow("Unknown finding number."))
            continue
        _security_fix_menu(match)


def run_network_security() -> None:
    print()
    print(bold("Network Security"))
    print(
        dim(
            "Host firewall view: open ports, who is connected, and live traffic "
            "on this computer. Use only on systems you own or may administer."
        )
    )
    print()

    if psutil is None:
        print(yellow("Install psutil: pip install psutil"))
        _print_done()
        return

    snap = _run_with_spinner(
        "Mapping apps, websites, and open ports…",
        _security_build_snapshot,
    )
    _security_display_dashboard(snap)
    suspicious = snap["suspicious"]

    if suspicious:
        print()
        _security_remediation_loop(suspicious)
    elif snap["findings"]:
        print()
        print(dim("Minor notices hidden. No suspicious traffic flagged."))

    print()
    _print_done()


def print_menu() -> None:
    print(bold("Options"))
    print(f"  {yellow('1')}  Network info")
    print(f"  {yellow('2')}  Scan your network")
    print(f"  {yellow('3')}  Network Security")
    print(f"  {yellow('4')}  Troubleshoot User")
    print(f"  {yellow('5')}  Internet speed test")
    print(f"  {yellow('6')}  Configure DNS")
    print(f"  {yellow('7')}  Exit")
    print()


def main() -> None:
    ensure_environment()
    clear_screen()
    print_header()

    while True:
        print_menu()
        choice = input(dim("Enter choice: ")).strip().lower()

        if not choice:
            continue

        if choice in ("1", "01"):
            try:
                run_network_intel()
            except KeyboardInterrupt:
                print(dim("\nCancelled."))
            if _post_done_prompt() == "exit":
                print()
                print(dim(f"Goodbye — {TOOL_NAME}"))
                break
            print()
        elif choice in ("2", "02"):
            try:
                run_network_host_survey()
            except KeyboardInterrupt:
                print(dim("\nCancelled."))
            if _post_done_prompt() == "exit":
                print()
                print(dim(f"Goodbye — {TOOL_NAME}"))
                break
            print()
        elif choice in ("3", "03"):
            try:
                run_network_security()
            except KeyboardInterrupt:
                print(dim("\nCancelled."))
            if _post_done_prompt() == "exit":
                print()
                print(dim(f"Goodbye — {TOOL_NAME}"))
                break
            print()
        elif choice in ("4", "04"):
            try:
                run_troubleshoot_host()
            except KeyboardInterrupt:
                print(dim("\nCancelled."))
            if _post_done_prompt() == "exit":
                print()
                print(dim(f"Goodbye — {TOOL_NAME}"))
                break
            print()
        elif choice in ("5", "05"):
            try:
                run_speed_test()
            except Exception as e:
                if type(e).__name__ == "SpeedtestException":
                    print(yellow(f"Speed test error: {e}"), file=sys.stderr)
                else:
                    raise
            except KeyboardInterrupt:
                print(dim("\nCancelled."))
            if _post_done_prompt() == "exit":
                print()
                print(dim(f"Goodbye — {TOOL_NAME}"))
                break
            print()
        elif choice in ("6", "06"):
            try:
                run_configure_dns()
            except KeyboardInterrupt:
                print(dim("\nCancelled."))
            print()
            _print_done()
            if _post_done_prompt() == "exit":
                print()
                print(dim(f"Goodbye — {TOOL_NAME}"))
                break
            print()
        elif choice in ("7", "q", "quit", "exit"):
            print()
            print(dim(f"Goodbye — {TOOL_NAME}"))
            break
        else:
            print(yellow("Unknown option. Try 1–7."))
            print()


if __name__ == "__main__":
    try:
        _check_python_version()
        main()
    except KeyboardInterrupt:
        print(dim("\nInterrupted."))
        sys.exit(130)
    except OSError as e:
        print(yellow(f"System error: {e}"), file=sys.stderr)
        sys.exit(1)
