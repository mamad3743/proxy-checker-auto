import subprocess
import platform
import concurrent.futures

INPUT = "hosts.txt"
OUTPUT = "working_ping.txt"
COUNT = 2
TIMEOUT = 3

IS_WINDOWS = platform.system().lower() == "windows"

# ANSI colors (most Windows 10+ terminals support these; CMD may show raw codes on old versions)
GREEN = chr(27) + "[92m"
RED = chr(27) + "[91m"
CYAN = chr(27) + "[96m"
BOLD = chr(27) + "[1m"
RESET = chr(27) + "[0m"


def build_ping_cmd(ip):
    if IS_WINDOWS:
        # -n = count, -w = timeout in milliseconds
        return ["ping", "-n", str(COUNT), "-w", str(TIMEOUT * 1000), ip]
    else:
        # -c = count, -W = timeout in seconds (Linux/Alpine/Termux)
        return ["ping", "-c", str(COUNT), "-W", str(TIMEOUT), ip]


def ping(entry):
    parts = entry.strip().split(",")
    if len(parts) != 2:
        return None
    hostname, ip = parts[0].strip(), parts[1].strip()
    try:
        result = subprocess.run(
            build_ping_cmd(ip),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COUNT * TIMEOUT + 5
        )
        alive = result.returncode == 0
    except Exception:
        alive = False
    return (hostname, ip, alive)


def main():
    with open(INPUT) as f:
        entries = [l for l in f if l.strip()]

    print(BOLD + CYAN + "\n  Railway TCP Proxy Health Check" + RESET)
    print(CYAN + "  " + "-" * 45 + RESET + "\n")

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
        for r in ex.map(ping, entries):
            if r is None:
                continue
            hostname, ip, alive = r
            results.append(r)
            if alive:
                tag = GREEN + BOLD + " ONLINE " + RESET
            else:
                tag = RED + BOLD + " OFFLINE" + RESET
            print("  [" + tag + "]  " + hostname.ljust(30) + " " + ip)

    working = [r for r in results if r[2]]

    with open(OUTPUT, "w") as f:
        for hostname, ip, alive in working:
            f.write(hostname + "," + ip + chr(10))

    print(CYAN + "\n  " + "-" * 45 + RESET)
    print(BOLD + "  Summary: " + RESET + GREEN + str(len(working)) + RESET +
          " / " + str(len(results)) + " proxies online")
    print("  Saved to: " + BOLD + OUTPUT + RESET + "\n")


main()
