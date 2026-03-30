"""
Clay Browser Helper — Self-Healing API Discovery

UNIX socket daemon wrapping Playwright/Chromium. Captures Clay API traffic
so Claude Code can discover correct input parameter names for new action types
without manual HAR exports.

Usage:
    python clay_browser.py launch [--headless]
    python clay_browser.py goto <url>
    python clay_browser.py snapshot
    python clay_browser.py screenshot [path]
    python clay_browser.py click <text> [--role button] [--nth 0]
    python clay_browser.py fill <text> [--placeholder "Search"]
    python clay_browser.py requests [--filter fields] [--last 5]
    python clay_browser.py close
"""

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone

RUNTIME_DIR = "/tmp/clay-browser"
SOCK_PATH = "/tmp/clay-browser/server.sock"
PID_PATH = "/tmp/clay-browser/server.pid"
REQUESTS_PATH = "/tmp/clay-browser/requests.jsonl"
LOG_PATH = "/tmp/clay-browser/daemon.log"

SESSION_FILE = os.path.join(os.path.dirname(__file__), "clay-session.json")


# ── Server (daemon) ──────────────────────────────────────────────────────────


class ClayBrowserServer:
    """Daemon: holds Playwright browser, listens on UNIX socket."""

    def __init__(self):
        self.browser = None
        self.context = None
        self.page = None
        self.pw = None
        self._pending = {}      # id(request) → entry dict
        self._captured = []     # completed entries (also in requests.jsonl)
        self._shutdown_requested = False

    def start(self, headless=False):
        """Launch browser, set up capture, serve forever."""
        os.makedirs(RUNTIME_DIR, exist_ok=True)

        # Write PID
        with open(PID_PATH, "w") as f:
            f.write(str(os.getpid()))

        # Clear previous requests log
        open(REQUESTS_PATH, "w").close()

        self._setup_browser(headless)
        self._setup_capture()
        self._serve_forever()

    def _setup_browser(self, headless):
        from playwright.sync_api import sync_playwright

        self.pw = sync_playwright().start()
        self.browser = self.pw.chromium.launch(headless=headless)
        self.context = self.browser.new_context(
            viewport={"width": 1440, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )

        # Inject session cookie
        cookie_value = self._load_cookie()
        self.context.add_cookies([{
            "name": "claysession",
            "value": cookie_value,
            "domain": ".clay.com",
            "path": "/",
            "httpOnly": True,
            "secure": True,
            "sameSite": "Lax",
        }])

        # Apply stealth
        try:
            from playwright_stealth import stealth_sync
            self.page = self.context.new_page()
            stealth_sync(self.page)
        except ImportError:
            self.page = self.context.new_page()

        print("[clay-browser] browser ready", flush=True)

    def _load_cookie(self) -> str:
        with open(SESSION_FILE) as f:
            data = json.load(f)
        return data["claysession"]

    def _setup_capture(self):
        """Attach request/response listeners for api.clay.com traffic."""
        self.page.on("request", self._on_request)
        self.page.on("response", self._on_response)

    def _on_request(self, request):
        if "api.clay.com" not in request.url:
            return
        entry = {
            "id": id(request),
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "url": request.url,
            "req_body": None,
        }
        if request.post_data:
            try:
                entry["req_body"] = json.loads(request.post_data)
            except (json.JSONDecodeError, TypeError):
                entry["req_body"] = request.post_data
        self._pending[id(request)] = entry

    def _on_response(self, response):
        if "api.clay.com" not in response.url:
            return
        req_id = id(response.request)
        entry = self._pending.pop(req_id, None)
        if not entry:
            return
        entry["status"] = response.status
        try:
            body = response.body()
            if len(body) < 1_000_000:
                entry["resp_body"] = json.loads(body)
            else:
                entry["resp_body"] = "(too large)"
        except Exception:
            entry["resp_body"] = None
        # Remove internal tracking id before persisting
        entry.pop("id", None)
        with open(REQUESTS_PATH, "a") as f:
            f.write(json.dumps(entry) + "\n")
        self._captured.append(entry)

    def _serve_forever(self):
        """Accept commands on UNIX socket. 0.5s timeout between accepts
        to let Playwright event handlers fire."""
        # Clean up stale socket
        if os.path.exists(SOCK_PATH):
            os.unlink(SOCK_PATH)

        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.bind(SOCK_PATH)
        sock.listen(1)
        sock.settimeout(0.5)

        print(f"[clay-browser] listening on {SOCK_PATH}", flush=True)

        while True:
            try:
                conn, _ = sock.accept()
            except socket.timeout:
                # Flush pending Playwright events (request/response callbacks)
                try:
                    self.page.evaluate("1")
                except Exception:
                    pass
                continue
            except OSError:
                break

            try:
                data = b""
                while True:
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\n" in data:
                        break

                line = data.decode("utf-8").strip()
                if not line:
                    continue

                cmd = json.loads(line)
                result = self._handle(cmd)
                conn.sendall((json.dumps(result) + "\n").encode("utf-8"))
            except Exception as e:
                try:
                    conn.sendall((json.dumps({"ok": False, "error": str(e)}) + "\n").encode("utf-8"))
                except Exception:
                    pass
            finally:
                conn.close()

            if self._shutdown_requested:
                self._shutdown()

    def _handle(self, cmd: dict) -> dict:
        """Dispatch to _cmd_* methods."""
        name = cmd.get("cmd", "")
        args = cmd.get("args", {})
        handler = getattr(self, f"_cmd_{name}", None)
        if not handler:
            return {"ok": False, "error": f"Unknown command: {name}"}
        try:
            return handler(args)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}"}

    # ── Commands ──────────────────────────────────────────────────────────────

    def _cmd_goto(self, args) -> dict:
        url = args.get("url", "")
        if not url:
            return {"ok": False, "error": "url required"}
        self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return {"ok": True, "title": self.page.title(), "url": self.page.url}

    def _cmd_snapshot(self, args) -> dict:
        snap = self.page.locator("body").aria_snapshot()
        return {"ok": True, "snapshot": snap}

    def _cmd_screenshot(self, args) -> dict:
        path = args.get("path", "/tmp/clay-browser/screenshot.png")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        self.page.screenshot(path=path, full_page=False)
        return {"ok": True, "path": path}

    def _cmd_click(self, args) -> dict:
        text = args.get("text", "")
        role = args.get("role")
        nth = args.get("nth")  # None means "not specified"

        if not text:
            return {"ok": False, "error": "text required"}

        if role:
            loc = self.page.get_by_role(role, name=text)
        else:
            # Try button first, fall back to text
            loc = self.page.get_by_role("button", name=text)
            if loc.count() == 0:
                loc = self.page.get_by_text(text)

        count = loc.count()
        if count == 0:
            return {"ok": False, "error": f"No element found: '{text}'"}
        if count > 1 and nth is None:
            return {
                "ok": False,
                "error": f"{count} matches found, use --nth to pick one",
                "count": count,
            }

        loc.nth(nth or 0).click()
        # Best-effort wait for triggered API calls
        try:
            self.page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        return {"ok": True, "clicked": text, "nth": nth}

    def _cmd_fill(self, args) -> dict:
        text = args.get("text", "")
        placeholder = args.get("placeholder")

        if not text:
            return {"ok": False, "error": "text required"}

        if placeholder:
            loc = self.page.get_by_placeholder(placeholder)
            count = loc.count()
            if count == 0:
                return {"ok": False, "error": f"No input with placeholder '{placeholder}'"}
            loc.first.fill(text)
        else:
            self.page.keyboard.type(text)

        return {"ok": True, "filled": text}

    def _cmd_requests(self, args) -> dict:
        filter_str = args.get("filter")
        last_n = args.get("last")

        entries = []
        if os.path.exists(REQUESTS_PATH):
            with open(REQUESTS_PATH) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        entries.append(json.loads(line))

        if filter_str:
            entries = [e for e in entries if filter_str in e.get("url", "")]

        if last_n:
            entries = entries[-last_n:]

        return {"ok": True, "count": len(entries), "requests": entries}

    def _cmd_eval(self, args) -> dict:
        js = args.get("js", "")
        if not js:
            return {"ok": False, "error": "js required"}
        result = self.page.evaluate(js)
        try:
            self.page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        return {"ok": True, "result": result}

    def _cmd_click_selector(self, args) -> dict:
        selector = args.get("selector", "")
        if not selector:
            return {"ok": False, "error": "selector required"}
        self.page.locator(selector).first.click()
        try:
            self.page.wait_for_load_state("networkidle", timeout=3000)
        except Exception:
            pass
        return {"ok": True, "clicked": selector}

    def _cmd_close(self, args) -> dict:
        # Schedule shutdown after response is sent
        self._shutdown_requested = True
        return {"ok": True, "message": "shutting down"}

    def _shutdown(self):
        """Clean shutdown — called after close response is sent."""
        try:
            self.page.close()
        except Exception:
            pass
        try:
            self.context.close()
        except Exception:
            pass
        try:
            self.browser.close()
        except Exception:
            pass
        try:
            self.pw.stop()
        except Exception:
            pass
        for path in [SOCK_PATH, PID_PATH]:
            if os.path.exists(path):
                os.unlink(path)
        print("[clay-browser] closed", flush=True)
        os._exit(0)


