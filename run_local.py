"""Run SafeOrder on your own computer with one command (for judges and reviewers).

    python run_local.py            (Windows: py run_local.py, or double-click run_local.bat)

It needs Python 3.11 or newer and an internet connection the first time (to install the packages).
It does everything else: creates a private virtual environment in .venv, installs the pinned
packages, generates the synthetic data, starts the server with the website on one address and opens
your browser. Stop it with Ctrl+C. Only the Python standard library is used here.

Everything is a sandbox: synthetic sellers, demo money, a demo admin account. Nothing leaves your
computer. Options:  --port 8000   --no-browser   --reset (delete the local database and start clean)
"""

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parent
VENV = REPO / ".venv"
STAMP = VENV / ".safeorder-runtime-installed"
REQUIREMENTS = REPO / "requirements-runtime.txt"
DB_FILE = REPO / "data" / "safeorder.db"
# A demo admin for this local sandbox only (it opens the analyst console and the time controls).
ADMIN_PHONE = "01900000000"
ADMIN_PIN = "12345"


def say(text: str) -> None:
    print(f"[SafeOrder] {text}", flush=True)


def venv_python() -> Path:
    return VENV / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(cmd: list[str | Path], **kwargs) -> None:
    subprocess.run([str(part) for part in cmd], check=True, cwd=REPO, **kwargs)


def ensure_environment() -> Path:
    if sys.version_info < (3, 11):  # noqa: UP036 - judges may run an older Python than the project's
        sys.exit(
            f"Python 3.11 or newer is needed (this is {sys.version.split()[0]}).\n"
            "Install it from https://www.python.org/downloads/ or use Docker (see the README)."
        )
    python = venv_python()
    if not python.exists():
        say("creating a private Python environment in .venv (one time) ...")
        run([sys.executable, "-m", "venv", VENV])
    wanted = REQUIREMENTS.read_text(encoding="utf-8")
    if not STAMP.exists() or STAMP.read_text(encoding="utf-8") != wanted:
        say("installing the packages (one time, a few minutes) ...")
        pip = [python, "-m", "pip", "install", "--quiet", "--disable-pip-version-check"]
        run([*pip, "-r", REQUIREMENTS])
        STAMP.write_text(wanted, encoding="utf-8")
    return python


def ensure_synthetic_data(python: Path, env: dict[str, str]) -> None:
    synthetic = REPO / "data" / "synthetic" / "v1"
    if (synthetic / "sellers.csv").exists() and (synthetic / "seller_daily_stats.csv").exists():
        return
    say("generating the synthetic sellers (one time, about a minute) ...")
    run([python, "-m", "scripts.generate_sellers", "--version", "both"], env=env)
    warm = "from app.trust.dataset import load_features; load_features('v1'); load_features('v2')"
    run([python, "-c", warm], env=env)


def free_port(start: int) -> int:
    for port in range(start, start + 20):
        with socket.socket() as probe:
            if probe.connect_ex(("127.0.0.1", port)) != 0:
                return port
    sys.exit(f"No free port found between {start} and {start + 19}; use --port.")


def wait_until_up(url: str, process: subprocess.Popen, seconds: int = 180) -> bool:
    deadline = time.time() + seconds
    while time.time() < deadline:
        if process.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as reply:
                if reply.status == 200:
                    return True
        except OSError:
            time.sleep(1)
    return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the SafeOrder sandbox locally.")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--reset", action="store_true", help="delete the local database first")
    args = parser.parse_args()

    python = ensure_environment()
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'backend'}{os.pathsep}{REPO}", "PYTHONUTF8": "1"}
    ensure_synthetic_data(python, env)
    if args.reset and DB_FILE.exists():
        DB_FILE.unlink()
        say("local database deleted: starting clean")
    env.update(
        SAFEORDER_SERVE_FRONTEND="1",
        SAFEORDER_PERSIST="1",  # keep accounts between runs (data/safeorder.db, not in git)
        SAFEORDER_FULL_DEMO="1",  # all 3,000 synthetic sellers and the seven demo stories
        SAFEORDER_PROTECT_ADMIN="1",
        SAFEORDER_ADMIN_PHONE=ADMIN_PHONE,
        SAFEORDER_ADMIN_PIN=ADMIN_PIN,
        SAFEORDER_AUTOSEED_BACKGROUND="1",
    )
    port = free_port(args.port)
    if hasattr(signal, "SIGTERM"):  # a plain "kill" must also stop the server it started
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    url = f"http://localhost:{port}"
    say(f"starting the server on {url} ...")
    server = subprocess.Popen(
        [
            str(python),
            "-m",
            "uvicorn",
            "app.main:app",
            "--app-dir",
            "backend",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--log-level",
            "warning",
        ],  # fmt: skip
        cwd=REPO,
        env=env,
    )
    try:
        if not wait_until_up(url, server):
            sys.exit("The server did not start. Scroll up for the error message.")
        say(f"READY: open {url}")
        say(f"Demo admin (analyst console, time controls): phone {ADMIN_PHONE}, PIN {ADMIN_PIN}")
        say("Everything here is synthetic data and demo money. Press Ctrl+C to stop.")
        say("First start: the demo stories load in the background for a minute or two.")
        if not args.no_browser:
            webbrowser.open(url)
        server.wait()
    except KeyboardInterrupt:
        say("stopping ...")
    finally:
        if server.poll() is None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()


if __name__ == "__main__":
    main()
