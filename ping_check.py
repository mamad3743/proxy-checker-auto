#!/usr/bin/env python3
"""Ping every IP listed in hosts.txt and save the online ones to working_ping.txt."""

import sys

import toolkit as tk


def main():
    tk.setup_terminal()

    if not tk.ping_available():
        print(tk.RED + tk.ping_missing_help() + tk.RESET)
        sys.exit(1)

    hosts = tk.load_hosts()
    if not hosts:
        print(tk.RED + "  No valid 'hostname,ip' lines found in " + tk.HOSTS_FILE + tk.RESET)
        sys.exit(1)

    tk.ping_all(hosts, title="Railway TCP Proxy Health Check")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n  Cancelled.")
