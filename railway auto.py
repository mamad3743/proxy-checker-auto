"""
Railway TCP Proxy — Auto Discover + IP Ping Check
---------------------------------------------------
Run it, paste your Railway API token, pick a project from a menu,
let Railway's own picker choose environment/service, and the rest
is automatic: create a TCP proxy, resolve its edge hostname to an
IP (the hostname itself does not answer ICMP ping), save it into
hosts.txt, ping-check every known edge IP, and optionally clean up
the temporary proxy at the end.

Note: Railway now allows up to 3 TCP proxies per service instance
(it used to be limited to 1).

Requirements:
- Railway CLI installed and on PATH: https://docs.railway.com/guides/cli
  (npm install -g @railway/cli   OR   bash <(curl -fsSL cli.new))
"""

import getpass
import itertools
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import concurrent.futures

HOSTS_FILE = "hosts.txt"
PING_OUTPUT = "working_ping.txt"
PING_COUNT = 2
PING_TIMEOUT = 3
IS_WINDOWS = platform.system().lower() == "windows"

# On Windows, npm installs `railway` as a .cmd shim. subprocess.run(["railway", ...])
# without shell=True often can't resolve that shim even though it works fine when
# typed directly into cmd.exe. shutil.which() correctly checks PATHEXT (.cmd/.bat/.exe)
# and returns the real, full path — resolve it once here and use it everywhere.
RAILWAY_BIN = shutil.which("railway") or "railway"

GREEN = chr(27) + "[92m"
RED = chr(27) + "[91m"
CYAN = chr(27) + "[96m"
YELLOW = chr(27) + "[93m"
MAGENTA = chr(27) + "[95m"
BOLD = chr(27) + "[1m"
DIM = chr(27) + "[2m"
RESET = chr(27) + "[0m"

HOST_RE = re.compile(r"([a-zA-Z0-9.-]+\.proxy\.rlwy\.net)\D+(\d+)")

LOGO = r"""
   ___       _ _
  | _ \__ _ (_) |_ ____ ____ _ _  _
  |   / _` || | \ V  V / _` | || |
  |_|_\__,_||_|_|\_/\_/\__,_|\_, |
       TCP Proxy Toolkit     |__/
"""


# ------------------------------------------------------------- UI helpers --

def credit_box():
    lines = [
        "Telegram : @mamadi1048",
        "GitHub   : github.com/mamad3743/proxy-checker-auto",
    ]
    max_len = max(len(l) for l in lines)
    inner = max_len + 2
    print("  " + CYAN + "╔" + "═" * inner + "╗" + RESET)
    for l in lines:
        content = " " + l + " " * (max_len - len(l)) + " "
        print("  " + CYAN + "║" + RESET + BOLD + content + RESET + CYAN + "║" + RESET)
    print("  " + CYAN + "╚" + "═" * inner + "╝" + RESET)
    print()


def banner(text):
    print(BOLD + CYAN + "\n  " + text + RESET)
    print(CYAN + "  " + "-" * 50 + RESET)


def ok(text):
    print(GREEN + "  ✓ " + RESET + text)


def fail(text):
    print(RED + "  ✗ " + RESET + text)


def info(text):
    print(DIM + "  » " + text + RESET)


class Spinner:
    """Simple animated spinner for slow subprocess calls."""

    FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(self, message):
        self.message = message
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin)

    def _spin(self):
        for frame in itertools.cycle(self.FRAMES):
            if self._stop.is_set():
                break
            sys.stdout.write("\r  " + CYAN + frame + RESET + " " + self.message)
            sys.stdout.flush()
            time.sleep(0.08)
        sys.stdout.write("\r" + " " * (len(self.message) + 4) + "\r")
        sys.stdout.flush()

    def __enter__(self):
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()


# --------------------------------------------------------- railway calls --

def run_railway(args, env, capture=True):
    cmd = [RAILWAY_BIN] + args
    return subprocess.run(
        cmd,
        env=env,
        stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.PIPE if capture else None,
        text=True,
    )


def check_cli_installed():
    try:
        subprocess.run([RAILWAY_BIN, "--version"], stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, text=True, check=True)
        return True
    except Exception:
        return False


def login(env):
    with Spinner("Verifying token..."):
        result = run_railway(["whoami"], env)
    if result.returncode != 0:
        fail("Login failed: " + (result.stderr or result.stdout).strip())
        return False
    ok("Logged in as " + BOLD + result.stdout.strip() + RESET)
    return True


def fetch_projects(env):
    """Return list of dicts: {id, name, workspace}. Empty list on failure."""
    with Spinner("Fetching your projects..."):
        result = run_railway(["list", "--json"], env)
    if result.returncode != 0 or not result.stdout.strip():
        return []
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []

    if isinstance(data, dict):
        data = data.get("projects") or data.get("data") or []
    if not isinstance(data, list):
        return []

    projects = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pid = item.get("id") or item.get("projectId")
        name = item.get("name") or item.get("projectName") or "(unnamed)"
        workspace = item.get("workspace")
        if isinstance(workspace, dict):
            workspace = workspace.get("name")
        workspace = workspace or item.get("workspaceName") or item.get("team") or "Personal"
        if pid:
            projects.append({"id": pid, "name": name, "workspace": workspace})
    return projects


