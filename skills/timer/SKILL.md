---
name: timer
description: Set named countdown timers that fire macOS notifications when done. Manage active timers with list and cancel. Use when the user says "set a timer for X", "remind me in X minutes", "start a pomodoro", "what timers are running", "cancel my timer".
argument-hint: "start <duration> [label] | list | cancel <id-or-label>"
---

# Timer

Manages named countdown timers as detached background processes. Each timer fires a macOS notification (Glass sound) when it expires. State persists in `~/.claude/timer/state.json` and survives across Claude sessions.

Helper: `${CLAUDE_SKILL_DIR}/scripts/timer.py`. Always invoke with `python3`.

## Commands

**Start** — `python3 ${CLAUDE_SKILL_DIR}/scripts/timer.py start <duration> [label]`

- `duration`: `25m`, `90s`, `1h30m`, `2h`, or raw integer (seconds).
- `label`: optional, default `"Timer"`. Quote multi-word labels.

**List** — `python3 ${CLAUDE_SKILL_DIR}/scripts/timer.py list`

Shows id, label, remaining time, and start time for every active timer. Dead PIDs are pruned automatically.

**Cancel** — `python3 ${CLAUDE_SKILL_DIR}/scripts/timer.py cancel <target>`

- Numeric `<target>` → cancel by id.
- Non-numeric → case-insensitive substring match against labels. Cancels every match.

## Intent mapping

- "set a timer for 25 minutes" → `start 25m`
- "remind me in 1 hour to check the laundry" → `start 1h "check the laundry"`
- "start a pomodoro" → `start 25m "pomodoro"`
- "what timers are running" / "show my timers" → `list`
- "cancel the pomodoro" → `cancel pomodoro`
- "cancel timer 3" → `cancel 3`

After starting a timer, print the script's output verbatim — it already confirms the id, label, and duration. No need to restate.

## Notes

- macOS-only. **Zero external dependencies** — uses only built-in `afplay` and `osascript`. Don't suggest `brew install terminal-notifier`.
- **Sound is the reliable signal.** Glass.aiff plays three times via `afplay`. Never needs permission, bypasses DND, always audible.
- **Visual notification is best-effort.** Fired via `osascript display notification`. The notification is attributed to "Script Editor" — that's the osascript host's bundle, and most users have already granted it notification permission long ago.
- **Known limitations of the visual** (don't try to "fix" these — we tried, it's worse):
  - **DND / Focus filters the notification.** Sound still plays.
  - **Clicking the notification opens Script Editor's iCloud folder**, not the user's terminal. Re-attributing requires a permitted app of our own, and there's no programmatic way to grant notification permission to a freshly-built AppleScript applet on modern macOS — macOS silently filters un-permitted apps with no prompt. We tried osacompile+plutil+codesign+lsregister; the apparent fix doesn't actually fire visible notifications.
- Cancellation kills the worker's process group (`killpg` with `SIGTERM`), so no orphan `sleep` lingers.
- State auto-prunes dead PIDs on every `start`, `list`, and `cancel`.
- Timers fire even if Claude Code is closed — workers are detached via `start_new_session=True`.
