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
    proc = subprocess.Popen(
        [sys.executable, str(worker), "_worker", str(duration_sec), label],
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


def fire_notification(label: str) -> None:
    """Best-effort visual notification. Sound is the reliable signal — fired separately.

    Uses raw osascript `display notification`. The notification is attributed to
    "Script Editor" (the osascript host's bundle id), so it inherits Script Editor's
    notification permission — which most macOS users already have granted.

    Tradeoffs accepted here (after burning many turns trying to do better):
      - Clicking the notification opens Script Editor's iCloud folder, not the
        user's terminal. Re-attributing requires a permitted app of our own,
        and there's no programmatic way to grant notification permission to a
        freshly-built AppleScript applet on modern macOS.
      - DND filters this like any other notification. Sound bypasses DND.
    """
    safe = label.replace("\\", "\\\\").replace('"', '\\"')
    subprocess.run(
        ["osascript", "-e", f'display notification "{safe}" with title "Timer done"'],
        check=False,
    )


def cmd_worker(argv: list) -> int:
    duration_sec = int(argv[0])
    label = argv[1] if len(argv) > 1 else "Timer"
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

    fire_notification(label)

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

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
