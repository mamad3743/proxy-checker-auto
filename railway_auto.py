#!/usr/bin/env python3
"""
Railway TCP Proxy - Auto Discover + IP Ping Check
---------------------------------------------------
Run it, paste your Railway API token, pick a project from a menu,
let Railway's own picker choose environment/service, and the rest
is automatic: create a TCP proxy, resolve its edge hostname to an
IP (the hostname itself does not answer ICMP ping), save it into
hosts.txt, ping-check every known edge IP, and optionally clean up
the temporary proxy at the end.

Usage:
    python3 railway_auto.py        (Windows: python railway_auto.py)

If the Railway CLI is missing the script offers to install it.
"""

import getpass
import itertools
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import threading
import time

import toolkit as tk
from toolkit import (BOLD, CYAN, DIM, GREEN, MAGENTA, RED, RESET, YELLOW)

HOST_RE = re.compile(r"([a-zA-Z0-9.-]+\.proxy\.rlwy\.net)\D+(\d+)")

LOGO = r"""
   ___       _ _
  | _ \__ _ (_) |_ ____ ____ _ _  _
  |   / _` || | \ V  V / _` | || |
  |_|_\__,_||_|_|\_/\_/\__,_|\_, |
       TCP Proxy Toolkit     |__/
"""

RAILWAY_BIN = "railway"  # replaced by the full path in main()
PROXY_PENDING = False    # True while a proxy created by this run still exists


# ------------------------------------------------------------- UI helpers --

def banner(text):
    print(BOLD + CYAN + "\n  " + text + RESET)
    print(CYAN + "  " + "-" * 50 + RESET)


def ok(text):
    print(GREEN + "  \u2713 " + RESET + text)


def fail(text):
    print(RED + "  \u2717 " + RESET + text)


def info(text):
    print(DIM + "  \u00bb " + text + RESET)


def ask(prompt):
    """input() that turns Ctrl+D / closed stdin into a clean cancel."""
    try:
        return input(prompt).strip()
    except EOFError:
        raise KeyboardInterrupt


class Spinner:
    """Animated spinner for slow calls (plain message when not a terminal)."""

    FRAMES = ["\u280b", "\u2819", "\u2839", "\u2838", "\u283c",
              "\u2834", "\u2826", "\u2827", "\u2807", "\u280f"]

    def __init__(self, message):
        self.message = message
        self._animate = sys.stdout.isatty()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._spin, daemon=True)

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
        if self._animate:
            self._thread.start()
        else:
            info(self.message)
        return self

    def __exit__(self, *exc):
        if self._animate:
            self._stop.set()
            self._thread.join()


# --------------------------------------------------------- railway CLI ----