# ── Client (CLI) ──────────────────────────────────────────────────────────────


class ClayBrowserClient:
    """Connect to daemon, send command, return result."""

    def send(self, cmd: str, **kwargs) -> dict:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.connect(SOCK_PATH)
        except (FileNotFoundError, ConnectionRefusedError):
            return {"ok": False, "error": "Daemon not running. Run: python clay_browser.py launch"}

        payload = json.dumps({"cmd": cmd, "args": kwargs}) + "\n"
        sock.sendall(payload.encode("utf-8"))

        data = b""
        while True:
            chunk = sock.recv(65536)
            if not chunk:
                break
            data += chunk
            if b"\n" in data:
                break
        sock.close()

        text = data.decode("utf-8").strip()
        if not text:
            return {"ok": True, "message": "connection closed (daemon may have shut down)"}
        return json.loads(text)


# ── Launcher ──────────────────────────────────────────────────────────────────


def _is_daemon_alive() -> bool:
    """Check if a daemon process is still running."""
    if not os.path.exists(PID_PATH):
        return False
    with open(PID_PATH) as f:
        pid = int(f.read().strip())
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _cleanup_stale():
    """Remove stale socket/pid if daemon is dead."""
    if os.path.exists(PID_PATH) and not _is_daemon_alive():
        for path in [SOCK_PATH, PID_PATH]:
            if os.path.exists(path):
                os.unlink(path)


