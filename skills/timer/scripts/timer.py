#!/usr/bin/env python3
"""Named countdown timers with macOS notifications.

Three commands: start, list, cancel. State lives in ~/.claude/timer/state.json.
Each timer is a detached background process that sleeps then fires a notification.
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

STATE_DIR = Path.home() / ".claude" / "timer"
STATE_FILE = STATE_DIR / "state.json"


def parse_duration(s: str) -> int:
    s = s.strip().lower()
    if s.isdigit():
        return int(s)
    total = 0
    num = ""
    for ch in s:
        if ch.isdigit():
            num += ch
        elif ch in ("h", "m", "s"):
            if not num:
                raise ValueError(f"bad duration: {s!r}")
            n = int(num)
            total += n * {"h": 3600, "m": 60, "s": 1}[ch]
            num = ""
        else:
            raise ValueError(f"bad duration: {s!r}")
    if num:
        total += int(num)
    if total <= 0:
        raise ValueError(f"duration must be > 0: {s!r}")
    return total


def fmt_remaining(secs: int) -> str:
    secs = max(0, int(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def load_state() -> list:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        return []
    try:
        return json.loads(STATE_FILE.read_text() or "[]")
    except json.JSONDecodeError:
        return []


def save_state(state: list) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False


def prune(state: list) -> list:
    return [t for t in state if pid_alive(t["pid"])]


def cmd_start(args) -> int:
    try:
        duration_sec = parse_duration(args.duration)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    label = args.label or "Timer"

    worker = Path(__file__).resolve()
    # Pass cwd through to the worker so the click-to-show file can show where
    # the timer was set from (helps the user remember which project/session
    # they were in when the timer eventually fires minutes later).
    proc = subprocess.Popen(
        [sys.executable, str(worker), "_worker", str(duration_sec), label, os.getcwd()],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    state = prune(load_state())
    next_id = max((t["id"] for t in state), default=0) + 1
    state.append({
        "id": next_id,
        "label": label,
        "duration_sec": duration_sec,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "pid": proc.pid,
    })
    save_state(state)
    print(f"Timer #{next_id} started: {label} ({fmt_remaining(duration_sec)})")
    return 0


SE_DOCS_DIR = Path.home() / "Library/Mobile Documents/com~apple~ScriptEditor2/Documents"
MESSAGE_PREFIX = "⏰ Timer · "
MAX_MESSAGE_FILES = 5


def _drop_message_file(label: str, context: str = "", cwd: str = "") -> None:
    """Write a `.txt` file to Script Editor's iCloud folder so clicking the
    notification's "Show" button surfaces the message.

    Why: osascript notifications inherit Script Editor's bundle id, so the
    click target is hardcoded to that folder. Rather than fight macOS, we
    use the click target as a feature — the filename IS the message, and
    the file body tells the user where to return and (optionally) why this
    fired. Auto-prunes to MAX_MESSAGE_FILES so iCloud doesn't pile up.
    """
    if not SE_DOCS_DIR.exists():
        return
    try:
        # Sanitize: macOS forbids / and : in filenames; cap at 200 chars
        safe_label = label.replace("/", "-").replace(":", "-").strip()[:200]
        now = datetime.now()
        fname = f"{MESSAGE_PREFIX}{safe_label} ({now.strftime('%H:%M')}).txt"
        fpath = SE_DOCS_DIR / fname

        term = os.environ.get("TERM_PROGRAM", "your terminal")
        cwd_line = f"Working directory: {cwd}\n" if cwd else ""
        context_block = f"\nContext:\n{context}\n" if context else ""
        body = (
            f"⏰ {label}\n"
            f"{'=' * 50}\n\n"
            f"Fired at: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{cwd_line}"
            f"\n→ Switch back to {term} to continue with your Claude session.\n"
            f"{context_block}"
        )
        fpath.write_text(body)

        # Prune old files we created (keep most recent MAX_MESSAGE_FILES)
        ours = sorted(
            (p for p in SE_DOCS_DIR.glob(f"{MESSAGE_PREFIX}*.txt") if p.is_file()),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        for old in ours[MAX_MESSAGE_FILES:]:
            old.unlink(missing_ok=True)
    except OSError:
        pass  # iCloud sync issue, permission, etc. — best-effort


def fire_notification(label: str, context: str = "", cwd: str = "") -> None:
    """Sound + visual notification. Sound is the reliable signal.

    Visual is fired via raw osascript `display notification`, attributed to
    Script Editor (the osascript host's bundle), which most users have
    already granted notification permission. The click target is hardcoded
    to Script Editor's iCloud Documents folder — we exploit that by writing
    a message file there before firing, so clicking the notification surfaces
    the actual message + return instructions + optional context.
    """
    _drop_message_file(label, context=context, cwd=cwd)
    safe = label.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'display notification "{safe}" with title "Timer done"'],
        check=False,
    )


def cmd_worker(argv: list) -> int:
    duration_sec = int(argv[0])
    label = argv[1] if len(argv) > 1 else "Timer"
    cwd = argv[2] if len(argv) > 2 else ""
    try:
        time.sleep(duration_sec)
    except KeyboardInterrupt:
        return 0

    # Sound first — afplay never needs permission, so this is the reliable signal.
    sound_file = "/System/Library/Sounds/Glass.aiff"
    if Path(sound_file).exists():
        for _ in range(3):
            subprocess.run(
                ["afplay", sound_file],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )

    fire_notification(label, cwd=cwd)

    # Remove self from state
    state = load_state()
    me = os.getpid()
    save_state([t for t in state if t.get("pid") != me])
    return 0


def cmd_list(args) -> int:
    state = prune(load_state())
    save_state(state)
    if not state:
        print("No active timers.")
        return 0
    now = datetime.now(timezone.utc)
    print(f"{'ID':<4} {'Label':<30} {'Remaining':<12} Started")
    for t in state:
        started = datetime.fromisoformat(t["started_at"])
        elapsed = (now - started).total_seconds()
        remaining = t["duration_sec"] - elapsed
        local = started.astimezone()
        print(f"{t['id']:<4} {t['label'][:30]:<30} {fmt_remaining(remaining):<12} {local.strftime('%H:%M:%S')}")
    return 0


def cmd_notify(args) -> int:
    """Fire sound + notification immediately. No countdown."""
    label = args.message or "Notification"
    context = args.context or ""
    cwd = os.getcwd()
    sound_file = "/System/Library/Sounds/Glass.aiff"
    if Path(sound_file).exists():
        subprocess.Popen(
            ["afplay", sound_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    fire_notification(label, context=context, cwd=cwd)
    print(f"Notified: {label}")
    return 0


def cmd_cancel(args) -> int:
    state = prune(load_state())
    target = args.target

    if target.isdigit():
        tid = int(target)
        matches = [t for t in state if t["id"] == tid]
    else:
        matches = [t for t in state if target.lower() in t["label"].lower()]

    if not matches:
        print(f"No active timer matching {target!r}.")
        save_state(state)
        return 1

    for t in matches:
        pid = t["pid"]
        try:
            # Kill the whole process group (worker is its own session leader)
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            try:
                os.kill(pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        print(f"Cancelled timer #{t['id']}: {t['label']}")

    cancelled_ids = {t["id"] for t in matches}
    save_state([t for t in state if t["id"] not in cancelled_ids])
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "_worker":
        return cmd_worker(sys.argv[2:])

    p = argparse.ArgumentParser(prog="timer", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    p_start = sub.add_parser("start", help="start a new timer")
    p_start.add_argument("duration", help="e.g. 25m, 90s, 1h30m, or raw seconds")
    p_start.add_argument("label", nargs="?", default=None, help='optional label, e.g. "pomodoro"')
    p_start.set_defaults(func=cmd_start)

    p_list = sub.add_parser("list", help="show active timers")
    p_list.set_defaults(func=cmd_list)

    p_cancel = sub.add_parser("cancel", help="cancel a timer by id or label substring")
    p_cancel.add_argument("target")
    p_cancel.set_defaults(func=cmd_cancel)

    p_notify = sub.add_parser("notify", help="fire sound + notification immediately (no countdown)")
    p_notify.add_argument("message", help="short message for the notification banner")
    p_notify.add_argument(
        "--context", "-c",
        default="",
        help="optional longer body for the click-to-show file (e.g. why this fired, what to do next)",
    )
    p_notify.set_defaults(func=cmd_notify)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