def find_railway():
    """Locate the railway executable (handles railway.cmd from npm on Windows)."""
    path = shutil.which("railway")
    if path:
        return path

    dirs = [os.path.join(os.path.expanduser("~"), ".railway", "bin")]
    npm = shutil.which("npm")
    if npm:
        try:
            prefix = subprocess.run(
                [npm, "prefix", "-g"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL, text=True, timeout=30,
            ).stdout.strip()
            if prefix:
                dirs += [prefix, os.path.join(prefix, "bin")]
        except (OSError, subprocess.SubprocessError):
            pass
    for d in dirs:
        path = shutil.which("railway", path=d)
        if path:
            return path
    return None


def install_cli():
    """Try to install the Railway CLI. Returns its path or None."""
    npm = shutil.which("npm")
    if npm:
        info("Running: npm install -g @railway/cli")
        if subprocess.run([npm, "install", "-g", "@railway/cli"]).returncode == 0:
            return find_railway()
        fail("npm install failed (on Linux/macOS a global install may need sudo).")

    if not tk.IS_WINDOWS and shutil.which("bash") and shutil.which("curl"):
        info("Running: bash <(curl -fsSL railway.com/install.sh)")
        rc = subprocess.run(["bash", "-c", "bash <(curl -fsSL railway.com/install.sh)"]).returncode
        if rc == 0:
            return find_railway()
        fail("The install script failed.")

    if tk.IS_WINDOWS:
        print("  Install manually with one of:")
        print("    npm install -g @railway/cli")
        print("    scoop install railway")
    return None


def ensure_cli():
    global RAILWAY_BIN
    path = find_railway()
    if not path:
        fail("Railway CLI not found on PATH.")
        answer = ask("  Install it now? [Y/n]: ").lower()
        if answer in ("", "y", "yes"):
            path = install_cli()
        if not path:
            print("  Install it yourself, then run this script again:")
            print("    npm install -g @railway/cli")
            print("    (or) bash <(curl -fsSL railway.com/install.sh)")
            sys.exit(1)
        ok("Railway CLI installed.")
    RAILWAY_BIN = path
    # A freshly installed CLI may live in a dir that is not on PATH yet.
    return path


def run_railway(args, env, capture=True, timeout=90):
    cmd = [RAILWAY_BIN] + args
    try:
        return subprocess.run(
            cmd,
            env=env,
            stdin=subprocess.DEVNULL if capture else None,  # never hang on a hidden prompt
            stdout=subprocess.PIPE if capture else None,
            stderr=subprocess.PIPE if capture else None,
            text=True,
            errors="replace",
            timeout=timeout if capture else None,
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 124, "", "timed out")
    except OSError as exc:
        return subprocess.CompletedProcess(cmd, 127, "", str(exc))


def login(env):
    with Spinner("Verifying token..."):
        result = run_railway(["whoami"], env)
    if result.returncode != 0:
        fail("Login failed: " + ((result.stderr or result.stdout) or "unknown error").strip())
        return False
    ok("Logged in: " + BOLD + (result.stdout or "").strip() + RESET)
    return True


def _project_from(item, workspace_hint=None):
    if not isinstance(item, dict):
        return None
    pid = item.get("id") or item.get("projectId")
    if not pid:
        return None
    name = item.get("name") or item.get("projectName") or "(unnamed)"
    workspace = item.get("workspace")
    if isinstance(workspace, dict):
        workspace = workspace.get("name")
    workspace = (workspace or item.get("workspaceName") or item.get("team")
                 or workspace_hint or "Personal")
    return {"id": pid, "name": name, "workspace": workspace}


def fetch_projects(env):
    """Return list of dicts: {id, name, workspace}. Empty list on failure."""
    with Spinner("Fetching your projects..."):
        result = run_railway(["list", "--json"], env)
    if result.returncode != 0 or not (result.stdout or "").strip():
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
        # Either a flat project list, or workspaces that contain a "projects" list.
        if isinstance(item, dict) and isinstance(item.get("projects"), list):
            for sub in item["projects"]:
                p = _project_from(sub, item.get("name"))
                if p:
                    projects.append(p)
        else:
            p = _project_from(item)
            if p:
                projects.append(p)
    return projects


def pick_project(env):
    projects = fetch_projects(env)
    if not projects:
        info("Could not auto-list projects, showing `railway list` directly:")
        run_railway(["list"], env, capture=False)
        return ask("\n  Enter the Project ID: ")

    print()
    for i, p in enumerate(projects, 1):
        print("   " + MAGENTA + BOLD + "[" + str(i) + "]" + RESET +
              "  " + p["name"] + "  " + DIM + "(" + str(p["workspace"]) + ")" + RESET)
    print()

    while True:
        choice = ask("  Pick a project (number): ")
        if choice.isdigit() and 1 <= int(choice) <= len(projects):
            return projects[int(choice) - 1]["id"]
        fail("Invalid choice, try again.")


def link_project(env, project_id):
    """Let Railway's own picker handle environment/service selection."""
    banner("Link Project (choose environment & service)")
    result = run_railway(["link", "-p", project_id], env, capture=False)
    return result.returncode == 0


# -------------------------------------------------------------- tcp proxy --

def _parse_proxy_json(text):
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    if isinstance(data, dict):
        lists = [v for v in data.values() if isinstance(v, list)]
        data = lists[0] if lists else [data]
    if not isinstance(data, list):
        return []

    entries = []
    for item in data:
        if not isinstance(item, dict):
            continue
        host = item.get("domain") or item.get("proxyDomain")
        port = item.get("proxyPort") or item.get("port")
        if not host and isinstance(item.get("endpoint"), str) and ":" in item["endpoint"]:
            host, _, port = item["endpoint"].rpartition(":")
        if host:
            entries.append((host, str(port) if port else "?", item.get("id")))
    return entries


def list_proxies(env):
    """Return [(hostname, proxy_port, proxy_id_or_None)] for the linked service."""
    result = run_railway(["tcp-proxy", "list", "--json"], env)
    entries = _parse_proxy_json(result.stdout or "") if result.returncode == 0 else []

    if not entries:
        plain = run_railway(["tcp-proxy", "list"], env)
        for match in HOST_RE.finditer(plain.stdout or ""):
            entries.append((match.group(1), match.group(2), None))

    seen, unique = set(), []
    for entry in entries:
        if (entry[0], entry[1]) not in seen:
            seen.add((entry[0], entry[1]))
            unique.append(entry)
    return unique


def create_proxy(env, port):
    with Spinner("Creating TCP proxy..."):
        result = run_railway(["tcp-proxy", "create", "--port", str(port)], env)
    if result.returncode != 0:
        fail("Failed to create proxy: " +
             ((result.stderr or result.stdout) or "unknown error").strip())
        return False
    ok("Proxy create requested.")
    return True


def wait_for_new_proxy(env, before, tries=10, delay=2):
    """Poll until a proxy that was not in `before` shows up."""
    known = {(h, p) for h, p, _ in before}
    with Spinner("Waiting for Railway to assign the proxy domain..."):
        for attempt in range(tries):
            for entry in list_proxies(env):
                if (entry[0], entry[1]) not in known:
                    return entry
            if attempt < tries - 1:
                time.sleep(delay)
    return None


def delete_proxy(env, entry):
    hostname, port, proxy_id = entry
    # Edge hostnames are shared between customers, so a bare domain is not unique.
    ident = proxy_id or (hostname + ":" + str(port))
    result = run_railway(["tcp-proxy", "delete", ident, "--yes"], env)
    return result.returncode == 0


def resolve_ip(hostname, tries=5, delay=2):
    for attempt in range(tries):
        try:
            return socket.gethostbyname(hostname)
        except socket.gaierror:
            if attempt < tries - 1:
                time.sleep(delay)
    return None


def ask_port():
    print("  " + DIM + "Common ports: 5432 Postgres \u00b7 6379 Redis \u00b7 "
          "3306 MySQL \u00b7 27017 MongoDB" + RESET)
    while True:
        raw = ask("  Internal application port to expose: ")
        if raw.isdigit() and 1 <= int(raw) <= 65535:
            return int(raw)
        fail("Enter a port number between 1 and 65535.")


# ------------------------------------------------------------------- main --

def main():
    global PROXY_PENDING
    tk.setup_terminal()
    print(MAGENTA + BOLD + LOGO + RESET)

    if not tk.ping_available():
        print(RED + tk.ping_missing_help() + RESET)
        sys.exit(1)

    ensure_cli()

    banner("Step 1 - Login")
    token = os.environ.get("RAILWAY_API_TOKEN", "").strip()
    if token:
        info("Using RAILWAY_API_TOKEN from the environment.")
    else:
        try:
            token = getpass.getpass("  Railway API token (input hidden): ").strip()
        except EOFError:
            raise KeyboardInterrupt
    if not token:
        fail("No token entered, aborting.")
        sys.exit(1)

    # Account/workspace token -> RAILWAY_API_TOKEN. Kept only in this
    # process' environment, never written to disk or logged.
    env = os.environ.copy()
    env["RAILWAY_API_TOKEN"] = token
    env.pop("RAILWAY_TOKEN", None)
    # A freshly installed CLI may not be on PATH; make sure children can find it.
    env["PATH"] = os.path.dirname(RAILWAY_BIN) + os.pathsep + env.get("PATH", "")

    if not login(env):
        sys.exit(1)

    banner("Step 2 - Choose your project")
    project_id = pick_project(env)
    if not project_id:
        fail("No project selected.")
        sys.exit(1)
    if not link_project(env, project_id):
        fail("Could not link the project (environment/service selection).")
        sys.exit(1)
    ok("Project linked.")

    banner("Step 3 - TCP proxy")
    existing = list_proxies(env)
    created = False
    entry = None
    if existing:
        # Don't hard-code Railway's per-service proxy limit (it has changed
        # before); let the user reuse a proxy or try to create another one.
        print()
        for i, e in enumerate(existing, 1):
            print("   " + MAGENTA + BOLD + "[" + str(i) + "]" + RESET +
                  "  use existing  " + e[0] + ":" + str(e[1]))
        print("   " + MAGENTA + BOLD + "[n]" + RESET + "  create a new proxy")
        print()
        while True:
            choice = (ask("  Your choice [1]: ") or "1").lower()
            if choice == "n":
                break
            if choice.isdigit() and 1 <= int(choice) <= len(existing):
                entry = existing[int(choice) - 1]
                break
            fail("Invalid choice, try again.")

    if entry is None:
        port = ask_port()
        if not create_proxy(env, port):  # Railway's own error (e.g. limit reached) is printed
            sys.exit(1)
        entry = wait_for_new_proxy(env, existing)
        if not entry:
            fail("Could not read back the new proxy. If it never becomes active, "
                 "redeploy the service and check the dashboard.")
            sys.exit(1)
        created = True
        PROXY_PENDING = True

    hostname, proxy_port, _ = entry
    ok("Assigned: " + BOLD + hostname + ":" + str(proxy_port) + RESET)

    with Spinner("Resolving " + hostname + "..."):
        ip = resolve_ip(hostname)
    if not ip:
        fail("DNS resolution failed for " + hostname)
        sys.exit(1)
    ok("Resolved IP: " + BOLD + ip + RESET)

    hosts = tk.load_hosts()
    is_new = hostname not in hosts
    changed = hosts.get(hostname) != ip
    hosts[hostname] = ip
    if changed:
        tk.save_hosts(hosts)
    if is_new:
        print(YELLOW + "  \u2605 New edge hostname added to hosts.txt!" + RESET)
    elif changed:
        info("Hostname already known, IP updated in hosts.txt.")
    else:
        info("Hostname already known, nothing changed in hosts.txt.")

    tk.ping_all(hosts)

    if created:
        if ask("  Delete this discovery proxy now? [y/N]: ").lower() == "y":
            if delete_proxy(env, entry):
                ok("Proxy deleted.")
                PROXY_PENDING = False
            else:
                fail("Could not delete the proxy automatically - remove it from the dashboard.")
        else:
            info("Proxy kept. Note: it stays on your service until you delete it.")

    print(BOLD + GREEN + "\n  Done.\n" + RESET)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(RED + "\n\n  Cancelled." + RESET)
        if PROXY_PENDING:
            print("  A TCP proxy created by this run is still on your service - "
                  "remove it from the dashboard if you don't need it.")
        print()
        sys.exit(130)
