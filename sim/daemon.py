"""
Long-running daemon that owns one Session and exposes it over a Unix socket.

Usage (typical, run in background):
    python daemon.py --to-number 7066226252 \
        --socket /tmp/sim_call_1.sock \
        --transcript /tmp/sim_call_1_transcript.json \
        --stderr /tmp/sim_call_1.stderr

Protocol (newline-delimited JSON):
    request:  {"cmd": "start"}                 -> bootstrap (only the first time)
              {"cmd": "say", "text": "..."}    -> send user message
              {"cmd": "transcript"}            -> save & return transcript
              {"cmd": "state"}                 -> current state
              {"cmd": "shutdown"}              -> exit
    response: {"ok": bool, ...result fields}
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import threading
import traceback

# allow `from session import Session`
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from session import BackendError, Session  # noqa: E402


def _send(conn: socket.socket, payload: dict) -> None:
    line = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
    conn.sendall(line)


def serve(args: argparse.Namespace) -> None:
    if os.path.exists(args.socket):
        os.unlink(args.socket)

    sess = Session(
        to_number=args.to_number,
        from_number=args.from_number,
        log_file=args.stderr,
    )

    started = False
    transcript_path = args.transcript
    lock = threading.Lock()

    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(args.socket)
    srv.listen(4)

    def handle(conn: socket.socket) -> None:
        nonlocal started
        try:
            buf = b""
            while True:
                chunk = conn.recv(65536)
                if not chunk:
                    break
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        req = json.loads(line.decode("utf-8"))
                    except json.JSONDecodeError as e:
                        _send(conn, {"ok": False, "error": f"bad json: {e}"})
                        continue
                    cmd = req.get("cmd")
                    try:
                        with lock:
                            if cmd == "start":
                                if started:
                                    _send(
                                        conn,
                                        {
                                            "ok": True,
                                            "already_started": True,
                                            "first_message": sess.first_message,
                                            "current_state": sess.current_state,
                                        },
                                    )
                                else:
                                    res = sess.start()
                                    started = True
                                    _send(
                                        conn,
                                        {
                                            "ok": True,
                                            "first_message": res.get("text"),
                                            "current_state": res.get("current_state"),
                                            "state_changes": res.get("state_changes"),
                                            "tool_calls": res.get("tool_calls"),
                                        },
                                    )
                            elif cmd == "say":
                                if not started:
                                    res = sess.start()
                                    started = True
                                    text = req.get("text", "")
                                    res2 = sess.say(text)
                                    _send(
                                        conn,
                                        {
                                            "ok": True,
                                            "first_message": res.get("text"),
                                            "text": res2.get("text"),
                                            "current_state": res2.get("current_state"),
                                            "state_changes": res2.get("state_changes"),
                                            "tool_calls": res2.get("tool_calls"),
                                            "call_ended": bool(res2.get("call_ended")),
                                        },
                                    )
                                else:
                                    text = req.get("text", "")
                                    res = sess.say(text)
                                    _send(
                                        conn,
                                        {
                                            "ok": True,
                                            "text": res.get("text"),
                                            "current_state": res.get("current_state"),
                                            "state_changes": res.get("state_changes"),
                                            "tool_calls": res.get("tool_calls"),
                                            "call_ended": bool(res.get("call_ended")),
                                        },
                                    )
                            elif cmd == "transcript":
                                if transcript_path:
                                    sess.save_transcript(
                                        transcript_path,
                                        extra={
                                            "label": args.label,
                                        },
                                    )
                                _send(
                                    conn,
                                    {
                                        "ok": True,
                                        "transcript": sess.get_transcript(),
                                        "saved_to": transcript_path,
                                        "current_state": sess.current_state,
                                    },
                                )
                            elif cmd == "state":
                                _send(
                                    conn,
                                    {
                                        "ok": True,
                                        "current_state": sess.current_state,
                                        "started": started,
                                    },
                                )
                            elif cmd == "shutdown":
                                if transcript_path:
                                    try:
                                        sess.save_transcript(
                                            transcript_path,
                                            extra={"label": args.label},
                                        )
                                    except Exception:
                                        pass
                                _send(conn, {"ok": True})
                                conn.close()
                                srv.close()
                                sess.close()
                                return
                            else:
                                _send(
                                    conn, {"ok": False, "error": f"unknown cmd: {cmd}"}
                                )
                    except BackendError as e:
                        _send(conn, {"ok": False, "error": str(e)})
                    except Exception as e:
                        _send(
                            conn,
                            {
                                "ok": False,
                                "error": f"{type(e).__name__}: {e}",
                                "traceback": traceback.format_exc(),
                            },
                        )
        finally:
            try:
                conn.close()
            except Exception:
                pass

    try:
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                break
            t = threading.Thread(target=handle, args=(conn,), daemon=True)
            t.start()
            t.join()  # serialize requests so they don't race the Session
    finally:
        try:
            srv.close()
        except Exception:
            pass
        try:
            os.unlink(args.socket)
        except FileNotFoundError:
            pass
        sess.close()


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--to-number", required=True)
    p.add_argument("--from-number", default="+10000000000")
    p.add_argument("--socket", required=True)
    p.add_argument("--transcript", required=True)
    p.add_argument("--stderr", required=True)
    p.add_argument("--label", default="")
    args = p.parse_args()
    serve(args)


if __name__ == "__main__":
    main()
