"""Shared helpers for the Railway TCP proxy toolkit (colors, hosts.txt, ping)."""

import concurrent.futures
import ipaddress
import os
import platform
import re
import shutil
import subprocess
import sys

# Always resolve files next to the scripts, not relative to the current dir.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOSTS_FILE = os.path.join(BASE_DIR, "hosts.txt")
PING_OUTPUT = os.path.join(BASE_DIR, "working_ping.txt")

PING_COUNT = 2
PING_TIMEOUT = 3  # seconds

_SYSTEM = platform.system().lower()
IS_WINDOWS = _SYSTEM == "windows"
IS_MAC = _SYSTEM == "darwin"


def setup_terminal():
    """Enable ANSI colors on Windows 10+ and make output encoding safe."""
    if IS_WINDOWS:
        os.system("")  # flips the console into VT/ANSI mode
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_USE_COLOR = sys.stdout.isatty() and "NO_COLOR" not in os.environ


def _c(code):
    return "\033[" + code + "m" if _USE_COLOR else ""


GREEN = _c("92")
RED = _c("91")
CYAN = _c("96")
YELLOW = _c("93")
MAGENTA = _c("95")
BOLD = _c("1")
DIM = _c("2")
RESET = _c("0")


# --------------------------------------------------------------- hosts.txt --

def parse_host_line(line):
    """'hostname,ip' -> (hostname, ip) or None if the line is not valid."""
    line = line.strip()
    if not line or "," not in line:
        return None
    hostname, ip = (part.strip() for part in line.split(",", 1))
    try:
        ipaddress.ip_address(ip)  # also stops a bad line being passed to ping as an option
    except ValueError:
        return None
    return hostname, ip


def load_hosts():
    hosts = {}
    if not os.path.exists(HOSTS_FILE):
        return hosts
    with open(HOSTS_FILE, encoding="utf-8") as f:
        for line in f:
            parsed = parse_host_line(line)
            if parsed:
                hosts[parsed[0]] = parsed[1]
    return hosts


def save_hosts(hosts):
    with open(HOSTS_FILE, "w", encoding="utf-8", newline="\n") as f:
        for hostname, ip in sorted(hosts.items()):
            f.write(hostname + "," + ip + "\n")


# -------------------------------------------------------------------- ping --

_TTL_RE = re.compile(r"ttl\s*[=:]\s*\d+", re.IGNORECASE)


def ping_available():
    return shutil.which("ping") is not None


def ping_missing_help():
    return (
        "  The `ping` command was not found, so every host would show OFFLINE.\n"
        "  Install it first:\n"
        "    Termux : pkg install inetutils\n"
        "    iSH    : apk add iputils\n"
        "    Debian/Ubuntu : sudo apt install iputils-ping"
    )


def build_ping_cmd(ip):
    if IS_WINDOWS:
        # -n = count, -w = timeout in milliseconds
        return ["ping", "-n", str(PING_COUNT), "-w", str(PING_TIMEOUT * 1000), ip]
    if IS_MAC:
        # BSD/macOS ping: -W is in MILLISECONDS (on Linux it is seconds)
        return ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT * 1000), ip]
    # Linux / Termux / iSH: -W is in seconds
    return ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT), ip]


def ping_ip(ip):
    try:
        result = subprocess.run(
            build_ping_cmd(ip),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            text=True,
            errors="replace",
            timeout=PING_COUNT * PING_TIMEOUT + 5,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    if result.returncode != 0:
        return False
    if IS_WINDOWS:
        # Windows ping exits 0 even for "Destination host unreachable" replies
        # coming from a local router; a real echo reply always carries TTL=.
        return bool(_TTL_RE.search(result.stdout or ""))
    return True


def _ping_entry(entry):
    hostname, ip = entry
    return hostname, ip, ping_ip(ip)


def ping_all(hosts, title="Ping Check (by IP - domains don't answer ICMP)"):
    """Ping every IP in `hosts` ({hostname: ip}); save the online ones."""
    print(BOLD + CYAN + "\n  " + title + RESET)
    print(CYAN + "  " + "-" * 50 + RESET)

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for hostname, ip, alive in pool.map(_ping_entry, list(hosts.items())):
            results.append((hostname, ip, alive))
            tag = (GREEN + BOLD + " ONLINE " + RESET) if alive else (RED + BOLD + " OFFLINE" + RESET)
            print("  [" + tag + "]  " + hostname.ljust(30) + " " + ip)

    working = [r for r in results if r[2]]
    with open(PING_OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        for hostname, ip, _ in working:
            f.write(hostname + "," + ip + "\n")

    print(CYAN + "\n  " + "-" * 50 + RESET)
    print(BOLD + "  Summary: " + RESET + GREEN + str(len(working)) + RESET +
          " / " + str(len(results)) + " online")
    print("  Saved online list to: " + BOLD + PING_OUTPUT + RESET + "\n")
    return results
