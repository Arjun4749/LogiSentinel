"""Start LogiSentinel: one command runs the API and the web app together.

    python run.py            (opens your browser automatically)
    python run.py --no-browser --port 8000
"""
import argparse
import os
import socket
import sys
import threading
import time
import webbrowser

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
sys.path.insert(0, BACKEND)
os.chdir(BACKEND)


def free_port(preferred: int) -> int:
    for port in [preferred] + list(range(8001, 8021)):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if os.name != "nt":  # ignore sockets left in TIME_WAIT by a previous run (uvicorn does the same)
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    return preferred


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--no-browser", action="store_true")
    args = ap.parse_args()
    if sys.version_info < (3, 9):
        print("\n[!] Python 3.9 or newer is needed (3.10+ recommended). You have", sys.version.split()[0])
        sys.exit(1)
    try:
        import uvicorn  # noqa: F401
        import fastapi  # noqa: F401
    except ImportError:
        print("\n[!] Python packages are missing. Run:  pip install -r backend/requirements.txt\n")
        sys.exit(1)
    if not os.path.exists(os.path.join(BACKEND, "static", "index.html")):
        print("\n[!] The web app build (backend/static) is missing. See README: 'Rebuilding the web app'.\n")
    port = free_port(args.port)
    url = f"http://127.0.0.1:{port}"
    print("=" * 64)
    print("  LogiSentinel - Predictive Logistics & Forward Supply Chain")
    print(f"  Open in your browser:  {url}")
    print("  Demo logins: admin/admin123  planner/planner123  viewer/viewer123")
    print("  First start trains the AI model (about 5-10 seconds).")
    print("  Press CTRL+C in this window to stop.")
    print("=" * 64)
    if not args.no_browser:
        def _open():
            time.sleep(4)
            try:
                webbrowser.open(url)
            except Exception:
                pass
        threading.Thread(target=_open, daemon=True).start()
    import uvicorn
    uvicorn.run("app.main:app", host=args.host, port=port, log_level="warning")


if __name__ == "__main__":
    main()