def launch_daemon(headless=False):
    """Fork a daemon process that runs the browser server."""
    _cleanup_stale()

    if _is_daemon_alive():
        with open(PID_PATH) as f:
            pid = f.read().strip()
        print(f"[clay-browser] already running (PID {pid})")
        return

    os.makedirs(RUNTIME_DIR, exist_ok=True)

    proc = subprocess.Popen(
        [sys.executable, __file__, "--daemon"] + (["--headless"] if headless else []),
        stdout=open(LOG_PATH, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )

    # Wait for socket to appear (up to 15s — browser launch can be slow)
    for _ in range(30):
        time.sleep(0.5)
        if os.path.exists(SOCK_PATH):
            # Verify socket is connectable
            try:
                s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                s.connect(SOCK_PATH)
                s.close()
                print(f"[clay-browser] launched. PID: {proc.pid}")
                return
            except (ConnectionRefusedError, OSError):
                continue

    # Timeout — check if process died
    if proc.poll() is not None:
        print(f"[clay-browser] daemon exited with code {proc.returncode}")
        print(f"[clay-browser] check log: {LOG_PATH}")
    else:
        print(f"[clay-browser] timeout waiting for socket (PID {proc.pid})")
        print(f"[clay-browser] check log: {LOG_PATH}")


# ── CLI ───────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Clay Browser Helper — self-healing API discovery",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    # Hidden daemon flag (used by launch_daemon)
    parser.add_argument("--daemon", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--headless", action="store_true", help="Run browser headless")

    sub = parser.add_subparsers(dest="command")

    # launch
    launch_p = sub.add_parser("launch", help="Start daemon + browser")
    launch_p.add_argument("--headless", action="store_true")

    # close
    sub.add_parser("close", help="Shutdown daemon")

    # goto
    goto_p = sub.add_parser("goto", help="Navigate to URL")
    goto_p.add_argument("url", help="Full Clay URL")

    # snapshot
    sub.add_parser("snapshot", help="aria_snapshot() of page body")

    # screenshot
    ss_p = sub.add_parser("screenshot", help="Save PNG screenshot")
    ss_p.add_argument("path", nargs="?", default="/tmp/clay-browser/screenshot.png")

    # click
    click_p = sub.add_parser("click", help="Click element by text")
    click_p.add_argument("text", help="Text to click")
    click_p.add_argument("--role", help="ARIA role (button, menuitem, link, etc.)")
    click_p.add_argument("--nth", type=int, default=None, help="0-indexed match (default: disambiguate)")

    # fill
    fill_p = sub.add_parser("fill", help="Type text")
    fill_p.add_argument("text", help="Text to type")
    fill_p.add_argument("--placeholder", help="Target input by placeholder text")

    # requests
    req_p = sub.add_parser("requests", help="Show captured API calls")
    req_p.add_argument("--filter", help="Filter URLs containing this string")
    req_p.add_argument("--last", type=int, help="Show only last N requests")

    # eval
    eval_p = sub.add_parser("eval", help="Evaluate JavaScript in browser context")
    eval_p.add_argument("js", help="JavaScript to evaluate")

    # click_selector
    sel_p = sub.add_parser("click_selector", help="Click element by CSS selector")
    sel_p.add_argument("selector", help="CSS selector")

    args = parser.parse_args()

    # Daemon mode (internal — spawned by launch_daemon)
    if args.daemon:
        server = ClayBrowserServer()
        server.start(headless=args.headless)
        return

    if not args.command:
        parser.print_help()
        return

    # Launch is special — forks daemon
    if args.command == "launch":
        launch_daemon(headless=args.headless)
        return

    # All other commands go through the client
    client = ClayBrowserClient()

    if args.command == "close":
        result = client.send("close")
    elif args.command == "goto":
        result = client.send("goto", url=args.url)
    elif args.command == "snapshot":
        result = client.send("snapshot")
    elif args.command == "screenshot":
        result = client.send("screenshot", path=args.path)
    elif args.command == "click":
        kwargs = {"text": args.text}
        if args.nth is not None:
            kwargs["nth"] = args.nth
        if args.role:
            kwargs["role"] = args.role
        result = client.send("click", **kwargs)
    elif args.command == "fill":
        kwargs = {"text": args.text}
        if args.placeholder:
            kwargs["placeholder"] = args.placeholder
        result = client.send("fill", **kwargs)
    elif args.command == "requests":
        kwargs = {}
        if args.filter:
            kwargs["filter"] = args.filter
        if args.last:
            kwargs["last"] = args.last
        result = client.send("requests", **kwargs)
    elif args.command == "eval":
        result = client.send("eval", js=args.js)
    elif args.command == "click_selector":
        result = client.send("click_selector", selector=args.selector)
    else:
        parser.print_help()
        return

    # Pretty-print result
    if result.get("ok"):
        # Special formatting for specific commands
        if args.command == "snapshot":
            print(result.get("snapshot", ""))
        elif args.command == "requests":
            reqs = result.get("requests", [])
            if not reqs:
                print("(no captured requests)")
            else:
                for r in reqs:
                    status = r.get("status", "?")
                    method = r.get("method", "?")
                    url = r.get("url", "")
                    # Shorten URL for display
                    short_url = url.replace("https://api.clay.com/v3", "")
                    print(f"\n{method} {short_url}  [{status}]")
                    if r.get("req_body"):
                        print(f"  req: {json.dumps(r['req_body'], indent=2)[:2000]}")
                    if r.get("resp_body") and r["resp_body"] != "(too large)":
                        body_str = json.dumps(r["resp_body"], indent=2)
                        if len(body_str) > 2000:
                            body_str = body_str[:2000] + "\n  ... (truncated)"
                        print(f"  resp: {body_str}")
                print(f"\n({result.get('count', 0)} total)")
        else:
            print(json.dumps(result, indent=2))
    else:
        print(f"ERROR: {result.get('error', 'unknown error')}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