def pick_project(env):
    projects = fetch_projects(env)
    if not projects:
        info("Could not auto-list projects, showing `railway list` directly:")
        run_railway(["list"], env, capture=False)
        return input("\n  Enter the Project ID or name: ").strip()

    print()
    for i, p in enumerate(projects, 1):
        print("   " + MAGENTA + BOLD + f"[{i}]" + RESET +
              f"  {p['name']}  " + DIM + f"({p['workspace']})" + RESET)
    print()

    while True:
        choice = input("  Pick a project (number): ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(projects):
            return projects[int(choice) - 1]["id"]
        fail("Invalid choice, try again.")


def link_project(env, project_id):
    """Let Railway's own picker handle team/environment/service selection."""
    banner("Link Project (choose environment & service)")
    result = subprocess.run([RAILWAY_BIN, "link", "-p", project_id], env=env)
    return result.returncode == 0


def create_proxy(env, port):
    with Spinner("Creating TCP proxy..."):
        result = run_railway(["tcp-proxy", "create", "--port", str(port)], env)
    if result.returncode != 0:
        fail("Failed to create proxy: " + (result.stderr or result.stdout).strip())
        return False
    ok("Proxy create requested.")
    return True


def list_proxies(env):
    result = run_railway(["tcp-proxy", "list", "--json"], env)
    text = result.stdout.strip()

    entries = []
    if result.returncode == 0 and text:
        try:
            data = json.loads(text)
            if isinstance(data, list):
                for item in data:
                    host = item.get("domain") or item.get("proxyDomain")
                    port = item.get("proxyPort") or item.get("port")
                    pid = item.get("id")
                    if host:
                        entries.append((host, port, pid))
        except json.JSONDecodeError:
            pass

    if not entries:
        plain = run_railway(["tcp-proxy", "list"], env)
        for match in HOST_RE.finditer(plain.stdout):
            entries.append((match.group(1), match.group(2), None))

    return entries


def delete_proxy(env, identifier):
    """identifier can be a proxy ID or its domain (both are accepted by the CLI)."""
    result = run_railway(["tcp-proxy", "delete", identifier, "--yes"], env)
    return result.returncode == 0


def resolve_ip(hostname):
    try:
        return socket.gethostbyname(hostname)
    except socket.gaierror:
        return None


# --------------------------------------------------------------- hosts.txt --

def load_hosts():
    if not os.path.exists(HOSTS_FILE):
        return {}
    hosts = {}
    with open(HOSTS_FILE) as f:
        for line in f:
            line = line.strip()
            if not line or "," not in line:
                continue
            h, ip = line.split(",", 1)
            hosts[h.strip()] = ip.strip()
    return hosts


def save_hosts(hosts):
    with open(HOSTS_FILE, "w") as f:
        for h, ip in sorted(hosts.items()):
            f.write(h + "," + ip + "\n")


# ------------------------------------------------------------------- ping --

def build_ping_cmd(ip):
    if IS_WINDOWS:
        return ["ping", "-n", str(PING_COUNT), "-w", str(PING_TIMEOUT * 1000), ip]
    return ["ping", "-c", str(PING_COUNT), "-W", str(PING_TIMEOUT), ip]


def ping_one(entry):
    hostname, ip = entry
    try:
        result = subprocess.run(
            build_ping_cmd(ip),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=PING_COUNT * PING_TIMEOUT + 5,
        )
        alive = result.returncode == 0
    except Exception:
        alive = False
    return (hostname, ip, alive)


def ping_all(hosts):
    banner("Ping Check (by IP — domains don't answer ICMP)")
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(ping_one, hosts.items()):
            hostname, ip, alive = r
            results.append(r)
            tag = (GREEN + BOLD + " ONLINE " + RESET) if alive else (RED + BOLD + " OFFLINE" + RESET)
            print("  [" + tag + "]  " + hostname.ljust(30) + " " + ip)

    working = [r for r in results if r[2]]
    with open(PING_OUTPUT, "w") as f:
        for hostname, ip, alive in working:
            f.write(hostname + "," + ip + "\n")

    print(CYAN + "\n  " + "-" * 50 + RESET)
    print(BOLD + "  Summary: " + RESET + GREEN + str(len(working)) + RESET +
          " / " + str(len(results)) + " online")
    print("  Saved online list to: " + BOLD + PING_OUTPUT + RESET + "\n")


def do_create_flow(env):
    banner("Create a TCP Proxy")
    print("  " + DIM + "Railway now allows up to 3 TCP proxies per service." + RESET)
    print("  " + DIM + "Common ports: 5432 Postgres · 6379 Redis · 3306 MySQL · 27017 MongoDB" + RESET)

    before = {p[0] for p in list_proxies(env)}
    if len(before) >= 3:
        fail("This service already has 3 TCP proxies (Railway's current max). Delete one first.")
        return

    port = input("  Internal application port to expose: ").strip()
    if not create_proxy(env, port):
        return

    info("Looking up assigned proxy domain...")
    proxies = list_proxies(env)
    if not proxies:
        fail("Could not read back the new proxy. Check the dashboard.")
        return

    # Multiple proxies can now exist on one service, so diff against the
    # pre-creation list instead of assuming the last entry is the new one.
    new_ones = [p for p in proxies if p[0] not in before]
    hostname, proxy_port, proxy_id = new_ones[0] if new_ones else proxies[-1]
    ok("Assigned: " + BOLD + hostname + ":" + str(proxy_port) + RESET)

    ip = resolve_ip(hostname)
    if not ip:
        fail("DNS resolution failed for " + hostname)
        return
    ok("Resolved IP: " + BOLD + ip + RESET)

    hosts = load_hosts()
    is_new = hostname not in hosts
    hosts[hostname] = ip
    save_hosts(hosts)
    if is_new:
        print(YELLOW + "  ★ New edge hostname added to hosts.txt!" + RESET)
    else:
        info("Hostname already known, IP refreshed in hosts.txt.")

    ping_all(hosts)

    identifier = proxy_id or hostname
    remove = input("  Delete this discovery proxy now? [y/N]: ").strip().lower()
    if remove == "y":
        if delete_proxy(env, identifier):
            ok("Proxy deleted.")
        else:
            fail("Could not delete automatically — remove it from the dashboard.")


def do_delete_flow(env):
    banner("Delete an Existing TCP Proxy")
    proxies = list_proxies(env)
    if not proxies:
        info("This service has no TCP proxies right now.")
        return

    print()
    for i, (hostname, port, pid) in enumerate(proxies, 1):
        print("   " + MAGENTA + BOLD + f"[{i}]" + RESET + f"  {hostname}:{port}")
    print()

    choice = input("  Pick a proxy to delete (number, or 'a' for all, Enter to cancel): ").strip().lower()
    if not choice:
        info("Cancelled.")
        return

    if choice == "a":
        targets = proxies
    elif choice.isdigit() and 1 <= int(choice) <= len(proxies):
        targets = [proxies[int(choice) - 1]]
    else:
        fail("Invalid choice.")
        return

    confirm = input(f"  Really delete {len(targets)} proxy(ies)? [y/N]: ").strip().lower()
    if confirm != "y":
        info("Cancelled.")
        return

    for hostname, port, pid in targets:
        identifier = pid or hostname
        if delete_proxy(env, identifier):
            ok(f"Deleted {hostname}:{port}")
        else:
            fail(f"Could not delete {hostname}:{port}")


# ------------------------------------------------------------------- main --

def main():
    print(MAGENTA + BOLD + LOGO + RESET)
    credit_box()

    if not check_cli_installed():
        fail("Railway CLI not found on PATH.")
        print("  Install it first:")
        print("    npm install -g @railway/cli")
        print("    (or) bash <(curl -fsSL cli.new)")
        sys.exit(1)

    banner("Step 1 — Login")
    token = getpass.getpass("  Railway API token (input hidden): ").strip()
    if not token:
        fail("No token entered, aborting.")
        sys.exit(1)

    # Account/workspace token -> RAILWAY_API_TOKEN. Kept only in this
    # subprocess environment, never written to disk or logged.
    env = os.environ.copy()
    env["RAILWAY_API_TOKEN"] = token
    env.pop("RAILWAY_TOKEN", None)

    if not login(env):
        sys.exit(1)

    banner("Step 2 — Choose your project")
    project_id = pick_project(env)
    if not project_id:
        fail("No project selected.")
        sys.exit(1)

    if not link_project(env, project_id):
        fail("Could not link the project (environment/service selection).")
        sys.exit(1)
    ok("Project linked.")

    banner("Step 3 — What do you want to do?")
    print("   " + MAGENTA + BOLD + "[1]" + RESET + "  Create a new TCP proxy")
    print("   " + MAGENTA + BOLD + "[2]" + RESET + "  Delete an existing TCP proxy")
    print("   " + MAGENTA + BOLD + "[3]" + RESET + "  Just ping-check hosts.txt")
    print()
    choice = input("  Choose (1/2/3): ").strip()

    if choice == "1":
        do_create_flow(env)
    elif choice == "2":
        do_delete_flow(env)
    elif choice == "3":
        ping_all(load_hosts())
    else:
        fail("Invalid choice.")
        sys.exit(1)

    print(BOLD + GREEN + "\n  Done.\n" + RESET)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(RED + "\n\n  Cancelled.\n" + RESET)
