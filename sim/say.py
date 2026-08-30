"""
One-shot client for the daemon.

Reads JSON request from argv (or fields via flags), prints JSON response.

Usage:
    python say.py --socket /tmp/x.sock start
    python say.py --socket /tmp/x.sock say "Yes this is Kelsey"
    python say.py --socket /tmp/x.sock state
    python say.py --socket /tmp/x.sock transcript
    python say.py --socket /tmp/x.sock shutdown

Exit code is non-zero on backend errors; the JSON response is always printed
on stdout (one line) so callers (subagents) can pipe it to `jq`.
"""

from __future__ import annotations

import argparse
import json
import socket
import sys
import time


def _connect(path: str, attempts: int = 30, delay: float = 0.5) -> socket.socket:
    last_err: Exception | None = None
    for _ in range(attempts):
        try:
            s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            s.connect(path)
            return s
        except (FileNotFoundError, ConnectionRefusedError) as e:
            last_err = e
            time.sleep(delay)
    raise SystemExit(f"could not connect to {path}: {last_err}")


def _send(sock: socket.socket, payload: dict) -> dict:
    sock.sendall((json.dumps(payload) + "\n").encode("utf-8"))
    buf = b""
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf += chunk
        if b"\n" in buf:
            break
    line, _, _ = buf.partition(b"\n")
    return json.loads(line.decode("utf-8"))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--socket", required=True)
    p.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="overall socket timeout in seconds",
    )
    p.add_argument("cmd", choices=["start", "say", "state", "transcript", "shutdown"])
    p.add_argument("text", nargs="?", default=None)
    args = p.parse_args()

    sock = _connect(args.socket)
    sock.settimeout(args.timeout)
    try:
        payload: dict = {"cmd": args.cmd}
        if args.cmd == "say":
            if args.text is None:
                raise SystemExit("say requires text argument")
            payload["text"] = args.text
        resp = _send(sock, payload)
    finally:
        try:
            sock.close()
        except Exception:
            pass

    sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
    sys.stdout.flush()
    if not resp.get("ok", False):
        sys.exit(2)


if __name__ == "__main__":
    main()
